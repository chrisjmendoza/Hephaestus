"""Per-repository persistent memory for the Hephaestus agent."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class TaskRecord:
    """A single completed-task entry stored in memory."""

    task: str
    outcome: str                          # "success" | "failed" | "partial"
    date: str                             # ISO-8601 UTC
    files_changed: list[str] = field(default_factory=list)
    error: str = ""


class MemoryStore:
    """Persists per-repository task history under ``memory/repos/``.

    Each repository gets its own JSON file named after a filesystem-safe
    slug derived from the repo path or name.  This keeps histories isolated
    and prevents a single file from growing without bound.

    Typical layout::

        memory/
          repos/
            hephaestus.json
            owner_target-repo.json

    Usage::

        store = MemoryStore.for_repo(".")
        store.record("fix login bug", "success", files_changed=["auth.py"])
        context = store.context_summary(n=5)   # recent entries as a readable string
    """

    def __init__(self, store_path: Path) -> None:
        self._path = store_path
        self._records: list[TaskRecord] = []
        self._load()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def for_repo(
        cls,
        repo_path: str | Path = ".",
        memory_root: str | Path = "memory",
    ) -> "MemoryStore":
        """Return a MemoryStore scoped to *repo_path*.

        The slug is derived from the resolved directory name so that
        ``for_repo(".")`` and ``for_repo("/absolute/path/to/hephaestus")``
        produce the same file when run from the same directory.
        """
        slug = cls._slug(Path(repo_path).resolve().name)
        store_path = Path(memory_root) / "repos" / f"{slug}.json"
        return cls(store_path)

    @classmethod
    def _slug(cls, name: str) -> str:
        """Convert a repo name into a safe filename component."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9_-]", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug or "unknown"

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @property
    def records(self) -> list[TaskRecord]:
        """Return all stored task records (oldest first)."""
        return list(self._records)

    def recent(self, n: int = 10) -> list[TaskRecord]:
        """Return the *n* most recent records."""
        return self._records[-n:]

    def context_summary(self, n: int = 5) -> str:
        """Return a compact human-readable summary of recent tasks for LLM context.

        Returns an empty string when there are no records yet.
        """
        entries = self.recent(n)
        if not entries:
            return ""
        lines = ["Recent task history for this repository:"]
        for rec in entries:
            line = f"- [{rec.date[:10]}] {rec.outcome.upper()}: {rec.task}"
            if rec.files_changed:
                line += f" (changed: {', '.join(rec.files_changed[:3])})"
            if rec.error:
                line += f" | error: {rec.error}"
            lines.append(line)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(
        self,
        task: str,
        outcome: str,
        files_changed: list[str] | None = None,
        error: str = "",
    ) -> TaskRecord:
        """Append a task record and immediately persist to disk.

        Args:
            task: Natural-language description of the task.
            outcome: ``"success"``, ``"failed"``, or ``"partial"``.
            files_changed: Files written or committed during the task.
            error: Error message if the task failed.

        Returns:
            The newly created :class:`TaskRecord`.
        """
        rec = TaskRecord(
            task=task,
            outcome=outcome,
            date=datetime.now(tz=timezone.utc).isoformat(),
            files_changed=files_changed or [],
            error=error,
        )
        self._records.append(rec)
        self._persist()
        return rec

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load records from disk; silently initialise empty store if missing."""
        if not self._path.exists():
            self._records = []
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            self._records = [TaskRecord(**entry) for entry in payload.get("tasks", [])]
        except (json.JSONDecodeError, TypeError, KeyError):
            self._records = []

    def _persist(self) -> None:
        """Write current records to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"tasks": [asdict(r) for r in self._records]}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
