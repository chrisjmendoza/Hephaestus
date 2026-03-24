"""Core orchestration logic for the Hephaestus development agent."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .git_context import GitCommitResult, GitContext, GitStatus
from .patch_executor import PatchExecutor, PatchResult
from .planner import TaskPlanner
from .repo_query import RepoQuery
from .repo_scanner import RepoScanner
from .repo_semantic import RepoSemanticIndex
from .task_reasoner import TaskReasoner
from .task_report import TaskReport, TaskReporter
from .test_runner import TestRunResult, TestRunner
from .tools import run_command


class HephaestusAgent:
    """Orchestrates planning and step execution for development tasks."""

    def __init__(
        self,
        prompt_path: str = "prompts/dev_agent.md",
        log_path: str = "logs/hephaestus.log",
    ) -> None:
        """Initialize dependencies and load instruction prompt."""
        self.prompt_path = Path(prompt_path)
        self.log_path = Path(log_path)
        self.planner = TaskPlanner()
        self.repo_scanner = RepoScanner(index_path=Path("memory") / "repo_index.json")
        self.repo_query = RepoQuery(index_path=Path("memory") / "repo_index.json")
        self.repo_semantic = RepoSemanticIndex(
            index_path=Path("memory") / "repo_index.json",
            embeddings_path=Path("memory") / "repo_embeddings.json",
        )
        self.task_reasoner = TaskReasoner(
            index_path=Path("memory") / "repo_index.json",
            embeddings_path=Path("memory") / "repo_embeddings.json",
        )
        self.patch_executor = PatchExecutor()
        self.test_runner = TestRunner()
        self.task_reporter = TaskReporter(
            report_path=Path("memory") / "task_report.json"
        )
        self._git: GitContext | None = None
        self.instructions = self.prompt_path.read_text(encoding="utf-8")

    def _get_git(self, repo_path: str = ".") -> GitContext:
        """Return a GitContext for repo_path, initializing lazily."""
        if self._git is None:
            self._git = GitContext(repo_path)
        return self._git

    def scan_repo(self, repo_path: str) -> dict:
        """Scan a repository and persist its index to memory."""
        self.log(f"REPO_SCAN_START {repo_path}")
        index = self.repo_scanner.scan_repository(repo_path)
        self.log(f"REPO_LANGUAGE_DETECTED {index.get('language_counts', {})}")
        self.log(f"REPO_SCAN_COMPLETE total_files={index['total_files']}")
        return index

    def query_repo(self, query_type: str) -> list[str] | dict[str, int]:
        """Query repository index data by query type."""
        self.log(f"REPO_QUERY_START {query_type}")

        if query_type == "python":
            result = self.repo_query.get_python_files()
        elif query_type == "tests":
            result = self.repo_query.get_test_files()
        elif query_type == "entrypoints":
            result = self.repo_query.get_entrypoints()
        elif query_type == "config":
            result = self.repo_query.get_config_files()
        elif query_type == "dirs":
            result = self.repo_query.get_directory_summary()
        else:
            raise ValueError(
                "Unsupported query type. Use: python, tests, entrypoints, config, dirs"
            )

        self.log(f"REPO_QUERY_COMPLETE {query_type}")
        return result

    def semantic_search(self, query: str, repo_path: str = ".", top_k: int = 5) -> list[str]:
        """Build and query semantic repository index for a natural-language query."""
        self.log(f"SEMANTIC_SEARCH_START {query}")
        self.scan_repo(repo_path)
        self.repo_semantic.build_index(repo_path)
        self.log("MULTILANG_INDEX_BUILD")
        results = self.repo_semantic.search(query, top_k=top_k)
        self.log(f"SEMANTIC_SEARCH_COMPLETE matches={len(results)}")
        return results

    def generate_task_plan(self, task: str, repo_path: str = ".") -> list[str]:
        """Generate and persist a structured development plan for a task."""
        self.log(f"TASK_REASON_START {task}")
        plan = self.task_reasoner.generate_plan(task, repo_path=repo_path)

        task_plan_path = Path("memory") / "task_plan.json"
        task_plan_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"task": task, "plan": plan}
        task_plan_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        self.log(f"TASK_REASON_COMPLETE steps={len(plan)}")
        return plan

    def generate_report(
        self,
        task: str,
        plan: list[str],
        patch_results: list[PatchResult] | None = None,
        test_results: list[TestRunResult] | None = None,
        commit_results: list[GitCommitResult] | None = None,
        outcome: str = "success",
    ) -> TaskReport:
        """Build, persist, and return a structured report for a completed task."""
        self.log(f"TASK_REPORT_START {task}")
        report = self.task_reporter.start(task, plan)

        for pr in patch_results or []:
            self.task_reporter.record_patch(
                report,
                file_path=pr.file_path,
                diff=pr.diff,
                applied=pr.applied,
                dry_run=pr.dry_run,
            )

        for tr in test_results or []:
            self.task_reporter.record_test(
                report,
                test_path=" ".join(tr.command),
                passed=tr.passed,
                summary=tr.summary,
                failed_tests=tr.failed_tests,
            )

        for cr in commit_results or []:
            self.task_reporter.record_commit(
                report,
                commit_sha=cr.commit_sha,
                commit_message=cr.commit_message,
                files_committed=cr.files_committed,
            )

        self.task_reporter.finish(report, outcome=outcome)
        self.task_reporter.persist(report)
        self.log(
            f"TASK_REPORT_COMPLETE outcome={outcome} "
            f"patches={len(report.patches)} "
            f"test_runs={len(report.test_runs)} "
            f"commits={len(report.commits)}"
        )
        return report

    def git_status(self, repo_path: str = ".") -> GitStatus:
        """Return a structured snapshot of the working tree state."""
        self.log(f"GIT_STATUS_START {repo_path}")
        status = self._get_git(repo_path).status()
        self.log(
            f"GIT_STATUS_COMPLETE branch={status.branch} "
            f"dirty={status.is_dirty} "
            f"staged={len(status.staged_files)} unstaged={len(status.unstaged_files)}"
        )
        return status

    def git_diff(self, repo_path: str = ".", file_path: str | None = None) -> str:
        """Return unified diff of unstaged working-tree changes."""
        self.log(f"GIT_DIFF_START {file_path or 'all'}")
        diff = self._get_git(repo_path).diff_working_tree(file_path)
        self.log(f"GIT_DIFF_COMPLETE chars={len(diff)}")
        return diff

    def git_commit_patch(
        self,
        file_paths: list[str],
        message: str,
        repo_path: str = ".",
    ) -> GitCommitResult:
        """Stage and commit the given files with a descriptive message."""
        self.log(f"GIT_COMMIT_START files={file_paths}")
        result = self._get_git(repo_path).commit_patch(file_paths, message)
        self.log(
            f"GIT_COMMIT_COMPLETE sha={result.commit_sha} "
            f"files={result.files_committed}"
        )
        return result

    def apply_patch(
        self,
        file_path: str,
        new_content: str,
        dry_run: bool = False,
    ) -> PatchResult:
        """Apply a full-content patch to a file, with optional dry-run preview."""
        self.log(f"PATCH_START {file_path} dry_run={dry_run}")
        result = self.patch_executor.apply(file_path, new_content, dry_run=dry_run)
        if result.diff:
            self.log(f"PATCH_PREVIEW\n{result.diff}")
        if result.applied:
            self.log(f"PATCH_APPLIED {file_path}")
        else:
            self.log(f"PATCH_SKIPPED {file_path} (dry_run)")
        return result

    def apply_replacement(
        self,
        file_path: str,
        old_text: str,
        new_text: str,
        dry_run: bool = False,
    ) -> PatchResult:
        """Replace a specific substring in a file, with optional dry-run preview."""
        self.log(f"PATCH_START {file_path} dry_run={dry_run}")
        result = self.patch_executor.apply_replacement(
            file_path, old_text, new_text, dry_run=dry_run
        )
        if result.diff:
            self.log(f"PATCH_PREVIEW\n{result.diff}")
        if result.applied:
            self.log(f"PATCH_APPLIED {file_path}")
        else:
            self.log(f"PATCH_SKIPPED {file_path} (dry_run)")
        return result

    def run_tests(
        self,
        test_path: str = "tests",
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Run tests at test_path and return a structured pass/fail result."""
        self.log(f"TEST_RUN_START {test_path}")
        result = self.test_runner.run(test_path, extra_args=extra_args)
        self.log(
            f"TEST_RUN_COMPLETE exit_code={result.exit_code} "
            f"passed={result.passed} summary={result.summary!r}"
        )
        if result.failed_tests:
            self.log(f"TEST_FAILURES {result.failed_tests}")
        return result

    def run_test_file(self, test_file: str) -> TestRunResult:
        """Run a single test file and return a structured pass/fail result."""
        self.log(f"TEST_RUN_START {test_file}")
        result = self.test_runner.run_file(test_file)
        self.log(
            f"TEST_RUN_COMPLETE exit_code={result.exit_code} "
            f"passed={result.passed} summary={result.summary!r}"
        )
        if result.failed_tests:
            self.log(f"TEST_FAILURES {result.failed_tests}")
        return result

    def run_task(self, task: str) -> str:
        """Create a plan and execute steps for the given task."""
        output_lines = ["Hephaestus initialized", f"Task received: {task}"]
        self.log(f"TASK_RECEIVED {task}")

        plan = self.planner.create_plan(task)
        self.log(f"PLAN_CREATED {plan}")
        output_lines.append(f"Plan generated: {plan}")
        output_lines.append("Executing steps")

        for step in plan:
            output_lines.append(self.execute_step(step))

        self.log("TASK_COMPLETE")
        output_lines.append("Task complete")
        return "\n".join(output_lines)

    def execute_step(self, step: str) -> str:
        """Execute one plan step using placeholder tool behavior."""
        self.log(f"STEP_START {step}")
        result = run_command("echo step executed")
        self.log(f"STEP_COMPLETE {step} | {result}")
        return f"{step}: {result}"

    def log(self, message: str) -> None:
        """Append a timestamped message to the agent log file."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {message}\n")
