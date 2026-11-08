"""Mostra uma busca real sem cadastrar ou contatar prestadores."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.schemas.common import ProviderCategory, mask_phone  # noqa: E402
from app.services.provider_browser import AgentBrowserAdapter  # noqa: E402
from app.services.provider_collector import reserve_browser_search  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--category", choices=[c.value for c in ProviderCategory], default="plumber"
    )
    parser.add_argument("--region", required=True)
    parser.add_argument("--limit", type=int, choices=range(1, 21), default=5)
    args = parser.parse_args()
    with SessionLocal() as db:
        reserve_browser_search(db, str(uuid4()), settings.max_browser_searches)
    source = AgentBrowserAdapter(
        settings.agent_browser_command,
        settings.browser_timeout_seconds,
        settings.agent_browser_executable_path,
    )
    results = await source.search(ProviderCategory(args.category), args.region, args.limit)
    print(
        json.dumps(
            [
                {
                    "id": p.place_id,
                    "name": p.name,
                    "region": p.region,
                    "rating": p.rating,
                    "masked_phone": mask_phone(p.phone),
                    "source": p.source,
                    "url": p.source_url,
                }
                for p in results
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
