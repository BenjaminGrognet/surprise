"""Loads .env at the project root into the environment, once, before any CLI entry point runs.

No dependency on python-dotenv: the file only ever holds simple KEY=VALUE lines here, and every
existing entry point already reads its config straight from os.environ.
"""

import os
from pathlib import Path


def _load_dotenv() -> None:
    for parent in Path(__file__).resolve().parents:
        env_path = parent / ".env"
        if env_path.is_file():
            break
    else:
        return
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    for key, value in values.items():
        os.environ.setdefault(key, value)


_load_dotenv()
