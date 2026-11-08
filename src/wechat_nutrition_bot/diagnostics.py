from __future__ import annotations

import argparse
import json
import sys

from .config import get_settings
from .repository import Repository


def run() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Read private local chat diagnostics for an explicitly bound test account."
    )
    parser.add_argument(
        "--alias",
        default=settings.diagnostic_test_alias,
        help="Stable test-account WeChat ID (the option name is retained for compatibility).",
    )
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    repository = Repository(settings.database_path, settings.user_hmac_secret)
    result = {
        "alias": args.alias,
        "bound": repository.is_diagnostic_alias_bound(args.alias),
        "messages": repository.get_diagnostic_messages(args.alias, args.limit),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
