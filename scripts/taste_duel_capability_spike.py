"""Bounded capability probe. Live output is aggregate metadata, never API payloads.

Install the reviewed harness into ignored .data/qloo-prompt2/harness first.
Offline is the default; --live additionally requires the explicit review flag.
No application configuration or credential-history file is loaded.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".data" / "qloo-prompt2"
HARNESS_VERSION = "0.1.26"
SECRET = "projects/project-bb13ecd8-9d67-408d-9a7/secrets/accesslife-qloo-api-key/versions/latest"
HARD_REQUEST_LIMIT = 12

# Internal imports are pinned spike-only, not a proposed production adapter API.
RUNNER = r"""
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const root = process.env.PROBE_ARTIFACTS;
const pkg = root + '/harness/node_modules/@qloo/qloo-harness';
const ledger = root + '/ledger.jsonl';
const live = process.env.PROBE_LIVE === '1';
const realFetch = globalThis.fetch;
let tail = Promise.resolve();
let attempts = fs.existsSync(ledger) ? fs.readFileSync(ledger,'utf8').split('\n').filter(Boolean).length : 0;
function record(entry) { fs.appendFileSync(ledger,JSON.stringify(entry)+'\n',{encoding:'utf8',mode:0o600}); }
const guardedFetch = async (input, init={}) => {
  const previous = tail;
  let release;
  tail = new Promise(resolve => { release=resolve; });
  await previous;
  try {
    const url = new URL(input instanceof Request ? input.url : input.toString());
    if (!live) throw new Error('PROBE_OFFLINE_NETWORK_BLOCKED');
    const method=init.method ?? (input instanceof Request ? input.method : 'GET');
    if (url.origin !== 'https://hackathon.api.qloo.com' || url.username || url.password || !['/search','/entities','/v2/insights'].includes(url.pathname) || method !== 'GET') throw new Error('PROBE_ENDPOINT_BLOCKED');
    if (attempts >= 12) throw new Error('PROBE_HARD_CAP_REACHED');
    attempts += 1;
    const ordinal=attempts, started=Date.now();
    // Reserve before dispatch: even connection failures consume the local budget.
    record({ordinal,path:url.pathname,method:'GET',reserved_at:new Date().toISOString()});
    const response=await realFetch(input,{...init,redirect:'manual',signal:AbortSignal.any([...(init.signal?[init.signal]:[]),AbortSignal.timeout(12000)])});
    const chunks=[]; let size=0;
    if(response.body) {
      const reader=response.body.getReader();
      while(true) { const {value,done}=await reader.read(); if(done) break; size+=value.byteLength; if(size>2000000) {await reader.cancel();throw new Error('PROBE_BODY_LIMIT');} chunks.push(Buffer.from(value)); }
    }
    const bytes=Buffer.concat(chunks);
    const headers={};
    for (const [name,value] of response.headers) {
      if (/^(?:x-)?(?:rate-?limit|quota)/i.test(name) || /(?:expir|retry-after)/i.test(name)) headers[name]=value;
    }
    const summary={ordinal,status:response.status,elapsed_ms:Date.now()-started,headers};
    try {
      const body=JSON.parse(bytes.toString('utf8'));
      const entities=Array.isArray(body.results)?body.results:(body.results?.entities??[]);
      const scores=entities.map(e=>e.query?.affinity??e.affinity).filter(v=>typeof v==='number'&&Number.isFinite(v));
      Object.assign(summary,{raw_top_keys:Object.keys(body),raw_entity_count:entities.length,raw_types:[...new Set(entities.map(e=>e.type).filter(Boolean))],raw_subtypes:[...new Set(entities.map(e=>e.subtype).filter(Boolean))],raw_query_affinity_count:entities.filter(e=>typeof e.query?.affinity==='number').length,raw_top_affinity_count:entities.filter(e=>typeof e.affinity==='number').length,raw_finite_affinities:scores.length,raw_affinity_min:scores.length?Math.min(...scores):null,raw_affinity_max:scores.length?Math.max(...scores):null,raw_affinities_nonincreasing:scores.every((v,i)=>i===0||scores[i-1]>=v),raw_adjacent_ties:scores.slice(1).filter((v,i)=>scores[i]===v).length,raw_images:entities.filter(e=>e.properties?.image).length,raw_entity_explainability:entities.filter(e=>e.query?.explainability).length,raw_global_explainability:Boolean(body.query?.explainability),raw_warning_count:Array.isArray(body.warnings)?body.warnings.length:body.warnings?1:0});
    } catch { summary.json_summary_unavailable=true; }
    fs.appendFileSync(root+'/responses-meta.jsonl',JSON.stringify(summary)+'\n',{encoding:'utf8',mode:0o600});
    // Buffer before releasing to ensure only one upstream request is active.
    await new Promise(resolve=>setTimeout(resolve,200));
    return new Response(bytes,{status:response.status,statusText:response.statusText,headers:response.headers});
  } finally { release(); }
};
// Install before loading the harness; this also blocks unexpected auxiliary fetches.
globalThis.fetch=guardedFetch;
const clientModule=await import(pathToFileURL(pkg+'/dist/chunks/chunk-ESNY4EJL.js').href);
const {createQlooTools}=await import(pathToFileURL(pkg+'/dist/qloo-tools.js').href);
const {startCanonicalMcpServer}=await import(pathToFileURL(pkg+'/dist/mcp.js').href);
const client=new clientModule.QlooClient({apiKey:process.env.QLOO_API_KEY || 'synthetic-offline-placeholder',baseUrl:'https://hackathon.api.qloo.com',allowCustomBaseUrl:true,maxAttempts:1,timeoutMs:12000,maxResponseBytes:2000000,fetch:guardedFetch});
startCanonicalMcpServer({tools:createQlooTools({client}),serverVersion:'0.1.26'});
"""


class McpProbe:
    """Small sequential JSON-RPC stdio driver with bounded reads and sanitized failures."""

    def __init__(self, *, live: bool = False, key: str = ""):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        package = ARTIFACTS / "harness/node_modules/@qloo/qloo-harness/package.json"
        if json.loads(package.read_text(encoding="utf-8"))["version"] != HARNESS_VERSION:
            raise RuntimeError("Pinned harness version mismatch")
        runner = ARTIFACTS / "probe-runner.mjs"
        runner.write_text(RUNNER, encoding="utf-8")
        env = {name: os.environ[name] for name in ("PATH", "SystemRoot", "TEMP", "TMP") if name in os.environ}
        env.update(PROBE_ARTIFACTS=ARTIFACTS.as_posix(), PROBE_LIVE="1" if live else "0")
        if key:
            env["QLOO_API_KEY"] = key
        self.process = subprocess.Popen(
            ["node", str(runner)], cwd=ARTIFACTS, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.counter = 0
        threading.Thread(target=self._read_stdout, daemon=True).start()
        # Drain without printing/storing arbitrary stderr, including payload-bearing errors.
        threading.Thread(target=lambda: self.process.stderr.read(), daemon=True).start()
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "tasteduel-capability-probe", "version": "1"}})
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.process.stdin.flush()

    def _read_stdout(self):
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def rpc(self, method: str, params: dict | None = None) -> dict:
        self.counter += 1
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.counter, "method": method, "params": params or {}}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            line = self.lines.get(timeout=max(0.01, deadline - time.monotonic()))
            if line is None:
                raise RuntimeError("MCP process closed unexpectedly; stderr deliberately redacted")
            value = json.loads(line)
            if value.get("id") == self.counter:
                if "error" in value:
                    raise RuntimeError("MCP protocol error; private details redacted")
                return value["result"]
        raise TimeoutError("MCP response deadline exceeded")

    def call(self, name: str, arguments: dict) -> dict:
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if isinstance(result.get("structuredContent"), dict):
            return result["structuredContent"]
        raise RuntimeError("MCP structured envelope missing")

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=5)


def ledger_count() -> int:
    path = ARTIFACTS / "ledger.jsonl"
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def offline_inspection() -> dict:
    before = ledger_count()
    probe = McpProbe()
    try:
        tools = probe.rpc("tools/list")
        capabilities = probe.call("qloo_capabilities", {})
        (ARTIFACTS / "offline-contract.json").write_text(json.dumps({"tools": tools, "capabilities": capabilities}, indent=2), encoding="utf-8")
        return {"harness_version": HARNESS_VERSION, "tool_names": [tool["name"] for tool in tools["tools"]], "capabilities_ready": capabilities.get("adapter", {}).get("ready"), "upstream_requests": ledger_count() - before}
    finally:
        probe.close()


def entity_type(row: dict) -> str | None:
    """Preserve the native resolver's subtype/type/types-array precedence."""
    direct = row.get("subtype") or row.get("type")
    if isinstance(direct, str) and direct.startswith("urn:entity:"):
        return direct
    types = row.get("types", [])
    if isinstance(types, list):
        for item in types:
            if isinstance(item, str) and item.startswith("urn:entity:"):
                return item
    return direct


def summarize_ranking(result: dict, target: str, seed_id: str) -> dict:
    """Aggregate feasibility only; do not persist a response, names, IDs or answer pairs."""
    records = result.get("results", [])
    if not isinstance(records, list):
        raise ValueError("Invalid results envelope")
    eligible, seen = [], set()
    wrong_type = missing_identity = duplicate = 0
    for row in records:
        if not isinstance(row, dict):
            missing_identity += 1
            continue
        entity_id, name, score = row.get("entity_id"), row.get("name"), row.get("affinity")
        if not isinstance(entity_id, str) or not entity_id or not isinstance(name, str) or not name:
            missing_identity += 1
            continue
        if entity_id == seed_id or entity_id in seen:
            duplicate += 1
            continue
        seen.add(entity_id)
        if entity_type(row) not in (target, "urn:entity:" + target):
            wrong_type += 1
            continue
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            continue
        eligible.append(row)
    values = [row["affinity"] for row in eligible]
    match_counts = {}
    for epsilon in (0, 0.000001, 0.0001, 0.001, 0.01):
        ordered = sorted(values)
        left, right, count = 0, len(ordered) - 1, 0
        while left < right and ordered[right] - ordered[left] > epsilon:
            count += 1
            left += 1
            right -= 1
        match_counts[str(epsilon)] = count
    return {
        "status": result.get("status"), "result_count": len(records), "eligible_unique": len(eligible),
        "duplicate_or_seed": duplicate, "missing_identity": missing_identity, "wrong_type": wrong_type,
        "compact_affinity_min": min(values) if values else None,
        "compact_affinity_max": max(values) if values else None,
        "compact_affinities_nonincreasing": all(a >= b for a, b in zip(values, values[1:])),
        "distinct_affinities": len(set(values)), "images": sum(bool(row.get("properties", {}).get("image")) for row in eligible),
        "entity_explanations": sum(bool(row.get("explainability")) for row in eligible),
        "global_explainability": bool(result.get("explainability")),
        "disjoint_extreme_pair_lower_bounds_by_raw_unit_epsilon": match_counts,
        "result_keys": sorted(result),
        "warning_count": len(result.get("warnings", [])),
    }


def chosen_seed(result: dict, expected_type: str) -> str | None:
    """A probe never guesses a resolution outcome. Ambiguity remains a failed seed."""
    if result.get("status") not in ("ok", "partial", "degraded"):
        return None
    records = result.get("results", [])
    if len(records) != 1:
        return None
    row = records[0]
    kind = entity_type(row)
    interpreted = result.get("interpretation", {}).get("entity", {})
    if kind is None and interpreted.get("entityId") == row.get("entity_id"):
        kind = interpreted.get("type")
    if kind not in (expected_type, "urn:entity:" + expected_type):
        return None
    return row.get("entity_id")


def live_inspection(*, resume_reviewed: bool = False) -> dict:
    lock_path = ARTIFACTS / "live-probe.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Persistent reservations prohibit a second invocation from resetting the cap.
    if ledger_count() and not resume_reviewed:
        raise RuntimeError("This capability ledger already contains requests; inspect it instead of restarting the live spike")
    if resume_reviewed and ledger_count() != 6:
        raise RuntimeError("Reviewed continuation is permitted only from the six-request checkpoint")
    with lock_path.open("x", encoding="utf-8") as lock:
        lock.write("Single sequential capability live owner; no credentials\n")
    probe = None
    try:
        from google.cloud import secretmanager

        response = secretmanager.SecretManagerServiceClient().access_secret_version(request={"name": SECRET}, timeout=8)
        key = response.payload.data.decode("utf-8").strip()
        probe = McpProbe(live=True, key=key)
        del key, response
        report = {"harness_version": HARNESS_VERSION, "transport": "official canonical MCP exports with injected bounded QlooClient", "max_attempts": 1, "request_timeout_ms": 12000, "hard_request_cap": HARD_REQUEST_LIMIT, "seeds": [], "rankings": [], "vertex": "deferred to curator"}
        seeds = []
        initial_seeds = (("artist-seed", "Radiohead", "artist"), ("movie-seed", "Inception", "movie"))
        for label, name, kind in (() if resume_reviewed else initial_seeds):
            before = ledger_count()
            result = probe.call("qloo_describe", {"entity": name, "type": kind})
            entity_id = chosen_seed(result, kind)
            report["seeds"].append({"label": label, "requested_name": name, "type": kind, "status": result.get("status"), "resolved": bool(entity_id), "requests": ledger_count() - before, "result_count": result.get("result_count"), "result_keys": sorted(result)})
            if entity_id:
                seeds.append((label, entity_id, kind))
        if resume_reviewed:
            # Same native resolver in a fresh MCP process: one untyped search per
            # name, then its in-process outcome is reused for the second target.
            seeds = list(initial_seeds)
            report["continuation"] = "Six prior requests retained; correct subtype precedence, no repeated describe. Named signals are independently resolved by the canonical harness."
        for label, entity_id, kind in seeds:
            for target in ("movie", "artist"):
                if ledger_count() >= HARD_REQUEST_LIMIT:
                    break
                before = ledger_count()
                result = probe.call("qloo_recommend", {"target_type": target, "signals": [entity_id], "explain": True, "limit": 20})
                signals = result.get("interpretation", {}).get("signals", [])
                resolved_seed = signals[0].get("entityId", "") if len(signals) == 1 else ""
                summary = summarize_ranking(result, target, resolved_seed or entity_id)
                summary.update(seed=label, seed_type=kind, target_type=target, cross_domain=kind != target, requests=ledger_count() - before)
                summary["resolved_signal_types"] = [signal.get("type") for signal in signals]
                summary["resolved_signal_count"] = len(signals)
                report["rankings"].append(summary)
        if not resume_reviewed and ledger_count() < HARD_REQUEST_LIMIT:
            before = ledger_count()
            result = probe.call("qloo_describe", {"entity": "Phoenix", "type": "artist"})
            report["ambiguity"] = {"requested_name": "Phoenix", "type": "artist", "status": result.get("status"), "requests": ledger_count() - before, "result_count": result.get("result_count"), "result_keys": sorted(result)}
        report["total_upstream_requests"] = ledger_count()
        report["quota_expiry_headers"] = [json.loads(line).get("headers", {}) for line in (ARTIFACTS / "responses-meta.jsonl").read_text(encoding="utf-8").splitlines()]
        filename = "capability-continuation-summary.json" if resume_reviewed else "capability-summary.json"
        (ARTIFACTS / filename).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        if probe:
            probe.close()
        lock_path.unlink(missing_ok=True)


def raw_wire_summary(body: dict) -> dict:
    results = body.get("results", [])
    records = results if isinstance(results, list) else results.get("entities", []) if isinstance(results, dict) else []
    scores = [row.get("query", {}).get("affinity", row.get("affinity")) for row in records]
    finite = [value for value in scores if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)]
    return {
        "raw_top_keys": sorted(body), "raw_entity_count": len(records),
        "raw_entity_field_names": sorted({key for row in records for key in row}),
        "raw_effective_types": sorted({entity_type(row) for row in records if entity_type(row)}),
        "raw_query_affinity_count": sum("affinity" in row.get("query", {}) for row in records),
        "raw_top_affinity_count": sum("affinity" in row for row in records),
        "raw_affinity_field_conflicts": sum("affinity" in row and "affinity" in row.get("query", {}) and row["affinity"] != row["query"]["affinity"] for row in records),
        "raw_finite_affinities": len(finite),
        "raw_affinity_min": min(finite) if finite else None, "raw_affinity_max": max(finite) if finite else None,
        "raw_affinities_nonincreasing": bool(finite) and all(a >= b for a, b in zip(finite, finite[1:])),
        "raw_adjacent_ties": sum(a == b for a, b in zip(finite, finite[1:])),
        "raw_images": sum(bool(row.get("properties", {}).get("image")) for row in records),
        "raw_entity_explainability": sum(bool(row.get("query", {}).get("explainability")) for row in records),
        "raw_global_explainability": bool(body.get("query", {}).get("explainability")),
        "raw_top_query_fields": sorted(body.get("query", {})),
        "raw_warning_count": len(body.get("warnings", [])),
    }


def insights_parameters(seed_id: str, target: str) -> dict:
    """Explicit diagnostic subset verified against the movie/artist parameter guides."""
    if target not in ("artist", "movie") or not isinstance(seed_id, str) or not seed_id:
        raise ValueError("Unsupported diagnostic target or unresolved seed")
    return {"filter.type": "urn:entity:" + target, "signal.interests.entities": seed_id,
            "take": 20, "feature.explainability": "true", "sort_by": "affinity"}


def raw_reviewed_continuation() -> dict:
    """Explicit four-request diagnostic escape hatch, not a production MCP fallback."""
    import httpx
    from google.cloud import secretmanager

    if ledger_count() != 8:
        raise RuntimeError("Raw continuation is restricted to the reviewed eight-request checkpoint")
    lock_path = ARTIFACTS / "live-probe.lock"
    with lock_path.open("x", encoding="utf-8") as lock:
        lock.write("Four-request reviewed raw diagnostic continuation; no credentials\n")
    try:
        secret = secretmanager.SecretManagerServiceClient().access_secret_version(request={"name": SECRET}, timeout=8)
        key = secret.payload.data.decode("utf-8").strip()
        report = {"transport": "explicit raw HTTP diagnostic escape hatch; canonical MCP Insights remains unverified", "prior_upstream_requests": 8, "seeds": [], "rankings": [], "vertex": "deferred", "within_target_cells": "unverified within this request budget"}
        with httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
            def get(path: str, params: dict) -> dict:
                if path not in ("/search", "/v2/insights") or ledger_count() >= HARD_REQUEST_LIMIT:
                    raise RuntimeError("Raw probe endpoint/budget blocked")
                ordinal = ledger_count() + 1
                with (ARTIFACTS / "ledger.jsonl").open("a", encoding="utf-8") as ledger:
                    ledger.write(json.dumps({"ordinal": ordinal, "path": path, "method": "GET", "reserved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "transport": "explicit-raw-diagnostic"}) + "\n")
                started, content = time.monotonic(), bytearray()
                with client.stream("GET", "https://hackathon.api.qloo.com" + path, params=params, headers={"X-Api-Key": key, "Accept": "application/json"}) as response:
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > 2_000_000:
                            raise RuntimeError("Raw probe body limit exceeded")
                    headers = {name: value for name, value in response.headers.items() if re.match(r"^(?:x-)?(?:rate-?limit|quota)", name, re.I) or re.search(r"expir|retry-after", name, re.I)}
                    body = json.loads(content)
                    meta = {"ordinal": ordinal, "status": response.status_code, "elapsed_ms": round((time.monotonic() - started) * 1000), "headers": headers, **raw_wire_summary(body)}
                    with (ARTIFACTS / "responses-meta.jsonl").open("a", encoding="utf-8") as target:
                        target.write(json.dumps(meta) + "\n")
                    if response.status_code != 200:
                        raise RuntimeError("Raw probe HTTP failure; details redacted")
                    time.sleep(0.2)
                    return body

            resolved = []
            for name, kind, target in (("Radiohead", "artist", "movie"), ("Inception", "movie", "artist")):
                body = get("/search", {"query": name, "types": "urn:entity:" + kind, "take": 5})
                records = body.get("results", [])
                if isinstance(records, dict):
                    records = records.get("entities", [])
                matches = [row for row in records if row.get("name", "").casefold() == name.casefold() and entity_type(row) == "urn:entity:" + kind]
                if len(matches) != 1:
                    report["seeds"].append({"requested_name": name, "expected_type": kind, "unique_exact_typed_match": False, "matching_count": len(matches)})
                    continue
                selected = matches[0]
                report["seeds"].append({"requested_name": name, "expected_type": kind, "unique_exact_typed_match": True, "matching_count": 1, "source_domain_field": "subtype" if selected.get("subtype") else "type" if selected.get("type") else "types[]"})
                resolved.append((name, kind, target, selected["entity_id"]))
            for name, kind, target, seed_id in resolved:
                body = get("/v2/insights", insights_parameters(seed_id, target))
                records = body.get("results", {}).get("entities", [])
                if raw_wire_summary(body)["raw_affinity_field_conflicts"]:
                    raise ValueError("Conflicting score fields; no feasibility claim")
                # Use observed query.affinity, retaining type information dropped
                # by compactEntity. This diagnostic is not a production adapter.
                normalized = [{**row, "affinity": row.get("query", {}).get("affinity", row.get("affinity")), "explainability": row.get("query", {}).get("explainability")} for row in records]
                summary = summarize_ranking({"status": "ok", "results": normalized, "explainability": body.get("query", {}).get("explainability")}, target, seed_id)
                summary.update(seed=name, seed_type=kind, target_type=target, cross_domain=True, wire=raw_wire_summary(body), explicit_sort_by_sent=True)
                report["rankings"].append(summary)
        report["total_upstream_requests"] = ledger_count()
        (ARTIFACTS / "raw-capability-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        lock_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--reviewed-budget", action="store_true")
    parser.add_argument("--resume-reviewed", action="store_true", help="Reviewed six-request continuation only; never resets the persistent ledger")
    parser.add_argument("--raw-reviewed", action="store_true", help="Reviewed remaining four-request raw diagnostic from the eight-request checkpoint")
    args = parser.parse_args()
    if args.live and not args.reviewed_budget:
        parser.error("Live workflow requires --reviewed-budget after offline schema and twelve-request-plan review")
    try:
        report = raw_reviewed_continuation() if args.live and args.raw_reviewed else live_inspection(resume_reviewed=args.resume_reviewed) if args.live else offline_inspection()
        print(json.dumps(report, indent=2))
    except Exception as exc:
        # Never emit arbitrary provider messages or stack traces containing request context.
        print(json.dumps({"probe_failed": type(exc).__name__, "private_details": "redacted", "upstream_requests": ledger_count()}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
