"""Provider composition root. Constructors never perform network or database IO."""

from datetime import datetime, timezone
from accesslife.config import settings
from accesslife.adapters.catalogue import PLACES, EVIDENCE
from accesslife.adapters.taste import DevelopmentTaste, QlooTaste
from accesslife.adapters.environment import weather, transit
from accesslife.adapters.retrieval import retrieve
from accesslife.adapters.generation import generate
from accesslife.ports.providers import TasteProvider, ProviderError
from accesslife.adapters.secrets import credential


class CataloguePlaces:
    def search(self, city_id):
        records = [p.model_copy(deep=True) for p in PLACES if p.city_id == city_id]
        for place in records:
            for fact in place.facts:
                fact.stale = fact.stale or datetime.now(timezone.utc).date().isoformat() > "2026-11-23"
        return records


class CatalogueEvidence:
    def lookup(self, evidence_ids):
        return {key: EVIDENCE[key] for key in set(evidence_ids) if key in EVIDENCE}


class ForecastWeather:
    async def forecast(self, city_id, date):
        try:
            return await weather(city_id, date)
        except ProviderError:
            return {"status": "unavailable", "provider": "Open-Meteo"}


class CityTransit:
    async def capabilities(self, city_id):
        try:
            return await transit(city_id)
        except ProviderError:
            return {
                "status": "routing_unverified",
                "message": "Transport provider is unavailable; every leg needs verification.",
            }


class MiniLMRetriever:
    def retrieve(self, query, city_id):
        return retrieve(query, city_id)


def taste_provider() -> TasteProvider:
    cfg = settings()
    factories = {
        "development": DevelopmentTaste,
        "qloo": lambda: QlooTaste(credential("qloo_api_key"), cfg.qloo_base_url),
    }
    if cfg.taste_provider not in factories:
        raise ValueError("Unknown taste provider")
    return factories[cfg.taste_provider]()


places_provider = CataloguePlaces()
evidence_provider = CatalogueEvidence()
weather_provider = ForecastWeather()
transit_provider = CityTransit()
knowledge_retriever = MiniLMRetriever()
generate_structured = generate
development_taste_provider = DevelopmentTaste
