"""LLM-powered task reasoning for Hephaestus."""

from __future__ import annotations

import os
from pathlib import Path

import anthropic

from .repo_scanner import RepoScanner
from .repo_semantic import RepoSemanticIndex


class TaskReasoner:
    """Generates structured implementation plans from task and repository context."""

    def __init__(
        self,
        index_path: str | Path = "memory/repo_index.json",
        embeddings_path: str | Path = "memory/repo_embeddings.json",
    ) -> None:
        """Initialize repository context helpers and Anthropic client setup."""
        self.index_path = Path(index_path)
        self.embeddings_path = Path(embeddings_path)
        self.repo_scanner = RepoScanner(index_path=self.index_path)
        self.repo_semantic = RepoSemanticIndex(
            index_path=self.index_path,
            embeddings_path=self.embeddings_path,
        )

    @staticmethod
    def _extract_snippet(path: Path, size: int = 500) -> str:
        """Read and truncate a code snippet for prompt context."""
        try:
            return path.read_text(encoding="utf-8")[:size]
        except UnicodeDecodeError:
            return ""

    @staticmethod
    def _parse_plan_text(plan_text: str) -> list[str]:
        """Convert model text output into a clean list of plan steps."""
        steps: list[str] = []
        for raw_line in plan_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if ". " in line[:4] and line[0].isdigit():
                line = line.split(". ", 1)[1].strip()
            if line.startswith("-"):
                line = line.lstrip("- ").strip()
            if line:
                steps.append(line)
        return steps

    @staticmethod
    def _fallback_plan(task: str, relevant_files: list[str]) -> list[str]:
        """Return deterministic fallback plan when LLM is unavailable."""
        focus = ", ".join(relevant_files[:3]) if relevant_files else "repository structure"
        return [
            f"Analyze task requirements for: {task}",
            f"Review relevant files and context: {focus}",
            "Define minimal code changes aligned with current architecture",
            "Implement and validate changes with focused tests",
            "Update documentation and summarize outcomes",
        ]

    def generate_patch(
        self,
        instruction: str,
        file_path: str,
        current_content: str,
        max_content_chars: int = 8000,
    ) -> str:
        """Generate modified file content from an instruction and the current file.

        Args:
            instruction: Natural-language description of the change to make.
            file_path:   Path to the target file (used for context in the prompt).
            current_content: Current text of the file.
            max_content_chars: Truncation limit for large files sent to the LLM.

        Returns:
            Complete new file content, or *current_content* if the LLM is
            unavailable or returns an empty response.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return current_content

        truncated = current_content[:max_content_chars]
        system_message = (
            "You are an expert software engineer.\n"
            "Given a file's current content and an instruction, "
            "return ONLY the complete modified file content.\n"
            "Do NOT include explanations, markdown code fences, or any other text.\n"
            "Return the raw file content only."
        )
        prompt = (
            f"Instruction:\n{instruction}\n\n"
            f"File: {file_path}\n\n"
            f"Current content:\n{truncated}\n"
        )

        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=os.getenv("HEPHAESTUS_PLAN_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=4096,
                system=system_message,
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks = [b for b in response.content if b.type == "text"]
            content = (text_blocks[0].text if text_blocks else "").strip()
            # Strip markdown fences if the model wrapped the output
            if content.startswith("```"):
                lines = content.splitlines()
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                content = "\n".join(lines[1:end])
            return content if content else current_content
        except Exception:
            return current_content

    def generate_plan(self, task: str, repo_path: str = ".") -> list[str]:
        """Generate a structured task plan using semantic context and LLM reasoning."""
        repo_root = Path(repo_path).resolve()

        self.repo_scanner.scan_repository(str(repo_root))
        self.repo_semantic.build_index(str(repo_root))
        relevant_files = self.repo_semantic.search(task, top_k=5)

        snippets: list[str] = []
        for relative_path in relevant_files:
            snippet = self._extract_snippet(repo_root / relative_path)
            snippets.append(f"FILE: {relative_path}\nSNIPPET:\n{snippet}")

        context_block = "\n\n".join(snippets)
        prompt = (
            f"Task:\n{task}\n\n"
            f"Relevant files:\n" + "\n".join(relevant_files) + "\n\n"
            f"Code context:\n{context_block}\n"
        )

        system_message = (
            "You are an experienced software engineer planning a code change.\n\n"
            "Given a repository context and a development task,\n"
            "produce a clear step-by-step implementation plan.\n\n"
            "Do NOT write code.\n"
            "Only describe the steps required."
        )

        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return self._fallback_plan(task, relevant_files)

        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=os.getenv("HEPHAESTUS_PLAN_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=1024,
                system=system_message,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
            text_blocks = [b for b in response.content if b.type == "text"]
            content = (text_blocks[0].text if text_blocks else "").strip()
            parsed = self._parse_plan_text(content)
            return parsed if parsed else self._fallback_plan(task, relevant_files)
        except Exception:
            return self._fallback_plan(task, relevant_files)
