"""Pytest plugin to collect main()-based test modules alongside native test_* functions."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_HAS_TEST_FN = re.compile(r"^def test_", re.MULTILINE)
_HAS_MAIN_FN = re.compile(r"^def main\b", re.MULTILINE)


class _MainTestItem(pytest.Item):
    """A single pytest item that calls a module's main() function."""

    def __init__(self, *, module, **kwargs):
        super().__init__(**kwargs)
        self._module = module

    def runtest(self) -> None:
        self._module.main()

    def repr_failure(self, excinfo):
        return str(excinfo.value)

    def reportinfo(self):
        return self.path, None, self.name


class _MainBasedFile(pytest.File):
    """Collector for test files that expose a main() function instead of test_* functions."""

    def collect(self):
        spec = importlib.util.spec_from_file_location(self.path.stem, str(self.path))
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(self.path.stem, module)
        spec.loader.exec_module(module)
        if callable(getattr(module, "main", None)):
            yield _MainTestItem.from_parent(self, name=self.path.stem, module=module)


def pytest_collect_file(parent, file_path):
    """Hook: wrap main()-only test files so pytest can discover and run them."""
    if file_path.suffix != ".py" or not file_path.name.endswith("_test.py"):
        return None
    try:
        src = file_path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Files with test_* functions are collected natively by pytest.
    if _HAS_TEST_FN.search(src):
        return None
    if _HAS_MAIN_FN.search(src):
        return _MainBasedFile.from_parent(parent, path=file_path)
    return None
