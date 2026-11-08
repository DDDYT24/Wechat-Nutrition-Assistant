from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def _available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_healthy(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"nutrition-bot exited during startup:\n{output}")
        try:
            response = httpx.get(f"{base_url}/health", timeout=0.5)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise AssertionError("nutrition-bot did not become healthy within 15 seconds")


def _signature(token: str, timestamp: str, nonce: str) -> str:
    value = "".join(sorted([token, timestamp, nonce]))
    return hashlib.sha1(value.encode()).hexdigest()


def test_real_server_accepts_signed_wechat_message(tmp_path: Path):
    project_root = Path(__file__).parents[1]
    port = _available_port()
    base_url = f"http://127.0.0.1:{port}"
    token = "process-e2e-wechat-token"
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "test",
            "APP_HOST": "127.0.0.1",
            "APP_PORT": str(port),
            "DATABASE_PATH": str(tmp_path / "process-e2e.sqlite3"),
            "FOOD_CATALOG_PATH": str(project_root / "data" / "foods_v1.json"),
            "USER_HMAC_SECRET": "process-e2e-secret-that-is-long-enough",
            "WECHAT_TOKEN": token,
            "DEEPSEEK_API_KEY": "",
            "INTERNAL_CHAT_ENABLED": "false",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "wechat_nutrition_bot.main"],
        cwd=project_root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )

    try:
        _wait_until_healthy(base_url, process)
        timestamp = "1784304000"
        nonce = "process-e2e"
        params = {
            "signature": _signature(token, timestamp, nonce),
            "timestamp": timestamp,
            "nonce": nonce,
        }
        verification = httpx.get(
            f"{base_url}/wechat/callback",
            params={**params, "echostr": "wechat-ready"},
            timeout=3,
        )
        message = """<xml>
<ToUserName>test-account</ToUserName>
<FromUserName>process-e2e-user</FromUserName>
<CreateTime>1784304000</CreateTime>
<MsgType>text</MsgType>
<Content>同意并开始</Content>
<MsgId>process-e2e-message-1</MsgId>
</xml>"""
        response = httpx.post(
            f"{base_url}/wechat/callback",
            params=params,
            content=message.encode("utf-8"),
            headers={"content-type": "application/xml"},
            timeout=5,
        )

        assert verification.status_code == 200
        assert verification.text == "wechat-ready"
        assert response.status_code == 200
        assert "请按任意顺序" in response.text
        assert httpx.post(
            f"{base_url}/internal/chat",
            json={"user_id": "process-e2e-user", "text": "帮助"},
            timeout=3,
        ).status_code == 404
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
