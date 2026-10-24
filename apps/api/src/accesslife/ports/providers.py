from typing import Protocol
from accesslife.domain.models import Explanation, IntentResult, Place


class ProviderError(Exception):
    def __init__(self, code: str, retryable: bool = False):
        self.code, self.retryable = code, retryable
        super().__init__(code)


class GenerationProvider(Protocol):
    async def generate(self, prompt: str, schema: type[Explanation] | type[IntentResult]): ...


class TasteProvider(Protocol):
    async def rank_candidates(self, places: list[Place], interests: list[str]) -> dict: ...


class TaskDispatcher(Protocol):
    def enqueue(self, run_id: str) -> None: ...


class PlacesProvider(Protocol):
    def search(self, city_id: str) -> list[Place]: ...


class AccessEvidenceProvider(Protocol):
    def lookup(self, evidence_ids: list[str]) -> dict: ...


class WeatherProvider(Protocol):
    async def forecast(self, city_id: str, date: str) -> dict: ...


class TransitProvider(Protocol):
    async def capabilities(self, city_id: str) -> dict: ...


class KnowledgeRetriever(Protocol):
    def retrieve(self, query: str, city_id: str) -> dict: ...
