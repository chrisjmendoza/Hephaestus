"""Smoke-style multi-language scan test for Hephaestus v0.5.1."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    """Scan repository and verify multi-language fields are present and populated."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    index_path = project_root / "memory" / "repo_index.json"
    if index_path.exists():
        index_path.unlink()

    agent = HephaestusAgent()
    index = agent.scan_repo(str(project_root))

    assert index_path.exists(), "Repository index file was not created"

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    language_keys = [
        "python_files",
        "kotlin_files",
        "java_files",
        "xml_files",
        "js_files",
        "gradle_files",
        "csharp_files",
        "cpp_files",
    ]
    for key in language_keys:
        assert key in payload, f"Missing language index field: {key}"

    has_any_files = any(len(payload.get(key, [])) > 0 for key in language_keys)
    assert has_any_files, "No files detected in any language category"
    assert payload.get("language_counts") is not None, "Missing language_counts summary"
    assert index.get("language_counts") is not None, "Missing language_counts in scan result"

    print("PASS")
    print("Repository multi-language scan test passed")


if __name__ == "__main__":
    main()
