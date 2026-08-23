"""Central application identity, mirrored to environment variables so any
module (including ones that can't import this one directly, e.g. subprocess
helpers) can read them via ``os.environ``. Pattern adapted from playForm's
``app_info.py``.
"""

import os


# Version bumped in one place only when building from source. Release builds
# override it from the git tag: build.py --version=X.Y.Z writes
# src/_build_version.py (gitignored, generated) and the import below picks it
# up, so a binary produced by the tag-triggered CI workflow self-reports the
# version that was actually released. Without that, the compiled app reported
# this literal forever and the update checker saw every release as "newer"
# than itself on every launch.
_FALLBACK_VERSION = "1.1.0"

try:
    from _build_version import BUILD_VERSION as _BUILD_VERSION
except ImportError:  # running from source, or built without --version
    _BUILD_VERSION = None


APP_NAME = "Photon Snapshot"
APP_DESCRIPTION = "A modern, accessible image viewer and editor."
APP_VERSION = _BUILD_VERSION or _FALLBACK_VERSION
# Numeric version build.py falls back to for the Windows version resource when
# the build version isn't a release number (CI's non-tag "dev-<date>-<sha>").
APP_VERSION_FALLBACK = _FALLBACK_VERSION
# Publisher/author/support match playForm's - same developer, same imprint.
# The license differs deliberately: see ./LICENSE (MIT here, GPL-3.0 there).
APP_PUBLISHER = "Joybytes"
APP_AUTHOR = "Still Standing"
APP_LICENSE = "MIT"
APP_COPYRIGHT = "Copyright © 2026 Still Standing"

APP_WEBSITE = "https://github.com/still-standing88/photon-snapshot"
APP_GITHUB_REPO = "still-standing88/photon-snapshot"  # owner/repo
APP_SUPPORT_EMAIL = "support@joybytes.dev"

# Folder name under the user's home directory where all app data (SQLite
# database, logs, screenshots, lang overrides, ...) is stored.
APP_DATA_DIRNAME = ".photon-snapshot"


# Deliberately prefixed, unlike playForm's bare APP_NAME/APP_VERSION/...:
# these leak into the environment of anything the app spawns, and bare names
# are easy for a child process to collide with. Every read goes through the
# ENV_* constants below, so the prefix costs nothing.
ENV_APP_NAME = "PHOTON_APP_NAME"
ENV_APP_DESCRIPTION = "PHOTON_APP_DESCRIPTION"
ENV_APP_VERSION = "PHOTON_APP_VERSION"
ENV_APP_PUBLISHER = "PHOTON_APP_PUBLISHER"
ENV_APP_AUTHOR = "PHOTON_APP_AUTHOR"
ENV_APP_LICENSE = "PHOTON_APP_LICENSE"
ENV_APP_COPYRIGHT = "PHOTON_APP_COPYRIGHT"
ENV_APP_WEBSITE = "PHOTON_APP_WEBSITE"
ENV_APP_GITHUB_REPO = "PHOTON_APP_GITHUB_REPO"
ENV_APP_SUPPORT_EMAIL = "PHOTON_APP_SUPPORT_EMAIL"


def setup_env() -> None:
    os.environ[ENV_APP_NAME] = APP_NAME
    os.environ[ENV_APP_DESCRIPTION] = APP_DESCRIPTION
    os.environ[ENV_APP_VERSION] = APP_VERSION
    os.environ[ENV_APP_PUBLISHER] = APP_PUBLISHER
    os.environ[ENV_APP_AUTHOR] = APP_AUTHOR
    os.environ[ENV_APP_LICENSE] = APP_LICENSE
    os.environ[ENV_APP_COPYRIGHT] = APP_COPYRIGHT
    os.environ[ENV_APP_WEBSITE] = APP_WEBSITE
    os.environ[ENV_APP_GITHUB_REPO] = APP_GITHUB_REPO
    os.environ[ENV_APP_SUPPORT_EMAIL] = APP_SUPPORT_EMAIL
