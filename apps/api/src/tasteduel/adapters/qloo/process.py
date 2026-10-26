"""One bounded canonical MCP child per API instance. Protocol data never enters logs."""

from __future__ import annotations

import asyncio
import contextvars
import json
import math
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from tasteduel.adapters.qloo.schema import valid_input

ReserveUpstream = Callable[[str], Awaitable[None]]
TOOLS = frozenset({"qloo_capabilities", "qloo_describe", "qloo_recommend"})
CHECKSUM = "sha256:762bdcc5e14ff797b6de739d2658a83f78af35e68d7a5a3449455be6046924f5"


class McpFailure(Exception):
    """Only a safe code, never subprocess or provider text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ManagedMcpProcess:
    def __init__(
        self,
        *,
        node: str = "node",
        runner: Path,
        api_key: str | None = None,
        reserve_upstream: ReserveUpstream | None = None,
        note_dispatch: Callable[[str], None] | None = None,
        startup_timeout: float = 5,
        call_timeout: float = 12,
        max_restarts: int = 2,
        command: tuple[str, ...] | None = None,
        contract_snapshot: Path | None = None,
    ):
        if (
            not math.isfinite(startup_timeout)
            or not math.isfinite(call_timeout)
            or startup_timeout <= 0
            or call_timeout <= 0
            or type(max_restarts) is not int
            or not 0 <= max_restarts <= 3
        ):
            raise ValueError("Invalid MCP bounds")
        self.command = command or (node, str(runner.resolve()))
        self._snapshot = (contract_snapshot or runner.resolve().parent / "discovered-contract.json").resolve()
        self._api_key = api_key
        self._reserve_default = reserve_upstream
        self._note_dispatch = note_dispatch
        self.startup_timeout, self.call_timeout, self.max_restarts = (
            startup_timeout,
            call_timeout,
            max_restarts,
        )
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task | None = None
        self._stderr: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._sequence = 0
        self._starts = 0
        self._ready = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._reserve: ReserveUpstream | None = None
        self._context: contextvars.Context | None = None
        self.http_statuses: list[int] = []
        self.stderr_lines_discarded = 0
        self.tool_schemas: dict[str, dict] = {}

    @property
    def ready(self) -> bool:
        return self._ready and self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        async with self._start_lock:
            if self.ready:
                return
            if self._closed:
                raise McpFailure("MCP_CLOSED")
            if self._starts > self.max_restarts:
                raise McpFailure("MCP_RESTART_LIMIT")
            await self._stop()
            self._starts += 1
            env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP") if key in os.environ}
            if self._api_key:
                env["QLOO_API_KEY"] = self._api_key
            try:
                async with asyncio.timeout(self.startup_timeout):
                    self._process = await asyncio.create_subprocess_exec(
                        *self.command,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                        limit=2_100_000,
                    )
                    self._reader = asyncio.create_task(self._read())
                    self._stderr = asyncio.create_task(self._drain_stderr())
                    initialized = await self._rpc(
                        "initialize",
                        {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "tasteduel", "version": "0.1.0"},
                        },
                    )
                    if initialized.get("serverInfo", {}).get("version") != "0.1.26":
                        raise McpFailure("MCP_VERSION_MISMATCH")
                    await self._write({"jsonrpc": "2.0", "method": "notifications/initialized"})
                    listing = await self._rpc("tools/list", {})
                    tools = listing.get("tools")
                    if not isinstance(tools, list):
                        raise McpFailure("MCP_INVALID_SCHEMA")
                    self.tool_schemas = {
                        t["name"]: t["inputSchema"]
                        for t in tools
                        if isinstance(t, dict)
                        and t.get("name") in TOOLS
                        and isinstance(t.get("inputSchema"), dict)
                    }
                    if set(self.tool_schemas) != TOOLS:
                        raise McpFailure("MCP_INVALID_SCHEMA")
                    snapshot = self._snapshot
                    if not snapshot.is_file():
                        raise McpFailure("MCP_SCHEMA_SNAPSHOT_MISSING")
                    expected = json.loads(snapshot.read_text(encoding="utf-8"))
                    expected = {tool["name"]: tool["inputSchema"] for tool in expected["tools"]["tools"]}
                    if self.tool_schemas != expected:
                        raise McpFailure("MCP_SCHEMA_MISMATCH")
                    capability = await self._rpc("tools/call", {"name": "qloo_capabilities", "arguments": {}})
                    structured = capability.get("structuredContent", {})
                    if structured.get("contract_checksum") != CHECKSUM:
                        raise McpFailure("MCP_CONTRACT_MISMATCH")
                    self._ready = True
            except asyncio.CancelledError:
                await self._stop()
                raise
            except TimeoutError:
                await self._stop()
                raise McpFailure("MCP_STARTUP_TIMEOUT") from None
            except McpFailure:
                await self._stop()
                raise
            except Exception:
                await self._stop()
                raise McpFailure("MCP_STARTUP_FAILURE") from None

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        reserve_upstream: ReserveUpstream | None = None,
    ) -> dict:
        if name not in TOOLS:
            raise McpFailure("MCP_WORKFLOW_BLOCKED")
        context = contextvars.copy_context()
        owns_operation = False
        try:
            async with asyncio.timeout(self.call_timeout):
                async with self._lock:
                    owns_operation = True
                    await self.start()
                    if not valid_input(arguments, self.tool_schemas[name]):
                        raise McpFailure("MCP_ARGUMENTS_INVALID")
                    self._reserve = reserve_upstream or self._reserve_default
                    self._context = context
                    self.http_statuses = []
                    try:
                        result = await self._rpc("tools/call", {"name": name, "arguments": arguments})
                        # Snapshot while the call lock is still held. Never consult another call's status list.
                        return {**result, "_tasteduel_http_statuses": tuple(self.http_statuses)}
                    finally:
                        self._reserve, self._context = None, None
        except (TimeoutError, asyncio.CancelledError) as failure:
            # Canonical 0.1.26 ignores cancellation notifications. Reap to stop abandoned work.
            if owns_operation:
                await self._stop()
            if isinstance(failure, asyncio.CancelledError):
                raise
            raise McpFailure("MCP_DEADLINE") from None

    async def _rpc(self, method: str, params: dict) -> dict:
        self._sequence += 1
        identifier = self._sequence
        future = asyncio.get_running_loop().create_future()
        self._pending[identifier] = future
        try:
            await self._write({"jsonrpc": "2.0", "id": identifier, "method": method, "params": params})
            return await future
        finally:
            self._pending.pop(identifier, None)

    async def _write(self, message: dict) -> None:
        process = self._process
        if not process or not process.stdin or process.returncode is not None:
            raise McpFailure("MCP_PROCESS_EXIT")
        try:
            process.stdin.write(json.dumps(message, allow_nan=False).encode() + b"\n")
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionError):
            raise McpFailure("MCP_PROCESS_EXIT") from None

    async def _read(self) -> None:
        assert self._process and self._process.stdout
        try:
            while line := await self._process.stdout.readline():
                message = json.loads(line)
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    raise McpFailure("MCP_INVALID_FRAME")
                if message.get("method") == "tasteduel/reserve":
                    allowed = False
                    path = message.get("params", {}).get("path")
                    if self._reserve and self._context and path in {"/search", "/entities", "/v2/insights"}:
                        try:
                            await asyncio.create_task(self._reserve(path), context=self._context.copy())
                            allowed = True
                        except Exception:
                            pass  # deny safely; callback's original text never reaches child/logs
                    await self._write(
                        {"jsonrpc": "2.0", "id": message.get("id"), "result": {"allowed": allowed}}
                    )
                elif message.get("method") == "tasteduel/dispatch":
                    path = message.get("params", {}).get("path")
                    if self._context and self._note_dispatch:
                        self._context.copy().run(self._note_dispatch, path)
                elif message.get("method") == "tasteduel/http":
                    status = message.get("params", {}).get("status")
                    if type(status) is int and 100 <= status <= 599 and len(self.http_statuses) < 6:
                        self.http_statuses.append(status)
                elif "id" in message:
                    future = self._pending.get(message["id"])
                    if future and not future.done():
                        if "error" in message:
                            future.set_exception(McpFailure("MCP_RPC_FAILURE"))
                        elif isinstance(message.get("result"), dict):
                            future.set_result(message["result"])
                        else:
                            future.set_exception(McpFailure("MCP_INVALID_FRAME"))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Bad framing is terminal; do not leave an orphan doing provider work.
            await self._stop()
        finally:
            self._ready = False
            await self._stop()
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(McpFailure("MCP_PROCESS_EXIT"))

    async def _drain_stderr(self) -> None:
        assert self._process and self._process.stderr
        while await self._process.stderr.read(4096):
            self.stderr_lines_discarded += 1  # Never copy arbitrary stderr, even after regex redaction.

    async def _stop(self) -> None:
        self._ready = False
        process = self._process
        if process and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), 1)
            except TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
        for task in (self._reader, self._stderr):
            if task and task is not asyncio.current_task() and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self._process = None

    async def close(self) -> None:
        self._closed = True
        await self._stop()
