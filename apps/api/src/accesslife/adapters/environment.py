import httpx
from accesslife.config import settings
from accesslife.adapters.catalogue import CITY_BY_ID
from accesslife.application.limits import provider_call


@provider_call
async def weather(city_id, date):
    if not settings().live_providers:
        return {"status": "disabled", "provider": "Open-Meteo"}
    city = CITY_BY_ID[city_id]
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": city.latitude,
                    "longitude": city.longitude,
                    "daily": "temperature_2m_max,precipitation_probability_max",
                    "timezone": city.time_zone,
                    "forecast_days": 16,
                },
            )
            response.raise_for_status()
            data = response.json()["daily"]
            if date not in data["time"]:
                return {"status": "outside_forecast_horizon", "provider": "Open-Meteo"}
            index = data["time"].index(date)
            return {
                "status": "live",
                "provider": "Open-Meteo",
                "temperature_max_c": data["temperature_2m_max"][index],
                "rain_probability": data["precipitation_probability_max"][index],
                "source_url": "https://open-meteo.com/",
                "date": date,
            }
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError):
        return {"status": "unavailable", "provider": "Open-Meteo"}


@provider_call
async def transit(city_id):
    cfg = settings()
    sources = {
        "london": ("TfL", "https://api.tfl.gov.uk/Line/Mode/tube/Status", cfg.tfl_api_key),
        "new-york": ("MTA", "https://www.mta.info/developers", cfg.mta_bus_api_key),
        "paris": ("IDFM", "https://prim.iledefrance-mobilites.fr/", cfg.idfm_api_key),
        "berlin": ("VBB", "https://unternehmen.vbb.de/digitale-services/", cfg.vbb_api_key),
        "chicago": ("CTA", "https://www.transitchicago.com/developers/", cfg.cta_api_key),
    }
    provider, source, key = sources[city_id]
    result = {
        "provider": provider,
        "status": "routing_unverified",
        "source_url": source,
        "configured": bool(key),
        "message": "Door-to-door route, boarding and vehicle access have not been verified.",
    }
    if city_id == "london" and cfg.live_providers:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(source, params={"app_key": key} if key else {})
                response.raise_for_status()
                result["feed_status"] = "live"
                result["lines_reported"] = len(response.json())
        except (httpx.HTTPError, ValueError):
            result["feed_status"] = "unavailable"
    return result


@provider_call
async def discover_osm(city_id):
    """Bounded optional discovery; OSM tags never become blanket access confirmation."""
    city = CITY_BY_ID[city_id]
    query = f"[out:json][timeout:6];nwr(around:1500,{city.latitude},{city.longitude})[tourism=museum];out center 12;"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data={"data": query})
            response.raise_for_status()
            records = []
            for item in response.json().get("elements", [])[:12]:
                tags = item.get("tags", {})
                location = item.get("center", item)
                if not tags.get("name") or "lat" not in location or "lon" not in location:
                    continue
                records.append(
                    {
                        "id": f"osm-{item['type']}-{item['id']}",
                        "city_id": city_id,
                        "name": tags["name"],
                        "category": "museum",
                        "latitude": location["lat"],
                        "longitude": location["lon"],
                        "interests": ["museum"],
                        "description": "Community-mapped discovery preview. Access features have not been reviewed.",
                        "facts": [
                            {
                                "feature": key,
                                "status": "unknown",
                                "evidence_ids": [],
                                "conflict": False,
                                "stale": False,
                            }
                            for key in ["step_free_entrance", "accessible_toilet", "lift"]
                        ],
                        "source_url": f"https://www.openstreetmap.org/{item['type']}/{item['id']}",
                    }
                )
            return {
                "status": "live",
                "places": records,
                "attribution": "© OpenStreetMap contributors, ODbL",
                "source_url": "https://www.openstreetmap.org/copyright",
            }
    except (httpx.HTTPError, ValueError):
        return {"status": "unavailable", "places": []}
