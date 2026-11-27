"""GitHub-releases-based update checker, adapted from playForm's
``update_checker.py``. Photon Snapshot ships as a single installer/zip
rather than playForm's manifest+zip self-patching scheme, so this version
checks for a newer release and offers to open its GitHub release page in
the browser, instead of silently downloading and swapping binaries - safer
and far less code for a small image-editor install.
"""

from __future__ import annotations

import json
import os
import platform as _platform_mod

from PySide6.QtCore import QObject, QTimer, QUrl, Slot, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

import app_info

_CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000  # 12 hours
_CHECK_DELAY_MS = 3_000


def _strip_v(tag: str) -> str:
    return tag.lstrip("vV")


def _version_tuple(version_str: str) -> tuple:
    """Parse 'v1.2.3', '1.2.3-beta.1', '1.2.3+build' etc. into a numeric
    tuple, ignoring any pre-release/build suffix (a pre-release of X.Y.Z
    compares equal to X.Y.Z here - close enough for release checking)."""
    core = _strip_v(version_str).split("-", 1)[0].split("+", 1)[0]
    parts = []
    for piece in core.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _is_newer(remote_tag: str, local_version: str) -> bool:
    try:
        remote = _version_tuple(remote_tag)
        local = _version_tuple(local_version)
        # Zero-pad so e.g. 1.2 == 1.2.0 instead of comparing unequal lengths.
        width = max(len(remote), len(local))
        remote += (0,) * (width - len(remote))
        local += (0,) * (width - len(local))
        return remote > local
    except Exception:
        return False


class UpdateAvailableDialog(QDialog):
    def __init__(self, release: dict, parent=None):
        super().__init__(parent)
        self._release = release
        tag = release.get("tag_name", "")
        title = release.get("name") or tag
        self.setWindowTitle(_("Update Available - {title}").format(title=title))
        self.setAccessibleName(_("Update available dialog"))
        self.setModal(True)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        current = os.environ.get(app_info.ENV_APP_VERSION, app_info.APP_VERSION)
        header = QLabel(
            _("<b>A new version of {app} is available!</b><br>"
              "Your version: <b>{current}</b> -> New version: <b>{new}</b>").format(
                app=os.environ.get(app_info.ENV_APP_NAME, app_info.APP_NAME),
                current=current,
                new=_strip_v(tag),
            )
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setAccessibleName(_("Release notes"))
        notes.setMarkdown(release.get("body") or _("No release notes provided."))
        layout.addWidget(notes, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        later_btn = QPushButton(_("Later"))
        later_btn.clicked.connect(self.reject)
        btn_row.addWidget(later_btn)
        open_btn = QPushButton(_("Open Download Page"))
        open_btn.setDefault(True)
        open_btn.clicked.connect(self._open_page)
        btn_row.addWidget(open_btn)
        layout.addLayout(btn_row)

    def _open_page(self):
        url = self._release.get("html_url") or f"https://github.com/{app_info.APP_GITHUB_REPO}/releases"
        QDesktopServices.openUrl(QUrl(url))
        self.accept()


class UpdateChecker(QObject):
    update_available = Signal(dict)
    no_update = Signal()
    check_error = Signal(str)

    _singleton: "UpdateChecker | None" = None

    @classmethod
    def instance(cls, parent=None) -> "UpdateChecker":
        if cls._singleton is None:
            cls._singleton = cls(parent)
        return cls._singleton

    def __init__(self, parent=None):
        super().__init__(parent)
        self._repo = os.environ.get(app_info.ENV_APP_GITHUB_REPO, app_info.APP_GITHUB_REPO)
        self._version = os.environ.get(app_info.ENV_APP_VERSION, app_info.APP_VERSION)
        self._parent_widget: QWidget | None = parent
        self._silent = True

        self._nam = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(_CHECK_INTERVAL_MS)
        self._timer.timeout.connect(lambda: self.check_now(silent=True))
        self._timer.start()

        QTimer.singleShot(_CHECK_DELAY_MS, lambda: self.check_now(silent=True))

    def check_now(self, *, silent: bool = True):
        if not self._repo:
            return
        if self._reply is not None and not self._reply.isFinished():
            return

        self._silent = silent
        url = f"https://api.github.com/repos/{self._repo}/releases/latest"
        request = QNetworkRequest(QUrl(url))
        request.setHeader(
            QNetworkRequest.KnownHeaders.UserAgentHeader,
            f"{os.environ.get(app_info.ENV_APP_NAME, app_info.APP_NAME)}/{self._version}",
        )
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._on_api_reply)

    @Slot()
    def _on_api_reply(self):
        reply = self._reply
        if reply is None:
            return
        try:
            http_status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            data = bytes(reply.readAll()).decode("utf-8", errors="replace")
            try:
                release = json.loads(data)
            except json.JSONDecodeError:
                release = {}

            if reply.error() != QNetworkReply.NetworkError.NoError or not release or "tag_name" not in release:
                message = release.get("message") if isinstance(release, dict) else None
                message = message or reply.errorString() or _("HTTP {status}").format(status=http_status)
                self.check_error.emit(message)
                if not self._silent:
                    QMessageBox.information(
                        self._parent_widget, _("No Releases Found"),
                        _("No releases have been published for this application yet."),
                    )
                return

            tag = release["tag_name"]
            if _is_newer(tag, self._version):
                self.update_available.emit(release)
                UpdateAvailableDialog(release, self._parent_widget).exec()
            else:
                self.no_update.emit()
                if not self._silent:
                    QMessageBox.information(
                        self._parent_widget, _("No Update Available"),
                        _("{app} is up to date (version {version}).").format(
                            app=os.environ.get(app_info.ENV_APP_NAME, app_info.APP_NAME),
                            version=self._version,
                        ),
                    )
        finally:
            reply.deleteLater()
            self._reply = None
