"""Verify synthetic saved game/challenge state through restarted Compose API."""

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


state_path = Path(os.environ["TASTEDUEL_PERSISTENCE_STATE_FILE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
origin = "http://127.0.0.1:13001"
api = "http://127.0.0.1:18005"


def request(method: str, path: str, *, body=None, cookie: str | None = None, key: str | None = None):
    headers = {"Accept": "application/json", "Origin": origin}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if cookie:
        headers["Cookie"] = f"tasteduel_session={cookie}"
    if key:
        headers["Idempotency-Key"] = key
    req = Request(api + path, data=data, headers=headers, method=method)
    with urlopen(req, timeout=8) as response:
        raw = response.read()
        return response.status, json.loads(raw) if raw else None, response.headers


status, result, _ = request(
    "GET", f"/v1/games/{state['base_game_id']}/results", cookie=state["creator_cookie"]
)
assert status == 200 and result["score"] == state["creator_score"]
status, invitation, _ = request("GET", f"/v1/challenges/{state['slug']}")
assert status == 200 and invitation["seed"]["name"] == state["seed_name"]
assert invitation["source"] == "fixture"
status, _, headers = request("POST", "/v1/sessions", body={})
assert status in {200, 201}
set_cookie = headers.get("Set-Cookie", "")
marker = "tasteduel_session="
assert marker in set_cookie
guest_cookie = set_cookie.split(marker, 1)[1].split(";", 1)[0]
status, replay, _ = request(
    "POST",
    f"/v1/challenges/{state['slug']}/plays",
    body={},
    cookie=guest_cookie,
    key="compose-persistence-fixed-replay-01",
)
assert status == 201 and replay["mode"] == "fixed"
choices = [choice["entity"]["name"] for choice in replay["current_round"]["choices"]]
assert choices == state["first_choices"]
assert state["provider_calls"] == 0
print("Compose persistence verified: creator result, public invitation, fixed first round; provider calls=0.")
