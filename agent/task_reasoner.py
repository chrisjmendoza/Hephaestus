"""LLM-powered task reasoning for Hephaestus."""

from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI

from .repo_scanner import RepoScanner
from .repo_semantic import RepoSemanticIndex


class TaskReasoner:
    """Generates structured implementation plans from task and repository context."""

    def __init__(
        self,
        index_path: str | Path = "memory/repo_index.json",
        embeddings_path: str | Path = "memory/repo_embeddings.json",
    ) -> None:
        """Initialize repository context helpers and OpenAI client setup."""
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

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return self._fallback_plan(task, relevant_files)

        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=os.getenv("HEPHAESTUS_PLAN_MODEL", "gpt-4o-mini"),
                temperature=0,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            parsed = self._parse_plan_text(content)
            return parsed if parsed else self._fallback_plan(task, relevant_files)
        except Exception:
            return self._fallback_plan(task, relevant_files)
