from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from .agent import Agent
from .llm import OllamaLLM
from .types import AgentConfig
from .utils import ensure_repo_path

DEFAULT_MODEL = "devstral-small-2:24b-cloud"
DEFAULT_HOST = "http://localhost:11434"
VERSION = "0.5.0"


def sanitize_name(text: str) -> str:
    """Convert text to a valid directory/file name."""
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[\s-]+', '_', text)
    return text.strip('_')


def generate_repo_name(project_name: str) -> str:
    """Generate repository path with timestamp."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"output/{project_name}_{timestamp}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cca",
        description="CLI agent for Code generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            cca create "calculator app"
            cca create "web scraper" --planning detailed
            cca commit --repo output/my_project
        """
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    p.add_argument("--repo", help="Repository path")
    p.add_argument(
        "--model",
        default=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL),
        help=f"Ollama model (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("OLLAMA_HOST", DEFAULT_HOST),
        help=f"Ollama host (default: {DEFAULT_HOST})",
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=float(os.environ.get("OLLAMA_TEMPERATURE", "0.0")),
        help="Sampling temperature (default: 0.0)",
    )
    p.add_argument("--verbose", action="store_true", help="Verbose output")

    sub = p.add_subparsers(dest="cmd", required=True)

    # Create command
    c = sub.add_parser("create", help="Create a module")
    c.add_argument("description", help="What to create")
    c.add_argument("--module", help="Module path (default: src/main.py)")
    c.add_argument(
        "--planning",
        choices=['default', 'detailed', 'minimal'],
        default='default',
        help="Planning prompt variant"
    )
    c.add_argument(
        "--codegen",
        choices=['default', 'documented', 'minimal'],
        default='default',
        help="Code generation prompt variant"
    )

    # List prompts command
    sub.add_parser("list-prompts", help="List all available prompt variants")

    # Commit command
    cm = sub.add_parser("commit", help="Commit changes")
    cm.add_argument("message", nargs='?', default="Update project", help="Commit message")
    cm.add_argument("--push", action="store_true", help="Also run git push")

    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    
    # List prompts command doesn't need repo
    if args.cmd == "list-prompts":
        from .prompt_manager import PromptManager
        pm = PromptManager()
        tasks = pm.list_available_tasks()
        
        print("Available Prompt Tasks and Variants:")
        print("=" * 60)
        for task in sorted(tasks):
            variants = pm.list_variants(task)
            metadata = pm.get_metadata(task)
            desc = metadata.get('description', 'No description')
            print(f"\n{task.upper()}")
            print(f"  Description: {desc}")
            print(f"  Variants: {', '.join(variants)}")
        print()
        return 0
    
    # Handle create command
    if args.cmd == "create":
        # Generate project name from description
        words = args.description.lower().split()
        stop_words = {'a', 'an', 'the', 'with', 'for', 'to', 'in', 'on', 'of', 'and', 'or'}
        key_words = [w for w in words[:4] if w not in stop_words]
        project_name = '_'.join(key_words) if key_words else 'project'
        
        if not args.repo:
            args.repo = generate_repo_name(sanitize_name(project_name))
            print(f"Repository: {args.repo}")
        
        if not args.module:
            args.module = 'src/main.py'
            print(f"Module: {args.module}")
        
        # Initialize git repo
        repo_path = Path(args.repo)
        if not repo_path.exists():
            repo_path.mkdir(parents=True, exist_ok=True)
            git_dir = repo_path / '.git'
            if not git_dir.exists():
                import subprocess
                subprocess.run(['git', 'init'], cwd=repo_path, capture_output=True)
                print(f"Initialized git repository")
        
        print(f"\nCreating: {args.description}")
        print(f"Planning: {args.planning}, Code gen: {args.codegen}\n")
    
    # Handle commit command
    if args.cmd == "commit":
        if not args.repo:
            print("Error: --repo is required for commit command", file=sys.stderr)
            return 1
    
    # Ensure repo exists for commands that need it
    if args.cmd in ["create", "commit"]:
        ensure_repo_path(args.repo)

    cfg = AgentConfig(
        repo=args.repo,
        model=args.model,
        host=args.host,
        temperature=args.temperature,
        verbose=args.verbose,
    )
    agent = Agent(cfg)
    
    # Set variants if create command
    if args.cmd == "create":
        agent.planning_variant = args.planning
        agent.code_gen_variant = args.codegen

    try:
        if args.cmd == "create":
            r = agent.create_program(args.description, args.module)
        elif args.cmd == "commit":
            r = agent.commit_and_push(args.message, args.push)
        else:
            print(f"Unknown command: {args.cmd}", file=sys.stderr)
            return 1

        stream = sys.stdout if r.ok else sys.stderr
        print(r.details, file=stream)
        
        return 0 if r.ok else 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        print(str(e) or e.__class__.__name__, file=sys.stderr)
        return 1


def main() -> None:
    # If the user runs `cca` with no arguments, open an interactive session.
    if len(sys.argv) == 1:
        from .interactive import repl
        raise SystemExit(repl())
    raise SystemExit(run())


if __name__ == "__main__":
    main()
