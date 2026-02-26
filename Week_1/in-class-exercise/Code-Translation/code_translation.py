from __future__ import annotations

import argparse
import re
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama

CODE_FENCE_RE = re.compile(r"```(?:python)?\s*(?P<code>[\s\S]*?)\s*```", re.IGNORECASE)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def extract_code(text: str) -> str:
    m = CODE_FENCE_RE.search(text)
    if m:
        return m.group("code").strip() + "\n"
    return text.strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-prompt-file", required=True, type=Path, help="Prompt template file.")
    ap.add_argument("--system-prompt-file", required=True, type=Path, help="System prompt file.")
    ap.add_argument("--model", default="devstral-small-2:24b-cloud", help="Ollama model name.")
    ap.add_argument("--base-url", default=None, help="Optional Ollama base URL, e.g. http://localhost:11434")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--num-ctx", type=int, default=4096 * 16)
    args = ap.parse_args()

    in_dir = Path("cpp_programs").resolve()
    out_dir = Path("output_code_translation/solution").resolve()

    if not in_dir.exists() or not in_dir.is_dir():
        raise SystemExit(f"Input folder not found: {in_dir}")

    prompt_template = read_text(args.user_prompt_file)
    system_prompt_text = read_text(args.system_prompt_file)

    cpp_files = sorted([p for p in in_dir.glob("*.cpp") if p.is_file()])
    if not cpp_files:
        raise SystemExit(f"No .cpp files found in: {in_dir}")

    llm_kwargs = {
        "model": args.model,
        "temperature": args.temperature,
        "num_ctx": args.num_ctx,
    }
    if args.base_url:
        llm_kwargs["base_url"] = args.base_url

    llm = ChatOllama(**llm_kwargs)

    system_msg = SystemMessage(content=system_prompt_text)

    out_dir.mkdir(parents=True, exist_ok=True)

    for src in cpp_files:
        code = read_text(src)

        user_prompt = prompt_template.format(
            filename=src.name,
            code=code,
        )

        resp = llm.invoke([system_msg, HumanMessage(content=user_prompt)])
        content = getattr(resp, "content", str(resp))
        fixed_code = extract_code(content)

        py_name = src.name[:-4] + ".py"
        dst = out_dir / py_name
        write_text(dst, fixed_code)

        print(f"Saved: {dst}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

