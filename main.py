"""Entry point for the Hephaestus development agent."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from agent.agent import HephaestusAgent


def main() -> None:
    """Parse CLI input, run the agent task loop, and print results."""
    load_dotenv()
    if len(sys.argv) < 2:
        print("Usage: python main.py \"<task>\" [--dry-run]")
        print("   or: python main.py scan <repo_path>")
        print("   or: python main.py query <python|tests|entrypoints|dirs>")
        print("   or: python main.py semantic \"<query>\" --repo <path>")
        print("   or: python main.py plan \"<task>\"")
        print("   or: python main.py resolve <issue_number> [--repo <path>] [--github-repo owner/repo] [--dry-run]")
        return

    print("Starting Hephaestus...")
    agent = HephaestusAgent()

    if sys.argv[1] == "scan":
        if len(sys.argv) < 3:
            print("Usage: python main.py scan <repo_path>")
            return

        repo_path = sys.argv[2]
        index = agent.scan_repo(repo_path)
        entrypoints_summary = ", ".join(index["entrypoints"]) or "None"
        config_summary = ", ".join(index["config_files"]) or "None"

        print("Repository Scan Complete")
        print("")
        print(f"Total files: {index['total_files']}")
        print(f"Python files: {len(index['python_files'])}")
        print(f"Test files: {len(index['test_files'])}")
        print(f"Language counts: {index.get('language_counts', {})}")
        print(f"Entrypoints: {entrypoints_summary}")
        print(f"Config files: {config_summary}")
        return

    if sys.argv[1] == "query":
        if len(sys.argv) < 3:
            print("Usage: python main.py query <python|tests|entrypoints|dirs>")
            return

        query_type = sys.argv[2]
        result = agent.query_repo(query_type)

        if query_type == "python":
            print(f"Python files detected: {len(result)}")
        elif query_type == "tests":
            print(f"tests detected: {len(result)}")
        elif query_type == "entrypoints":
            summary = ", ".join(result) if result else "None"
            print(f"entrypoints: {summary}")
        elif query_type == "dirs" and isinstance(result, dict):
            print("Directory summary:")
            for directory, count in result.items():
                print(f"{directory}: {count}")
        return

    if sys.argv[1] == "semantic":
        if len(sys.argv) < 3:
            print("Usage: python main.py semantic \"<query>\" --repo <path>")
            return

        semantic_args = sys.argv[2:]
        repo_path = "."
        if "--repo" in semantic_args:
            repo_flag_index = semantic_args.index("--repo")
            if repo_flag_index + 1 >= len(semantic_args):
                print("Usage: python main.py semantic \"<query>\" --repo <path>")
                return
            repo_path = semantic_args[repo_flag_index + 1]
            query_parts = semantic_args[:repo_flag_index]
        else:
            query_parts = semantic_args

        query = " ".join(query_parts).strip()
        if not query:
            print("Usage: python main.py semantic \"<query>\" --repo <path>")
            return

        results = agent.semantic_search(query, repo_path=repo_path)
        print("Top matches:")
        print("")
        for index, path in enumerate(results, start=1):
            print(f"{index}. {path}")
        return

    if sys.argv[1] == "plan":
        if len(sys.argv) < 3:
            print("Usage: python main.py plan \"<task>\"")
            return

        task = " ".join(sys.argv[2:]).strip()
        plan = agent.generate_task_plan(task, repo_path=".")

        print("PLAN")
        for index, step in enumerate(plan, start=1):
            print(f"{index}. {step}")
        return

    if sys.argv[1] == "resolve":
        if len(sys.argv) < 3 or not sys.argv[2].lstrip("-").isdigit():
            print("Usage: python main.py resolve <issue_number> [--repo <path>] [--github-repo owner/repo] [--dry-run]")
            return

        resolve_args = sys.argv[2:]
        issue_number = int(resolve_args[0])

        repo_path = "."
        github_repo: str | None = None
        dry_run = False

        i = 1
        while i < len(resolve_args):
            arg = resolve_args[i]
            if arg == "--repo" and i + 1 < len(resolve_args):
                repo_path = resolve_args[i + 1]
                i += 2
            elif arg == "--github-repo" and i + 1 < len(resolve_args):
                github_repo = resolve_args[i + 1]
                i += 2
            elif arg == "--dry-run":
                dry_run = True
                i += 1
            else:
                i += 1

        import os
        github_token = os.getenv("GITHUB_TOKEN")

        if not github_repo:
            print(f"Resolving issue #{issue_number} in {repo_path} (local only, no PR)...")
        else:
            print(f"Resolving issue #{issue_number} in {repo_path} via {github_repo}...")
        if dry_run:
            print("(dry-run mode — no files will be written or committed)")

        # Fetch the issue to use its title/body as the task description
        if github_repo:
            try:
                issue = agent.gh_get_issue(github_repo, issue_number)
                task = f"Fix GitHub issue #{issue_number}: {issue.title}\n\n{issue.body or ''}"
                print(f"Issue: {issue.title}")
            except Exception as exc:
                print(f"Could not fetch issue from GitHub: {exc}")
                task = f"Fix issue #{issue_number}"
        else:
            task = f"Fix issue #{issue_number}"

        # Generate a plan to determine which files need patching
        plan = agent.generate_task_plan(task, repo_path=repo_path)
        print("\nPLAN:")
        for idx, step in enumerate(plan, start=1):
            print(f"  {idx}. {step}")

        result = agent.resolve_issue(
            task=task,
            patches=[],  # patches derived from the plan via resolve_issue pipeline
            repo_path=repo_path,
            github_repo=github_repo,
            issue_number=issue_number,
            dry_run=dry_run,
            github_token=github_token,
        )

        if result.success:
            print(f"\nResolved successfully.")
            if result.pull_request:
                print(f"Pull request: {result.pull_request.url}")
        else:
            print(f"\nResolution failed: {result.error}")
        return

    task_args = sys.argv[1:]
    dry_run = "--dry-run" in task_args
    task_words = [a for a in task_args if a != "--dry-run"]
    task = " ".join(task_words).strip()
    if dry_run:
        print("(dry-run mode — no files will be written or committed)")
    result = agent.run_task(task, dry_run=dry_run)
    print(result)


if __name__ == "__main__":
    main()
