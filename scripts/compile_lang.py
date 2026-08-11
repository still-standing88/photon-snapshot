"""Compiles every ``lang/<code>/LC_MESSAGES/photon_snapshot.po`` into the
binary ``.mo`` catalog gettext actually loads at runtime (see
``utilities.i18n.install_translation``).

A minimal, dependency-free PO parser + GNU MO writer - the project doesn't
otherwise need Babel/polib, and the `msgfmt` CLI from GNU gettext isn't
guaranteed to be on a Windows dev machine's PATH, so this avoids requiring
either just to build the app's own catalogs.

Usage:
    python scripts/compile_lang.py
"""

from __future__ import annotations

import array
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANG_DIR = ROOT / "lang"


def unescape(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_po(text: str) -> dict[str, str]:
    """Very small PO parser: handles single- and multi-line quoted string
    concatenation for msgid/msgstr, which is all this project's generated
    .po files use (no plural forms, no msgctxt)."""
    entries: dict[str, str] = {}
    msgid_lines: list[str] = []
    msgstr_lines: list[str] = []
    mode = None  # "id" | "str" | None

    def flush():
        if msgid_lines:
            msgid = unescape("".join(msgid_lines))
            msgstr = unescape("".join(msgstr_lines))
            entries[msgid] = msgstr

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            flush()
            msgid_lines = [line[len("msgid "):].strip().strip('"')]
            msgstr_lines = []
            mode = "id"
        elif line.startswith("msgstr "):
            msgstr_lines = [line[len("msgstr "):].strip().strip('"')]
            mode = "str"
        elif line.startswith('"') and line.endswith('"'):
            content = line[1:-1]
            if mode == "id":
                msgid_lines.append(content)
            elif mode == "str":
                msgstr_lines.append(content)
    flush()
    return entries


def write_mo(entries: dict[str, str], out_path: Path):
    """GNU MO binary format writer - see
    https://www.gnu.org/software/gettext/manual/html_node/MO-Files.html
    """
    keys = sorted(k for k in entries.keys() if k != "")
    offsets = []
    ids = b""
    strs = b""

    # Header entry (empty msgid) carries catalog metadata; gettext expects
    # it present as the first string table entry.
    header_msgstr = entries.get("", "")
    all_keys = [""] + keys

    for key in all_keys:
        msgid_bytes = key.encode("utf-8")
        msgstr_bytes = (header_msgstr if key == "" else entries[key]).encode("utf-8")
        offsets.append((len(ids), len(msgid_bytes), len(strs), len(msgstr_bytes)))
        ids += msgid_bytes + b"\x00"
        strs += msgstr_bytes + b"\x00"

    keystart = 7 * 4 + 16 * len(all_keys)
    valuestart = keystart + len(ids)

    koffsets = []
    voffsets = []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    offsets_flat = koffsets + voffsets

    output = struct.pack(
        "Iiiiiii",
        0x950412DE,  # magic
        0,           # version
        len(all_keys),
        7 * 4,                          # offset of key table
        7 * 4 + len(all_keys) * 8,      # offset of value table
        0, 0,                           # hash table size, offset (unused)
    )
    output += array.array("i", offsets_flat).tobytes()
    output += ids
    output += strs

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(output)


def main():
    po_files = sorted(LANG_DIR.glob("*/LC_MESSAGES/photon_snapshot.po"))
    if not po_files:
        print("No .po files found under lang/ - run build_po.py first.", file=sys.stderr)
        sys.exit(1)

    for po_path in po_files:
        entries = parse_po(po_path.read_text(encoding="utf-8"))
        mo_path = po_path.with_suffix(".mo")
        write_mo(entries, mo_path)
        print(f"Compiled {po_path.relative_to(ROOT)} -> {mo_path.relative_to(ROOT)} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
