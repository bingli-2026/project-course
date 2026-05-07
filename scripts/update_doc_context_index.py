#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "doc" / "context" / "key-context-index.md"


def collect(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pat in patterns:
        files.extend(ROOT.glob(pat))
    uniq = sorted({p for p in files if p.is_file()}, key=lambda p: p.as_posix())
    return uniq


def fmt_list(paths: list[Path]) -> str:
    if not paths:
        return "- (none)"
    lines = []
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        lines.append(f"- `{rel}`")
    return "\n".join(lines)


def main() -> int:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    context_docs = collect([
        "doc/communications/*.md",
        "doc/*开题*.md",
        "doc/plantuml/*.puml",
        "doc/images/plantuml/*.svg",
    ])
    project_docs = collect([
        "README.md",
        "pyproject.toml",
        "laboratory/**/README.md",
        "src/project_course/**/*.py",
        "tests/**/*.py",
    ])

    body = "\n".join(
        [
            "# Key Context Index",
            "",
            f"Generated at: `{now}`",
            "",
            "## Key Context Documents",
            fmt_list(context_docs),
            "",
            "## Project Documents",
            fmt_list(project_docs),
            "",
            "## How To Refresh",
            "Run: `python3 scripts/update_doc_context_index.py`",
        ]
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body + "\n", encoding="utf-8")
    print(f"Updated {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
