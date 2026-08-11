"""Extracts every ``_("...")`` msgid used across ``src/`` into
``lang/photon_snapshot.pot`` (a gettext PO template).

Uses Python's ``ast`` module rather than a regex, so it can't be fooled by
``_()`` calls split across lines or containing escaped quotes - and it
skips ``_()`` calls whose argument isn't a plain string literal (an f-string
or a variable), which can't become a msgid anyway and would need the
surrounding code restructured to use ``.format()`` instead (as the rest of
the app already does).

Usage:
    python scripts/extract_strings.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "lang" / "photon_snapshot.pot"

EXCLUDE_NAMES = {"resources_rc.py"}


class Extractor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.found: list[tuple[str, int]] = []

    def visit_Call(self, node: ast.Call):
        is_underscore_call = isinstance(node.func, ast.Name) and node.func.id == "_"
        if is_underscore_call and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.found.append((first.value, node.lineno))
        self.generic_visit(node)


def extract_from_file(path: Path) -> list[tuple[str, int]]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        print(f"WARNING: could not parse {path}: {e}", file=sys.stderr)
        return []
    extractor = Extractor(str(path))
    extractor.visit(tree)
    return extractor.found


def escape(msgid: str) -> str:
    return msgid.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main():
    entries: dict[str, list[str]] = {}  # msgid -> [ "file:line", ... ]

    for path in sorted(SRC.rglob("*.py")):
        if path.name in EXCLUDE_NAMES or "__pycache__" in path.parts:
            continue
        for msgid, lineno in extract_from_file(path):
            location = f"{path.relative_to(ROOT).as_posix()}:{lineno}"
            entries.setdefault(msgid, []).append(location)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write(
            'msgid ""\n'
            'msgstr ""\n'
            '"Project-Id-Version: Photon Snapshot\\n"\n'
            '"MIME-Version: 1.0\\n"\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n'
            '"Content-Transfer-Encoding: 8bit\\n"\n'
            "\n"
        )
        for msgid in sorted(entries.keys(), key=str.lower):
            for location in entries[msgid]:
                f.write(f"#: {location}\n")
            f.write(f'msgid "{escape(msgid)}"\n')
            f.write('msgstr ""\n\n')

    print(f"Extracted {len(entries)} unique strings to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
