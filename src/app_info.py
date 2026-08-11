"""Central application identity, mirrored to environment variables so any
module (including ones that can't import this one directly, e.g. subprocess
helpers) can read them via ``os.environ``. Pattern adapted from playForm's
``app_info.py``.
"""

import os


APP_NAME = "Photon Snapshot"
APP_DESCRIPTION = "A modern, accessible image viewer and editor."
APP_VERSION = "1.1.0"
APP_PUBLISHER = "still-standing88"
APP_AUTHOR = "still-standing88"
APP_LICENSE = "MIT"
APP_COPYRIGHT = "Copyright © 2026 still-standing88"

APP_WEBSITE = "https://github.com/still-standing88/photon-snapshot"
APP_GITHUB_REPO = "still-standing88/photon-snapshot"  # owner/repo
APP_SUPPORT_EMAIL = ""

# Folder name under the user's home directory where all app data (SQLite
# database, logs, screenshots, lang overrides, ...) is stored.
APP_DATA_DIRNAME = ".photon-snapshot"


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
