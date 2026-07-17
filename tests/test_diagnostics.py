from __future__ import annotations

import json
import os
import subprocess
import sys


def test_diagnostics_cli_handles_designated_wechat_id(settings):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "wechat_nutrition_bot.diagnostics",
            "--alias",
            "your-test-wechat-id",
            "--limit",
            "3",
        ],
        capture_output=True,
        check=True,
        env={
            **os.environ,
            "DATABASE_PATH": str(settings.database_path),
            "USER_HMAC_SECRET": settings.user_hmac_secret,
        },
    )
    payload = json.loads(result.stdout.decode("utf-8"))
    assert payload["alias"] == "your-test-wechat-id"
    assert payload["bound"] is False
