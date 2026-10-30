"""capability synthetic checks; intentionally independent of the old app/database fixtures."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("tasteduel_capability_spike", ROOT / "scripts/taste_duel_capability_spike.py")
spike = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spike)
FIXTURE = json.loads(Path(__file__).with_name("synthetic_recommend.json").read_text(encoding="utf-8"))


def test_five_disjoint_pairs_without_requiring_unlicensed_artwork():
    result = spike.summarize_ranking(FIXTURE, "movie", "synthetic-seed")
    assert result["eligible_unique"] == 10
    assert result["images"] == 0
    assert result["disjoint_extreme_pair_lower_bounds_by_raw_unit_epsilon"]["0.01"] == 5
    assert result["compact_affinities_nonincreasing"]
    serialized = json.dumps(result)
    assert "Synthetic Film" not in serialized and "synthetic-01" not in serialized


def test_ties_do_not_establish_five_winners():
    value = copy.deepcopy(FIXTURE)
    for row in value["results"]:
        row["affinity"] = 0.5
    assert spike.summarize_ranking(value, "movie", "seed")["disjoint_extreme_pair_lower_bounds_by_raw_unit_epsilon"]["0"] == 0


def test_extreme_pair_count_is_a_constructive_lower_bound_not_maximum_matching():
    value = copy.deepcopy(FIXTURE)
    value["results"] = value["results"][:4]
    for row, score in zip(value["results"], [0.0, 0.001, 0.002, 0.003]):
        row["affinity"] = score
    summary = spike.summarize_ranking(value, "movie", "seed")
    assert not summary["compact_affinities_nonincreasing"]
    assert summary["disjoint_extreme_pair_lower_bounds_by_raw_unit_epsilon"]["0.001"] == 1
    # (0,.002) and (.001,.003) are two valid edges. A low bound cannot reject coverage.
    assert 0.002 - 0.0 > 0.001 and 0.003 - 0.001 > 0.001


@pytest.mark.parametrize("target", ["movie", "artist"])
def test_explicit_raw_insights_request_subset(target):
    assert spike.insights_parameters("synthetic-seed", target) == {
        "filter.type": "urn:entity:" + target, "signal.interests.entities": "synthetic-seed",
        "take": 20, "feature.explainability": "true", "sort_by": "affinity",
    }
    with pytest.raises(ValueError):
        spike.insights_parameters("synthetic-seed", "book")
    with pytest.raises(ValueError):
        spike.insights_parameters("", target)


def test_raw_wire_score_provenance_and_conflicts():
    row = {"entity_id": "synthetic", "name": "Synthetic", "types": ["urn:entity:movie"],
           "query": {"affinity": 0.81, "explainability": {"warning": "Synthetic limited influence"}}}
    body = {"results": {"entities": [row]}, "query": {"explainability": {}}, "warnings": []}
    summary = spike.raw_wire_summary(body)
    assert summary["raw_query_affinity_count"] == 1
    assert summary["raw_top_affinity_count"] == summary["raw_affinity_field_conflicts"] == 0
    assert summary["raw_affinity_min"] == 0.81
    # Top-level warning count does not establish absence of nested explanation warnings.
    assert summary["raw_warning_count"] == 0 and row["query"]["explainability"]["warning"]
    row["affinity"] = 81
    assert spike.raw_wire_summary(body)["raw_affinity_field_conflicts"] == 1


@pytest.mark.parametrize("score", [None, True, float("nan"), float("inf"), "0.9"])
def test_nonfinite_missing_or_nonnumeric_affinity_is_ineligible(score):
    value = copy.deepcopy(FIXTURE)
    value["results"][0]["affinity"] = score
    assert spike.summarize_ranking(value, "movie", "seed")["eligible_unique"] == 9


def test_duplicates_seed_wrong_type_and_ambiguous_identity_cannot_fill_pool():
    value = copy.deepcopy(FIXTURE)
    value["results"][1]["entity_id"] = value["results"][0]["entity_id"]
    value["results"][2]["entity_id"] = "seed"
    value["results"][3]["type"] = "urn:entity:artist"
    value["results"][4].pop("name")
    summary = spike.summarize_ranking(value, "movie", "seed")
    assert summary["eligible_unique"] == 6
    assert summary["duplicate_or_seed"] == 2
    assert summary["wrong_type"] == summary["missing_identity"] == 1


def test_unknown_result_shape_fails_and_ambiguity_never_auto_selects():
    with pytest.raises(ValueError):
        spike.summarize_ranking({"results": {}}, "movie", "seed")
    assert spike.chosen_seed({"status": "needs_input", "results": FIXTURE["results"]}, "movie") is None


def test_provider_subtype_precedes_general_entity_type():
    value = copy.deepcopy(FIXTURE)
    for row in value["results"]:
        row["subtype"] = row["type"]
        row["type"] = "urn:entity"
    assert spike.summarize_ranking(value, "movie", "seed")["eligible_unique"] == 10
    assert spike.chosen_seed({"status": "ok", "results": [value["results"][0]]}, "movie") == "synthetic-01"


def test_types_array_and_matching_interpretation_survive_compact_metadata_loss():
    raw = {"entity_id": "synthetic-id", "name": "Synthetic Film", "types": ["urn:entity", "urn:entity:movie"]}
    assert spike.entity_type(raw) == "urn:entity:movie"
    compact = {"entity_id": "synthetic-id", "name": "Synthetic Film"}
    result = {"status": "ok", "results": [compact], "interpretation": {"entity": {"entityId": "synthetic-id", "type": "urn:entity:movie"}}}
    assert spike.chosen_seed(result, "movie") == "synthetic-id"
    result["interpretation"]["entity"]["entityId"] = "different-id"
    assert spike.chosen_seed(result, "movie") is None


def test_fetch_guard_caps_persisted_attempts_and_serializes_synthetic_network(tmp_path):
    # Execute the actual guard against fake fetch, stopping before harness imports.
    code = """
process.env.PROBE_ARTIFACTS=ARTIFACT_PATH;
process.env.PROBE_LIVE='1';
let active=0,maxActive=0,forwarded=0;
globalThis.fetch=async(input,options)=>{active++;forwarded++;maxActive=Math.max(maxActive,active);if(options.redirect!=='manual')throw Error('Redirect contract');await new Promise(resolve=>setTimeout(resolve,2));active--;return new Response(JSON.stringify({results:[]}),{status:200});};
""".replace("ARTIFACT_PATH", json.dumps(str(tmp_path).replace("\\", "/")))
    code += spike.RUNNER.split("const clientModule=")[0]
    code += """
const outputs=await Promise.allSettled(Array.from({length:13},()=>guardedFetch(new URL('https://hackathon.api.qloo.com/search'),{method:'GET'})));
let requestPostBlocked=false;try{await guardedFetch(new Request('https://hackathon.api.qloo.com/search',{method:'POST'}));}catch(error){requestPostBlocked=error.message==='PROBE_ENDPOINT_BLOCKED';}
let unsafeUrlsBlocked=0;for(const url of ['https://user:pass@hackathon.api.qloo.com/search','https://hackathon.api.qloo.com/not-allowlisted','https://api.qloo.com/search']){try{await guardedFetch(new URL(url));}catch(error){if(error.message==='PROBE_ENDPOINT_BLOCKED')unsafeUrlsBlocked++;}}
console.log(JSON.stringify({forwarded,maxActive,rejected:outputs.filter(x=>x.status==='rejected').length,ledgerLines:fs.readFileSync(ledger,'utf8').trim().split('\\n').length,requestPostBlocked,unsafeUrlsBlocked}));
"""
    completed = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, timeout=12)
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {"forwarded": 12, "maxActive": 1, "rejected": 1, "ledgerLines": 12, "requestPostBlocked": True, "unsafeUrlsBlocked": 3}


def test_offline_manifest_has_strict_actual_tool_limits_without_provider_calls():
    package = spike.ARTIFACTS / "harness/node_modules/@qloo/qloo-harness/package.json"
    if not package.exists():
        pytest.skip("Pinned private spike harness is not installed; never install or call a provider from tests")
    before = spike.ledger_count()
    summary = spike.offline_inspection()
    assert summary["upstream_requests"] == 0
    assert spike.ledger_count() == before
    manifest = json.loads((spike.ARTIFACTS / "offline-contract.json").read_text())
    tools = {tool["name"]: tool for tool in manifest["tools"]["tools"]}
    recommend = tools["qloo_recommend"]["inputSchema"]
    assert recommend["additionalProperties"] is False
    assert recommend["properties"]["limit"]["maximum"] == 20
    assert "filter.exists" not in recommend["properties"] and "sort_by" not in recommend["properties"]
    assert tools["qloo_rank"]["inputSchema"]["properties"]["options"]["maxItems"] == 10


@pytest.mark.parametrize("kind", ["valid", "malformed", "rate_limit", "auth", "timeout"])
def test_pinned_http_contract_auth_deadline_and_one_attempt_are_synthetic(kind):
    chunk = spike.ARTIFACTS / "harness/node_modules/@qloo/qloo-harness/dist/chunks/chunk-ESNY4EJL.js"
    if not chunk.exists():
        pytest.skip("Pinned private spike harness is not installed")
    code = """
const {QlooClient}=await import(CHUNK);
globalThis.fetch=()=>{throw new Error('Unexpected real network forbidden');};
let calls=0;
const fakeFetch=async(url,options)=>{
 calls++;
 if(url.origin!=='https://hackathon.api.qloo.com'||url.pathname!=='/search'||url.searchParams.get('query')!=='Synthetic Seed'||options.method!=='GET'||options.headers['X-Api-Key']!=='synthetic-contract-key')throw new Error('Contract mismatch');
 if(KIND==='timeout'){await new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true}));}
 if(KIND==='malformed')return new Response('not-json',{status:200});
 return new Response(JSON.stringify(KIND==='valid'?{results:[]}:{error:'synthetic-only'}),{status:KIND==='rate_limit'?429:KIND==='auth'?401:200,headers:{'content-type':'application/json','retry-after':'0'}});
};
const client=new QlooClient({apiKey:'synthetic-contract-key',baseUrl:'https://hackathon.api.qloo.com',allowCustomBaseUrl:true,fetch:fakeFetch,maxAttempts:1,timeoutMs:15});
const keepAlive=setTimeout(()=>{},1000);
try {await client.searchEntities({query:'Synthetic Seed',types:'urn:entity:artist',take:5}); console.log(JSON.stringify({calls,ok:true}));}
catch(error){console.log(JSON.stringify({calls,ok:false,code:error.code,retryable:error.retryable}));}
finally{clearTimeout(keepAlive);}
""".replace("CHUNK", json.dumps(chunk.as_uri())).replace("KIND", json.dumps(kind))
    completed = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, timeout=8)
    assert completed.returncode == 0, "Synthetic Node contract process failed; no untrusted stderr is printed"
    result = json.loads(completed.stdout)
    assert result["calls"] == 1
    assert result["ok"] is (kind == "valid")
    if kind == "rate_limit":
        assert result["retryable"] is True
    elif kind == "auth":
        assert result["retryable"] is False
    elif kind == "timeout":
        assert result["code"] == "QLOO_TIMEOUT"
