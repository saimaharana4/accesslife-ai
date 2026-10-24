"""Live coverage check. Never prints payloads, credentials or cultural identifiers."""

import asyncio
from accesslife.adapters.catalogue import CITIES, PLACES
from accesslife.composition import taste_provider


async def main():
    provider = await asyncio.to_thread(taste_provider)
    failures = []
    for city in CITIES:
        places = [p for p in PLACES if p.city_id == city.id]
        try:
            result = await provider.rank_candidates(places, ["art", "history"])
            assert result["provider"] == "qloo" and result["live"] and result["scores"]
            assert set(result["order"]) == {p.id for p in places}
            print(
                {
                    "city": city.id,
                    "live_qloo": "passed",
                    "candidates": len(places),
                    "scored": len(result["scores"]),
                    "unmapped": len(result["unmapped"]),
                },
                flush=True,
            )
        except Exception as exc:
            failures.append(city.id)
            print(
                {"city": city.id, "live_qloo": "failed", "code": getattr(exc, "code", type(exc).__name__)},
                flush=True,
            )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
