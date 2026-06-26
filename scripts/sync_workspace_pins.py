"""Pin workspace packages to the core promptuna version for PyPI metadata."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED_PACKAGES = ("cli", "server")
PIN_PATTERN = re.compile(r'"promptuna==[^"]+"')


def main() -> None:
    """Write ``promptuna==<core version>`` pins into workspace package metadata."""
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    pin = f'"promptuna=={version}"'

    for package in PINNED_PACKAGES:
        path = ROOT / package / "pyproject.toml"
        text = path.read_text()
        updated, count = PIN_PATTERN.subn(pin, text)
        if count != 1:
            raise SystemExit(f"expected one promptuna pin in {path}, found {count}")
        path.write_text(updated)


if __name__ == "__main__":
    main()
