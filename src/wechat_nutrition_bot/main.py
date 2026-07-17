from __future__ import annotations

import uvicorn

from .config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "wechat_nutrition_bot.wechat:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        access_log=False,
    )


if __name__ == "__main__":
    run()
