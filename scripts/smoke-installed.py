"""Verify an installed package and its HTTP callback without a source checkout."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="nutrition-wheel-") as directory:
        original = Path.cwd()
        os.chdir(directory)
        process = None
        log_file = None
        try:
            from wechat_nutrition_bot.catalog import FoodCatalog
            from wechat_nutrition_bot.config import Settings

            catalog = FoodCatalog(Settings(_env_file=None).food_catalog_path)
            assert catalog.version == "2.0-cn6"
            assert len(catalog.foods) == 1623
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            token = "package-smoke-wechat-token"
            environment = os.environ.copy()
            environment.pop("FOOD_CATALOG_PATH", None)
            environment.update(
                APP_ENV="test",
                APP_HOST="127.0.0.1",
                APP_PORT=str(port),
                DATABASE_PATH=str(Path(directory) / "test.sqlite3"),
                USER_HMAC_SECRET="package-smoke-secret-with-at-least-32-characters",
                WECHAT_TOKEN=token,
                DEEPSEEK_API_KEY="",
                INTERNAL_CHAT_ENABLED="false",
            )
            log_path = Path(directory) / "server.log"
            log_file = log_path.open("w", encoding="utf-8")
            process = subprocess.Popen(
                [sys.executable, "-m", "wechat_nutrition_bot.main"],
                env=environment,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(f"{base}/health", timeout=1) as response:
                        health = json.load(response)
                    break
                except urllib.error.URLError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        details = log_path.read_text(encoding="utf-8", errors="replace")
                        raise RuntimeError(
                            f"Installed package did not become healthy:\n{details}"
                        ) from None
                    time.sleep(0.1)
            assert health["version"] == "1.2.0"
            assert health["internal_chat_enabled"] is False
            timestamp, nonce = "1784304000", "package-smoke"
            signed_value = "".join(sorted([token, timestamp, nonce])).encode()
            signature = hashlib.sha1(signed_value).hexdigest()
            query = urllib.parse.urlencode(
                {"signature": signature, "timestamp": timestamp, "nonce": nonce}
            )
            body = (
                "<xml><ToUserName>test-account</ToUserName>"
                "<FromUserName>package-smoke-user</FromUserName>"
                "<CreateTime>1784304000</CreateTime><MsgType>text</MsgType>"
                "<Content>同意并开始</Content><MsgId>package-smoke-1</MsgId></xml>"
            ).encode()
            request = urllib.request.Request(
                f"{base}/wechat/callback?{query}", body, {"Content-Type": "application/xml"}
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert "请按任意顺序" in response.read().decode()
            print("Installed package: catalogue, health and signed XML callback passed.")
        finally:
            if process is not None:
                if os.name == "nt" and process.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if log_file is not None:
                log_file.close()
            os.chdir(original)


if __name__ == "__main__":
    main()
