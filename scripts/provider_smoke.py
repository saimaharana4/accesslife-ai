"""One small model request; prints outcome, never credentials."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))
from accesslife.adapters.generation import ModelGeneration  # noqa: E402
from accesslife.domain.models import Explanation  # noqa: E402
from accesslife.config import settings  # noqa: E402


async def main():
    try:
        result = await asyncio.wait_for(
            ModelGeneration("vertex_ai").generate(
                "Return one sentence saying this is a provisional outing. Include no evidence IDs.",
                Explanation,
            ),
            25,
        )
        print(
            {
                "provider": "vertex_ai",
                "model": settings().vertex_ai_model,
                "status": "passed",
                "structured_output": bool(result.summary),
            }
        )
    except Exception as exc:
        print(
            {
                "provider": "vertex_ai",
                "model": settings().vertex_ai_model,
                "status": "unavailable",
                "error": getattr(exc, "code", type(exc).__name__),
                "upstream_code": getattr(exc.__cause__, "code", None),
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
