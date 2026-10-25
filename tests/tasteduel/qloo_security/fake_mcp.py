"""Offline hostile MCP child used only by subprocess-boundary tests.

All keys, titles and environment values in these tests are synthetic. This helper
never imports the Qloo harness or makes network requests.
"""

import json
import os
from pathlib import Path
import sys
import threading
import time


mode = sys.argv[1]
# Public offline schemas only, not live provider output. Exact schema checking
# remains enabled while hostile process behavior is simulated independently.
contract = json.loads(
    (Path(__file__).resolve().parents[3] / "runtime/qloo/discovered-contract.json").read_text(
        encoding="utf-8"
    )
)
lock = threading.Lock()


def emit(value):
    with lock:
        sys.stdout.write(json.dumps(value) + "\n")
        sys.stdout.flush()


def reply(request, result):
    emit({"jsonrpc": "2.0", "id": request["id"], "result": result})


def tool_reply(request):
    if mode == "exit":
        os._exit(23)
    if mode == "hang":
        time.sleep(60)
        return
    if mode == "malformed":
        sys.stdout.write("not MCP JSON; synthetic-sensitive-value\n")
        sys.stdout.flush()
        return
    if mode == "oversized":
        sys.stdout.write("x" * (2 * 1024 * 1024) + "\n")
        sys.stdout.flush()
        return
    if mode == "stderr":
        sys.stderr.write("synthetic-sensitive-value " * 2000 + "\n")
        sys.stderr.flush()
    if mode in {"reserve", "reserve_invalid_path"}:
        emit(
            {
                "jsonrpc": "2.0",
                "id": "reserve-offline-1",
                "method": "tasteduel/reserve",
                "params": {"path": "/search" if mode == "reserve" else "/unapproved"},
            }
        )
        # The main input loop processes the parent's reservation response. The
        # marker is returned only when an upstream dispatch would be allowed.
        reservations["reserve-offline-1"] = request
        return
    if mode == "concurrent":
        # Responses intentionally finish in reverse order.
        time.sleep(0.08 if request["params"]["arguments"].get("entity") == "first" else 0.01)
        emit(
            {
                "jsonrpc": "2.0",
                "method": "tasteduel/http",
                "params": {"status": 200 if request["params"]["arguments"].get("entity") == "first" else 429},
            }
        )
    reply(
        request,
        {
            "content": [],
            "structuredContent": {
                "synthetic": True,
                "entity": request["params"]["arguments"].get("entity"),
                "environment_keys": sorted(os.environ),
                "pid": os.getpid(),
            },
        },
    )


reservations = {}
for raw in sys.stdin:
    request = json.loads(raw)
    method = request.get("method")
    if not method and request.get("id") in reservations:
        caller = reservations.pop(request["id"])
        reply(caller, {"structuredContent": {"dispatched": request.get("result", {}).get("allowed") is True}})
        continue
    if method == "initialize":
        if mode == "startup_hang":
            time.sleep(60)
        reply(
            request,
            {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "qloo-harness", "version": "0.1.26"},
                "capabilities": {"tools": {}},
            },
        )
    elif method == "tools/list":
        reply(request, contract["tools"])
    elif method == "tools/call" and request["params"]["name"] == "qloo_capabilities":
        capabilities = contract["capabilities"]
        if mode == "bad_contract":
            capabilities = dict(capabilities, contract_checksum="sha256:" + "0" * 64)
        reply(request, {"structuredContent": capabilities, "content": []})
    elif method == "tools/call":
        if mode == "concurrent":
            threading.Thread(target=tool_reply, args=(request,), daemon=True).start()
        else:
            tool_reply(request)
