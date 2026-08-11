"""gettext-based translation loading, adapted from playForm's
``utilities/i18n.py``.

Every user-facing string in the app is wrapped in ``_()`` (installed as a
builtin by :func:`install_translation`, called once at startup before any
GUI module is imported). Catalog sources live in ``lang/<code>/LC_MESSAGES/
photon_snapshot.po`` and are compiled to ``.mo`` by
``scripts/compile_lang.py`` (see that script for how the four shipped
languages - English, Arabic, French, Spanish - are built and verified).
"""

from __future__ import annotations

import gettext
from pathlib import Path

from utilities.functions import get_lang_dir

DOMAIN = "photon_snapshot"

# Languages shipped with the app out of the box.
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ar": "العربية",  # العربية
    "fr": "Français",
    "es": "Español",
}

RTL_LANGUAGES = {"ar"}


def get_locale_dir() -> Path:
    return Path(get_lang_dir())


def _language_candidates(language: str | None) -> list[str] | None:
    if not language:
        return None
    raw = str(language).strip()
    if not raw:
        return None

    candidates: list[str] = []
    base = raw.replace("-", "_")
    for candidate in (raw, raw.lower(), base, base.lower(), base.split("_", 1)[0], base.split("_", 1)[0].lower()):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def install_translation(language: str | None = None, domain: str = DOMAIN):
    """Install ``_()`` as a builtin. Falls back to an identity translation
    (returns the msgid unchanged) when no compiled catalog is found for the
    requested language - e.g. running from source before
    ``scripts/compile_lang.py`` has been run, or for English itself, which
    has no .mo (the source strings *are* English)."""
    localedir = str(get_locale_dir())
    languages = _language_candidates(language)
    translation = gettext.translation(domain, localedir=localedir, languages=languages, fallback=True)
    translation.install()
    return translation


def is_rtl(language: str | None) -> bool:
    if not language:
        return False
    return language.split("_", 1)[0].lower() in RTL_LANGUAGES
