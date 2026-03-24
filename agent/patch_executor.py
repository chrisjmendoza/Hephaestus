"""File patching with unified diff preview for Hephaestus."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatchResult:
    """Outcome of a single patch operation."""

    file_path: str
    diff: str
    applied: bool
    dry_run: bool


class PatchExecutor:
    """Applies file patches with unified diff preview and dry-run support."""

    def apply(
        self,
        file_path: str | Path,
        new_content: str,
        dry_run: bool = False,
    ) -> PatchResult:
        """Replace full file content and return a unified diff of the change.

        Args:
            file_path: Path to the target file.
            new_content: Desired final content of the file.
            dry_run: If True, compute diff but do not write to disk.

        Returns:
            PatchResult with diff text and applied status.
        """
        target = Path(file_path)
        old_content = target.read_text(encoding="utf-8") if target.exists() else ""

        diff = "".join(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{target.name}",
                tofile=f"b/{target.name}",
            )
        )

        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_content, encoding="utf-8")

        return PatchResult(
            file_path=str(target),
            diff=diff,
            applied=not dry_run,
            dry_run=dry_run,
        )

    def apply_replacement(
        self,
        file_path: str | Path,
        old_text: str,
        new_text: str,
        dry_run: bool = False,
    ) -> PatchResult:
        """Replace a specific substring within a file.

        Args:
            file_path: Path to the target file.
            old_text: Exact text to find and replace (must appear exactly once).
            new_text: Replacement text.
            dry_run: If True, compute diff but do not write to disk.

        Returns:
            PatchResult with diff text and applied status.

        Raises:
            ValueError: If old_text is not found in the file.
            ValueError: If old_text appears more than once (ambiguous replacement).
        """
        target = Path(file_path)
        original = target.read_text(encoding="utf-8")

        count = original.count(old_text)
        if count == 0:
            raise ValueError(
                f"Replacement target not found in {target.name}. "
                "Ensure old_text matches exactly."
            )
        if count > 1:
            raise ValueError(
                f"Replacement target found {count} times in {target.name}. "
                "Provide more context to make the match unambiguous."
            )

        modified = original.replace(old_text, new_text, 1)
        return self.apply(target, modified, dry_run=dry_run)
