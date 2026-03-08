"""Entry point for the Hephaestus development agent."""

from __future__ import annotations

import sys

from agent.agent import HephaestusAgent


def main() -> None:
    """Parse CLI input, run the agent task loop, and print results."""
    if len(sys.argv) < 2:
        print("Usage: python main.py \"<task>\"")
        print("   or: python main.py scan <repo_path>")
        print("   or: python main.py query <python|tests|entrypoints|dirs>")
        print("   or: python main.py semantic \"<query>\"")
        print("   or: python main.py plan \"<task>\"")
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
        elif query_type == "dirs":
            print("Directory summary:")
            for directory, count in result.items():
                print(f"{directory}: {count}")
        return

    if sys.argv[1] == "semantic":
        if len(sys.argv) < 3:
            print("Usage: python main.py semantic \"<query>\"")
            return

        query = " ".join(sys.argv[2:]).strip()
        results = agent.semantic_search(query, repo_path=".")
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

    task = " ".join(sys.argv[1:]).strip()
    result = agent.run_task(task)
    print(result)


if __name__ == "__main__":
    main()
