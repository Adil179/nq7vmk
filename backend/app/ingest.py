from __future__ import annotations

import asyncio

from .store import build_cache


async def main() -> None:
    payload = await build_cache()
    meta = payload["meta"]
    print(
        f"Cached {meta['actualPoints']} actuals, "
        f"{meta['forecastPoints']} forecast rows, "
        f"{meta['alignedHours']} aligned hours."
    )


if __name__ == "__main__":
    asyncio.run(main())
