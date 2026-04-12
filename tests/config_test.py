"""Tests for agent/config.py — user data directory resolution and init."""

from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import agent.config as config_module
from agent.config import (
    _APP_NAME,
    data_dir,
    init_data_dir,
    logs_dir,
    memory_dir,
    prompts_dir,
    default_prompt_path,
)


def _tmp() -> Path:
    return Path(tempfile.mkdtemp())


def _cleanup(p: Path) -> None:
    shutil.rmtree(str(p), ignore_errors=True)


# ---------------------------------------------------------------------------
# data_dir() resolution
# ---------------------------------------------------------------------------

def test_data_dir_returns_path_containing_app_name():
    """data_dir() should return a path that contains the app name."""
    result = data_dir()
    assert _APP_NAME in str(result)
    print("PASS: data_dir contains app name")


def test_data_dir_creates_directory():
    """data_dir() must create the directory if it doesn't exist."""
    result = data_dir()
    assert result.exists() and result.is_dir()
    print("PASS: data_dir creates directory")


def test_data_dir_windows_uses_appdata():
    """On Windows, data_dir should be under APPDATA."""
    tmp = _tmp()
    try:
        with patch("platform.system", return_value="Windows"):
            with patch.dict("os.environ", {"APPDATA": str(tmp)}, clear=False):
                result = config_module.data_dir()
        assert str(tmp) in str(result)
    finally:
        _cleanup(tmp)
    print("PASS: data_dir Windows uses APPDATA")


def test_data_dir_linux_uses_xdg():
    """On Linux, data_dir should respect XDG_DATA_HOME."""
    tmp = _tmp()
    try:
        with patch("platform.system", return_value="Linux"):
            with patch.dict("os.environ", {"XDG_DATA_HOME": str(tmp)}, clear=False):
                result = config_module.data_dir()
        assert str(tmp) in str(result)
    finally:
        _cleanup(tmp)
    print("PASS: data_dir Linux uses XDG_DATA_HOME")


def test_data_dir_macos_path():
    """On macOS, data_dir should contain 'Application Support'."""
    tmp = _tmp()
    try:
        with patch("platform.system", return_value="Darwin"):
            with patch("pathlib.Path.home", return_value=tmp):
                result = config_module.data_dir()
        assert "Application Support" in str(result)
    finally:
        _cleanup(tmp)
    print("PASS: data_dir macOS uses ~/Library/Application Support")


# ---------------------------------------------------------------------------
# Sub-directory helpers
# ---------------------------------------------------------------------------

def test_subdirectory_helpers_return_existing_dirs():
    """logs_dir, memory_dir, prompts_dir must all return existing directories."""
    for fn, name in [(logs_dir, "logs"), (memory_dir, "memory"), (prompts_dir, "prompts")]:
        result = fn()
        assert result.exists() and result.is_dir(), f"{name} dir should exist"
    print("PASS: subdirectory helpers all return existing directories")


# ---------------------------------------------------------------------------
# init_data_dir()
# ---------------------------------------------------------------------------

def test_init_data_dir_idempotent():
    """Calling init_data_dir() twice must not raise or overwrite files."""
    first = init_data_dir()
    second = init_data_dir()
    assert first == second
    print("PASS: init_data_dir is idempotent")


def test_init_data_dir_creates_all_subdirs():
    """init_data_dir() must ensure logs/, memory/, and prompts/ all exist."""
    root = init_data_dir()
    for sub in ("logs", "memory", "prompts"):
        assert (root / sub).is_dir(), f"{sub}/ should exist after init"
    print("PASS: init_data_dir creates all required subdirectories")


# ---------------------------------------------------------------------------
# default_prompt_path()
# ---------------------------------------------------------------------------

def test_default_prompt_path_returns_file():
    """default_prompt_path() should return an existing non-empty .md file."""
    path = default_prompt_path()
    assert path.exists() and path.suffix == ".md"
    assert len(path.read_text(encoding="utf-8")) > 0
    print("PASS: default_prompt_path returns existing non-empty .md file")


def test_default_prompt_path_copies_bundled_when_missing():
    """When user-dir prompt is absent, bundled source should be copied."""
    tmp = _tmp()
    try:
        fake_prompts = tmp / "prompts"
        fake_prompts.mkdir()
        with patch.object(config_module, "prompts_dir", return_value=fake_prompts):
            result = config_module.default_prompt_path()
        assert result.exists()
        assert result.read_text(encoding="utf-8").strip()
    finally:
        _cleanup(tmp)
    print("PASS: default_prompt_path copies bundled prompt when missing")


# ---------------------------------------------------------------------------
# HephaestusAgent uses config paths
# ---------------------------------------------------------------------------

def test_agent_uses_config_paths_by_default():
    """HephaestusAgent() with no args should use config-resolved paths."""
    tmp = _tmp()
    try:
        fake_memory = tmp / "memory"
        fake_logs = tmp / "logs"
        fake_prompts = tmp / "prompts"
        for d in (fake_memory, fake_logs, fake_prompts):
            d.mkdir()

        prompt = fake_prompts / "dev_agent.md"
        prompt.write_text("You are Hephaestus.", encoding="utf-8")

        with patch.object(config_module, "memory_dir", return_value=fake_memory):
            with patch.object(config_module, "logs_dir", return_value=fake_logs):
                with patch.object(config_module, "default_prompt_path", return_value=prompt):
                    from agent.agent import HephaestusAgent
                    agent = HephaestusAgent()

        assert str(fake_logs) in str(agent.log_path)
        assert str(fake_memory) in str(agent.repo_scanner.index_path)
        assert agent.instructions == "You are Hephaestus."
    finally:
        _cleanup(tmp)
    print("PASS: HephaestusAgent uses config-resolved paths by default")


# ---------------------------------------------------------------------------
# CLI init command
# ---------------------------------------------------------------------------

def test_cli_init_command_prints_data_dir():
    """hep init should print the data directory path."""
    tmp = _tmp()
    try:
        captured: list[str] = []

        def capturing_print(*args, **kwargs):
            captured.append(" ".join(str(a) for a in args))

        with patch("sys.argv", ["hep", "init"]):
            with patch.object(config_module, "init_data_dir", return_value=tmp):
                with patch("builtins.print", capturing_print):
                    import main as main_module
                    importlib.reload(main_module)
                    main_module.main()

        assert any(str(tmp) in line for line in captured), (
            f"Expected data dir path in output, got: {captured}"
        )
    finally:
        _cleanup(tmp)
    print("PASS: CLI init command prints data directory paths")


if __name__ == "__main__":
    test_data_dir_returns_path_containing_app_name()
    test_data_dir_creates_directory()
    test_data_dir_windows_uses_appdata()
    test_data_dir_linux_uses_xdg()
    test_data_dir_macos_path()
    test_subdirectory_helpers_return_existing_dirs()
    test_init_data_dir_idempotent()
    test_init_data_dir_creates_all_subdirs()
    test_default_prompt_path_returns_file()
    test_default_prompt_path_copies_bundled_when_missing()
    test_agent_uses_config_paths_by_default()
    test_cli_init_command_prints_data_dir()
    print("\n=== config tests PASSED ===")
