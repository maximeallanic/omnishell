#!/usr/bin/env python3
"""No source file over 500 lines: a file that grows past it holds more than one concern and should be split."""
import subprocess
import sys
from pathlib import Path

LIMIT = 500
TEXT = {".py", ".js", ".sh", ".css", ".xml", ".json", ".md", ".yml", ".html", ".service", ".desktop", ".svg"}
ROOT = Path(__file__).resolve().parent.parent


def files():
    try:  # the files git would publish; outside a checkout, everything but caches
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard"], check=True,
                             capture_output=True, text=True).stdout.split("\n")
        return [ROOT / f for f in out if f]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts]


def main():
    too_long = []
    for path in files():
        if path.suffix in TEXT or (path.is_file() and path.read_bytes()[:2] == b"#!"):
            n = len(path.read_text(encoding="utf-8").splitlines())
            if n > LIMIT:
                too_long.append(f"{path.relative_to(ROOT)}: {n} lines")
    for line in too_long:
        print(f"over {LIMIT} lines: {line}")
    if not too_long:
        print(f"file sizes: every file is at most {LIMIT} lines")
    return 1 if too_long else 0


if __name__ == "__main__":
    sys.exit(main())
