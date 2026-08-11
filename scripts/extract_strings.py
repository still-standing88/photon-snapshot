"""Extracts every ``_("...")`` msgid used across ``src/`` into
``lang/photon_snapshot.pot`` (a gettext PO template).

Uses Python's ``ast`` module rather than a regex, so it can't be fooled by
``_()`` calls split across lines or containing escaped quotes.

``_()`` calls whose argument isn't a plain string literal (a variable, an
f-string, ...) can't become a msgid and are skipped - but unlike a plain
skip, this script treats it as an error: such a call silently never gets
translated at runtime (gettext's ``_()`` just returns whatever was passed
in when there's no matching msgid), so it's a real bug, not just a gap in
this extractor. Any such call site is printed as a warning and the script
exits non-zero; fix it by writing out each ``_("literal")`` call directly
instead of looping over a (key, label) list and calling ``_(label)`` on the
loop variable (see ``gui/overlay_panel.py``'s shape combo for the pattern
to follow, and its comment for how this exact mistake shipped once).

A dynamic ``_()`` lookup is occasionally legitimate - e.g. the Hotkeys
dialog does ``_(section)``/``_(action)`` to translate akeyconfig section/
action names that come from ``app_constance.default_keys.key_dict`` at
runtime. Two things make that safe rather than a repeat of the bug above:
(1) :func:`extract_key_config_labels` below pulls those exact strings
directly from ``key_dict`` as real msgids, so they *are* in the catalog
despite never appearing as literal ``_("...")`` calls; (2) the call site
is marked with a trailing ``# i18n-dynamic: ok`` comment, which silences
the warning for that line specifically - use it only when you've done the
equivalent of (1) for whatever dynamic value is involved.

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
DYNAMIC_OK_MARKER = "i18n-dynamic: ok"


class Extractor(ast.NodeVisitor):
    def __init__(self, filename: str, source_lines: list[str]):
        self.filename = filename
        self.source_lines = source_lines
        self.found: list[tuple[str, int]] = []
        # _("...") calls whose argument isn't a plain string literal - these
        # silently never get translated at runtime (gettext's _() just
        # returns whatever was passed in when there's no matching msgid),
        # so this is a real bug class, not just an extraction gap. It has
        # already shipped once (a combo box built by looping over a
        # (key, label) list and calling _(label) on the loop variable) -
        # flagging it here means the next occurrence fails the build
        # instead of silently shipping un-translatable text. Lines marked
        # `# i18n-dynamic: ok` are exempted (see module docstring).
        self.non_literal_calls: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call):
        is_underscore_call = isinstance(node.func, ast.Name) and node.func.id == "_"
        if is_underscore_call and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.found.append((first.value, node.lineno))
            elif not self._is_marked_ok(node.lineno):
                self.non_literal_calls.append((node.lineno, ast.dump(first)))
        self.generic_visit(node)

    def _is_marked_ok(self, lineno: int) -> bool:
        if 1 <= lineno <= len(self.source_lines):
            return DYNAMIC_OK_MARKER in self.source_lines[lineno - 1]
        return False


def extract_from_file(path: Path) -> tuple[list[tuple[str, int]], list[tuple[int, str]]]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        print(f"WARNING: could not parse {path}: {e}", file=sys.stderr)
        return [], []
    extractor = Extractor(str(path), source.splitlines())
    extractor.visit(tree)
    return extractor.found, extractor.non_literal_calls


def extract_key_config_labels() -> list[tuple[str, str]]:
    """Section/action names from app_constance.default_keys.key_dict are
    looked up dynamically at runtime (see the module docstring) - pull them
    in directly rather than requiring a dummy list of literal _() calls
    somewhere (which would need `_` to already be installed at whatever
    point that module first gets imported, a fragile ordering requirement
    this avoids entirely)."""
    sys.path.insert(0, str(SRC))
    from app_constance import default_keys  # noqa: PLC0415 - deliberately deferred, see above

    location = "src/app_constance/default_keys.py:key_dict"
    result: list[tuple[str, str]] = []
    for section, actions in default_keys.key_dict.items():
        result.append((section, location))
        for action in actions:
            result.append((action, location))
    return result


def escape(msgid: str) -> str:
    return msgid.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main():
    entries: dict[str, list[str]] = {}  # msgid -> [ "file:line", ... ]
    warnings: list[str] = []

    for path in sorted(SRC.rglob("*.py")):
        if path.name in EXCLUDE_NAMES or "__pycache__" in path.parts:
            continue
        found, non_literal = extract_from_file(path)
        for msgid, lineno in found:
            location = f"{path.relative_to(ROOT).as_posix()}:{lineno}"
            entries.setdefault(msgid, []).append(location)
        for lineno, arg_repr in non_literal:
            rel = path.relative_to(ROOT).as_posix()
            warnings.append(f"{rel}:{lineno}: _() called with a non-literal argument ({arg_repr}) - will never be translated")

    for msgid, location in extract_key_config_labels():
        entries.setdefault(msgid, []).append(location)

    if warnings:
        print(f"WARNING: {len(warnings)} _() call(s) with a non-literal argument (see above/below) -", file=sys.stderr)
        for w in warnings:
            print(f"  {w}", file=sys.stderr)

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

    if warnings:
        sys.exit(1)


if __name__ == "__main__":
    main()
