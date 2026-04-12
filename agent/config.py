"""User-scoped configuration and data directory resolution for Hephaestus.

On all platforms Hephaestus stores its runtime state (logs, memory, cached
indices, and the agent prompt) in a per-user directory so that the tool works
correctly regardless of the current working directory:

  Windows : %APPDATA%\\Hephaestus
  macOS   : ~/Library/Application Support/Hephaestus
  Linux   : ~/.local/share/Hephaestus  (or $XDG_DATA_HOME/Hephaestus)

The ``data_dir()`` function returns this path and creates it on first access.

Sub-directories
---------------
- ``logs/``     – agent runtime logs
- ``memory/``   – repo indices, embeddings, task reports, per-repo history
- ``prompts/``  – agent operating instructions (copied from package on init)
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


_APP_NAME = "Hephaestus"


def data_dir() -> Path:
    """Return the platform-specific user data directory, creating it if needed."""
    system = platform.system()

    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        # XDG Base Directory specification
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"

    app_dir = base / _APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def logs_dir() -> Path:
    """Return (and create) the logs sub-directory inside the data dir."""
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def memory_dir() -> Path:
    """Return (and create) the memory sub-directory inside the data dir."""
    d = data_dir() / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def prompts_dir() -> Path:
    """Return (and create) the prompts sub-directory inside the data dir."""
    d = data_dir() / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_prompt_path() -> Path:
    """Return the path to dev_agent.md in the user data dir.

    If the file does not yet exist, copy it from the package's bundled copy.
    Call ``init_data_dir()`` explicitly to do a full first-run setup.
    """
    dest = prompts_dir() / "dev_agent.md"
    if not dest.exists():
        _copy_bundled_prompt(dest)
    return dest


def init_data_dir() -> Path:
    """Scaffold the user data directory with all required sub-dirs and files.

    Safe to call multiple times — existing files are never overwritten.
    Returns the data directory path.
    """
    data = data_dir()
    logs_dir()
    memory_dir()
    prompts_dir()
    dest = prompts_dir() / "dev_agent.md"
    if not dest.exists():
        _copy_bundled_prompt(dest)
    return data


def _copy_bundled_prompt(dest: Path) -> None:
    """Copy dev_agent.md from the package source tree to dest.

    Looks for the file relative to this module's location so it works both
    when running from the source tree and when installed as a package.
    """
    # When installed as a package, prompts/ is a sibling of agent/
    candidates = [
        Path(__file__).resolve().parent.parent / "prompts" / "dev_agent.md",
    ]
    for src in candidates:
        if src.exists():
            shutil.copy2(src, dest)
            return
    # If not found (e.g. minimal install), write a minimal placeholder
    dest.write_text(
        "You are Hephaestus, an AI software engineering agent. "
        "Prefer minimal, safe, incremental changes.\n",
        encoding="utf-8",
    )
