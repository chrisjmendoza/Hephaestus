"""LLM-powered task reasoning for Hephaestus.

Provider selection
------------------
Set ``AI_PROVIDER`` to one of ``openai``, ``anthropic``, or
``openai-compatible`` (any OpenAI-API-compatible server such as Ollama,
Groq, LM Studio, etc.).

When ``AI_PROVIDER`` is not set, the provider is auto-detected from which
API key is present in the environment:

* ``ANTHROPIC_API_KEY`` → **anthropic**
* ``OPENAI_API_KEY``    → **openai**
* ``OPENAI_BASE_URL`` only → **openai-compatible** (e.g. local Ollama)
* None of the above    → deterministic fallback plan (no LLM call)

Override the model with ``AI_MODEL``.  Default models:

* openai: ``gpt-4o-mini``
* anthropic: ``claude-3-5-haiku-20241022``
* openai-compatible: must be supplied via ``AI_MODEL``
"""

from __future__ import annotations

import os
from pathlib import Path

from .repo_scanner import RepoScanner
from .repo_semantic import RepoSemanticIndex

_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
}

_SYSTEM_MESSAGE = (
    "You are an experienced software engineer planning a code change.\n\n"
    "Given a repository context and a development task,\n"
    "produce a clear step-by-step implementation plan.\n\n"
    "Do NOT write code.\n"
    "Only describe the steps required."
)


class TaskReasoner:
    """Generates structured implementation plans from task and repository context."""

    def __init__(
        self,
        index_path: str | Path = "memory/repo_index.json",
        embeddings_path: str | Path = "memory/repo_embeddings.json",
    ) -> None:
        """Initialize repository context helpers."""
        self.index_path = Path(index_path)
        self.embeddings_path = Path(embeddings_path)
        self.repo_scanner = RepoScanner(index_path=self.index_path)
        self.repo_semantic = RepoSemanticIndex(
            index_path=self.index_path,
            embeddings_path=self.embeddings_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

        provider, api_key, model, base_url = self._resolve_provider()
        if not provider:
            return self._fallback_plan(task, relevant_files)

        try:
            if provider == "anthropic":
                content = self._call_anthropic(prompt, _SYSTEM_MESSAGE, model, api_key)
            else:
                content = self._call_openai(prompt, _SYSTEM_MESSAGE, model, api_key, base_url)

            if not content:
                return self._fallback_plan(task, relevant_files)

            parsed = self._parse_plan_text(content)
            return parsed if parsed else self._fallback_plan(task, relevant_files)
        except Exception:
            return self._fallback_plan(task, relevant_files)

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_provider() -> tuple[str, str, str, str]:
        """Determine active provider, API key, model, and base URL from env.

        Returns ``(provider, api_key, model, base_url)``.  ``provider`` is an
        empty string when no credentials are configured, signalling that the
        caller should fall back to the deterministic plan.
        """
        provider = os.getenv("AI_PROVIDER", "").strip().lower()
        model_override = os.getenv("AI_MODEL", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "").strip()

        # Auto-detect when AI_PROVIDER is not explicitly set
        if not provider:
            if anthropic_key:
                provider = "anthropic"
            elif openai_key:
                provider = "openai"
            elif base_url:
                provider = "openai-compatible"
            else:
                return ("", "", "", "")

        # Map provider to credentials and default model
        if provider == "anthropic":
            key = anthropic_key
            default_model = _PROVIDER_DEFAULTS["anthropic"]
        elif provider == "openai-compatible":
            # Local endpoints (Ollama, LM Studio) don't require a real key
            key = openai_key or "local"
            default_model = ""
        else:
            provider = "openai"
            key = openai_key
            default_model = _PROVIDER_DEFAULTS["openai"]

        if not key:
            return ("", "", "", "")

        model = model_override or default_model
        return (provider, key, model, base_url)

    # ------------------------------------------------------------------
    # LLM callers (SDK imported lazily to keep startup fast)
    # ------------------------------------------------------------------

    @staticmethod
    def _call_openai(
        prompt: str,
        system: str,
        model: str,
        api_key: str,
        base_url: str = "",
    ) -> str | None:
        """Call OpenAI (or any OpenAI-compatible) chat completions endpoint."""
        from openai import OpenAI

        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        client = OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return (response.choices[0].message.content or "").strip() or None

    @staticmethod
    def _call_anthropic(
        prompt: str,
        system: str,
        model: str,
        api_key: str,
    ) -> str | None:
        """Call Anthropic Messages API."""
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text if message.content else ""
        return text.strip() or None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

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
