#!/usr/bin/env python3
"""Превращает coverage.json (branch coverage) в отчёт, пригодный для LLM.

Этот скрипт для каждой непокрытой строки/ветки находит функцию, в
которой она находится, вытаскивает реальный сниппет кода вокруг неё и
помечает потенциально важные пропуски (в первую очередь — `raise`/`except`,
то есть необработанные тестами пути ошибок).

Использование:
    1. Прогони тесты с branch coverage и JSON-отчётом:
       pytest --cov=autodoc --cov-branch --cov-report=json

    2. Сгенерируй отчёт:
       python coverage_gap_report.py \
           --coverage-json coverage.json \
           --tests-root tests \
           --out coverage_gaps.md
"""

import argparse
import ast
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Scope:
    start: int
    end: int
    qualname: str


@dataclass
class Gap:
    start: int
    end: int
    qualname: str | None
    kind: str  # "lines" | "branch"
    detail: str = ""


def build_scope_index(source: str) -> list[Scope]:
    """Строит список функций/классов файла с их диапазонами строк."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    scopes: list[Scope] = []
    stack: list[str] = []

    def visit(node: ast.AST) -> None:
        is_scope = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        if is_scope:
            stack.append(node.name)  # type: ignore[attr-defined]
            end = getattr(node, "end_lineno", node.lineno)
            scopes.append(Scope(node.lineno, end, ".".join(stack)))
        for child in ast.iter_child_nodes(node):
            visit(child)
        if is_scope:
            stack.pop()

    visit(tree)
    return scopes


def find_enclosing(scopes: list[Scope], line: int) -> str | None:
    candidates = [s for s in scopes if s.start <= line <= s.end]
    if not candidates:
        return None
    candidates.sort(key=lambda s: s.end - s.start)
    return candidates[0].qualname


def merge_ranges(lines: list[int]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for ln in sorted(set(lines)):
        if ranges and ln == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], ln)
        else:
            ranges.append((ln, ln))
    return ranges


def find_test_file(src_path: str, tests_root: Path) -> Path | None:
    """Best-effort поиск теста по имени файла-источника (без жёсткой привязки к структуре)."""
    stem = Path(src_path).stem
    candidates = list(tests_root.rglob(f"test_{stem}*.py"))
    if not candidates:
        return None
    src_parts = set(Path(src_path).parts)

    def score(p: Path) -> int:
        return len(set(p.parts) & src_parts)

    candidates.sort(key=score, reverse=True)
    return candidates[0]


def build_file_report(
    src_path: str,
    file_data: dict,
    src_root: Path,
    tests_root: Path | None,
    context: int,
) -> str | None:
    summary = file_data["summary"]
    if summary["percent_covered"] >= 100:
        return None

    full_path = src_root / src_path
    if not full_path.exists():
        return None
    source_lines = full_path.read_text(encoding="utf-8").splitlines()
    scopes = build_scope_index("\n".join(source_lines))

    missing_lines = set(file_data.get("missing_lines", []))
    missing_branches = file_data.get("missing_branches", [])

    gap_lines: set[int] = set(missing_lines)
    for frm, to in missing_branches:
        gap_lines.add(frm)
        if to > 0:
            gap_lines.add(to)

    ranges = merge_ranges(sorted(gap_lines))

    out = [f"## `{src_path}`"]
    stmt_pct = summary["percent_covered_display"]
    branch_pct = summary.get("percent_branches_covered_display")
    header = f"строки: {stmt_pct}%"
    if branch_pct is not None:
        header += f", ветки: {branch_pct}%"
    out.append(
        f"_{header}, непокрытых строк: {len(missing_lines)}, непокрытых веток: {len(missing_branches)}_"
    )

    test_file = find_test_file(src_path, tests_root) if tests_root else None
    if test_file:
        out.append(f"Связанный тест: `{test_file}`")
    else:
        out.append("Связанный тест: **не найден автоматически — проверить вручную**")
    out.append("")

    for start, end in ranges:
        qualname = find_enclosing(scopes, start) or "(модульный уровень)"
        snippet_start = max(1, start - context)
        snippet_end = min(len(source_lines), end + context)

        out.append(f"### `{qualname}` — строки {start}-{end}")
        out.append("```python")
        for i in range(snippet_start, snippet_end + 1):
            line_text = source_lines[i - 1] if i - 1 < len(source_lines) else ""
            marker = ""
            if i in missing_lines:
                marker = "  # НЕ ПОКРЫТО"
                if "raise" in line_text or "except" in line_text:
                    marker = "  # НЕ ПОКРЫТО — путь ошибки (raise/except)"
            out.append(f"{i:>5}: {line_text}{marker}")
        out.append("```")

        branch_notes = [
            f"- ветка {frm} → {to if to > 0 else 'выход из функции'} ни разу не выполнялась в тестах"
            for frm, to in missing_branches
            if start <= frm <= end or (to > 0 and start <= to <= end)
        ]
        if branch_notes:
            out.append("\n".join(branch_notes))
        out.append("")

    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", default="coverage.json", type=Path)
    parser.add_argument("--src-root", default=".", type=Path)
    parser.add_argument("--tests-root", default="tests", type=Path)
    parser.add_argument("--out", default="coverage_gaps.md", type=Path)
    parser.add_argument("--context", default=2, type=int, help="строк контекста вокруг пропуска")
    args = parser.parse_args()

    data = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    tests_root = args.tests_root if args.tests_root.exists() else None

    files = data["files"]
    # худшие по покрытию — первыми, чтобы модель/человек начинали с самого важного
    ordered = sorted(files.items(), key=lambda kv: kv[1]["summary"]["percent_covered"])

    sections = []
    for src_path, file_data in ordered:
        section = build_file_report(src_path, file_data, args.src_root, tests_root, args.context)
        if section:
            sections.append(section)

    totals = data["totals"]
    header = (
        f"# Отчёт о пробелах в покрытии\n\n"
        f"Всего: строки {totals['percent_covered_display']}%, "
        f"ветки {totals.get('percent_branches_covered_display', 'н/д')}%. "
        f"Файлов с пробелами: {len(sections)} из {len(files)}.\n\n"
        "Ниже — только код вокруг непокрытых строк/веток, отсортировано от "
        "худшего покрытия к лучшему. Особое внимание — пометкам "
        "`путь ошибки (raise/except)`.\n"
    )

    args.out.write_text(header + "\n---\n\n" + "\n---\n\n".join(sections), encoding="utf-8")
    print(f"Готово: {args.out} ({len(sections)} файлов с пробелами)")


if __name__ == "__main__":
    main()
