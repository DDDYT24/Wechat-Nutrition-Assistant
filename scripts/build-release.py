"""Build a complete project ZIP, Python packages and SHA-256 checksums."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def check_paths(names: list[str]) -> None:
    forbidden_parts = {".git", ".venv", "node_modules", ".data", "__pycache__"}
    forbidden_names = {".env", "AGENTS.md", "TODO.md", "V1.2_PLAN.md"}
    for name in names:
        path = PurePosixPath(name)
        if forbidden_parts.intersection(path.parts) or path.name in forbidden_names:
            raise ValueError(f"Local-only path found in package: {name}")
        if path.suffix in {".db", ".sqlite", ".sqlite3", ".log", ".jsonl", ".pem", ".key"}:
            raise ValueError(f"Runtime or secret file found in package: {name}")


def main() -> None:
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--"], cwd=ROOT, check=True)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    subprocess.run(["uv", "build", "--out-dir", str(output)], cwd=ROOT, check=True)
    prefix = f"Wechat-Nutrition-Assistant-v{version}"
    bundle = output / f"{prefix}.zip"
    subprocess.run(
        ["git", "archive", "--format=zip", f"--prefix={prefix}/", "-o", str(bundle), "HEAD"],
        cwd=ROOT,
        check=True,
    )
    wheel = output / f"wechat_nutrition_bot-{version}-py3-none-any.whl"
    source = output / f"wechat_nutrition_bot-{version}.tar.gz"
    for archive in (bundle, wheel):
        with zipfile.ZipFile(archive) as package:
            check_paths(package.namelist())
            if package.testzip() is not None:
                raise ValueError(f"Corrupt ZIP archive: {archive.name}")
            if archive == wheel:
                assert "wechat_nutrition_bot/data/foods_v2.json" in package.namelist()
    with tarfile.open(source) as package:
        check_paths(package.getnames())
    checksums = "".join(
        f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}\n"
        for file in (bundle, wheel, source)
    )
    (output / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
    print(checksums, end="")
    print(f"Release artifacts ready in {output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
