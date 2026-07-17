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
        reload_excludes=[".venv/**", ".git/**", "__pycache__/**", "*.pyc", ".data/**"]
        if settings.app_env == "development"
        else None,
        access_log=False,
    )


if __name__ == "__main__":
    run()
