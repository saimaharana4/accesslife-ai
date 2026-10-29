"""Choice-only projection; gameplay services enforce ownership and current-round delivery."""

from tasteduel.api.schemas import ArtworkPublic, ChoicePublic, EntityPublic
from tasteduel.domain.duel_pool import PresentedChoice
from tasteduel.domain.types import RankingSource


def pool_choice_public(choice: PresentedChoice, *, source: RankingSource) -> ChoicePublic:
    """No pool/answer/band/score/provider URL; future caller must authorize delivery.

    Existing project-owned SVG IDs are used independently of score/winner. No
    provider URL is promoted to a licensed asset by a boolean metadata flag.
    """
    entity = choice.entity
    return ChoicePublic(
        id=choice.id,
        entity=EntityPublic(
            id=entity.id,
            name=entity.name,
            type=entity.domain,
            source=source,
            artwork=ArtworkPublic(
                kind="owned_fallback", asset_id="afterlight" if entity.domain == "movie" else "velvet-static"
            ),
        ),
    )
