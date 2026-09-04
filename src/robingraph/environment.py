"""Local environment-file loading for RobinGraph command entry points."""

from __future__ import annotations

from collections.abc import MutableMapping
import os
from pathlib import Path
import re


_ENVIRONMENT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_local_environment(
    path: Path | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> bool:
    """Load a root ``.env`` file without replacing explicit shell settings.

    The loader deliberately supports only the portable ``KEY=VALUE`` form;
    shell interpolation and command substitution are never evaluated.
    """

    environment_path = path or Path.cwd() / ".env"
    if not environment_path.is_file():
        return False

    target = os.environ if environ is None else environ
    for line_number, raw_line in enumerate(environment_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"{environment_path}:{line_number} must use KEY=VALUE format")
        key, value = line.split("=", 1)
        key = key.strip()
        if not _ENVIRONMENT_KEY.fullmatch(key):
            raise ValueError(f"{environment_path}:{line_number} has an invalid environment variable name")
        target.setdefault(key, value.strip())
    return True
