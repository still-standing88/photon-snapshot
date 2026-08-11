"""Builds ``lang/<code>/LC_MESSAGES/photon_snapshot.po`` for every language
in ``translations_data.TRANSLATIONS`` from ``lang/photon_snapshot.pot``
(run ``extract_strings.py`` first if the source has changed) plus the
hand-written translations in ``translations_data.py``.

Reports any msgid missing a translation for a given language (so gaps are
caught explicitly instead of silently falling back to English at runtime).

Usage:
    python scripts/extract_strings.py   # refresh the .pot, if needed
    python scripts/build_po.py
    python scripts/compile_lang.py      # .po -> .mo
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translations_data import TRANSLATIONS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POT = ROOT / "lang" / "photon_snapshot.pot"

MSGID_RE = re.compile(r'^msgid "(.*)"$')


def unescape(s: str) -> str:
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")


def escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def extract_msgids(pot_text: str) -> list[str]:
    msgids = []
    for line in pot_text.splitlines():
        m = MSGID_RE.match(line)
        if m:
            msgids.append(unescape(m.group(1)))
    return msgids[1:]  # drop the header entry (empty msgid)


def build_po(language: str, msgids: list[str], header_lang: str) -> tuple[str, list[str]]:
    catalog = TRANSLATIONS[language]
    missing = []
    lines = [
        'msgid ""',
        'msgstr ""',
        '"Project-Id-Version: Photon Snapshot\\n"',
        f'"Language: {header_lang}\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        "",
    ]
    for msgid in msgids:
        translation = catalog.get(msgid)
        if translation is None:
            missing.append(msgid)
            translation = msgid  # fall back to English rather than emit blank
        lines.append(f'msgid "{escape(msgid)}"')
        lines.append(f'msgstr "{escape(translation)}"')
        lines.append("")
    return "\n".join(lines), missing


def main():
    pot_text = POT.read_text(encoding="utf-8")
    msgids = extract_msgids(pot_text)
    print(f"{len(msgids)} msgids in template")

    header_langs = {"fr": "fr", "es": "es", "ar": "ar"}
    any_missing = False
    for code in TRANSLATIONS:
        po_text, missing = build_po(code, msgids, header_langs[code])
        out_dir = ROOT / "lang" / code / "LC_MESSAGES"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "photon_snapshot.po"
        out_path.write_text(po_text, encoding="utf-8")
        print(f"{code}: wrote {out_path.relative_to(ROOT)} ({len(msgids) - len(missing)}/{len(msgids)} translated)")
        if missing:
            any_missing = True
            print(f"  MISSING ({len(missing)}):")
            for m in missing:
                print(f"    - {m!r}")

    if any_missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
