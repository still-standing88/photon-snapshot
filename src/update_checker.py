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
import re

from PySide6.QtCore import QObject, QTimer, QUrl, Slot, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

import app_info
from log_handler import get_logger

_CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000  # 12 hours
_CHECK_DELAY_MS = 3_000


def _strip_v(tag: str) -> str:
    return tag.lstrip("vV")


def _parse_version(text: str) -> tuple[int, ...] | None:
    """Leading dotted-numeric part of a version/tag, or None if there isn't one.

    Tolerates the tag shapes GitHub actually gets used with - ``v1.2.0``,
    ``1.2``, ``1.2.0-beta.1``, ``1.2.0rc1``. The old implementation did a bare
    ``int()`` over ``tag.split(".")`` inside a try/except that returned False,
    so any pre-release or suffixed tag was silently treated as "not newer" and
    the update was never offered.
    """
    match = re.match(r"\d+(?:\.\d+)*", _strip_v(text).strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(0).split("."))


def _is_newer(remote_tag: str, local_version: str) -> bool:
    remote = _parse_version(remote_tag)
    local = _parse_version(local_version)
    if remote is None or local is None:
        # Most likely a dev build, whose version is "dev-<date>-<sha>" rather
        # than a release number. Declining to compare is the right answer, but
        # say so in the log rather than looking like "already up to date".
        get_logger().info(
            "Skipping update comparison: cannot parse %s",
            "release tag %r" % remote_tag if remote is None else "local version %r" % local_version,
        )
        return False
    # Zero-pad to equal length so 1.2 and 1.2.0 compare equal rather than
    # (1, 2) < (1, 2, 0). Comparing only the numeric core also means a
    # pre-release tag never counts as newer than the same released version.
    width = max(len(remote), len(local))
    remote += (0,) * (width - len(remote))
    local += (0,) * (width - len(local))
    return remote > local


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
    no_releases = Signal()
    check_error = Signal(str)

    _singleton: "UpdateChecker | None" = None

    @classmethod
    def instance(cls, parent=None, *, background: bool = False) -> "UpdateChecker":
        if cls._singleton is None:
            cls._singleton = cls(parent, background=background)
            return cls._singleton

        checker = cls._singleton
        # Help -> Check for Updates can run before or after the startup checker
        # exists. Either way the dialogs should be parented to the widget that
        # asked, not to whichever window happened to construct the singleton.
        if parent is not None:
            checker._parent_widget = parent
        if background:
            checker._start_background_checks()
        return checker

    def __init__(self, parent=None, *, background: bool = False):
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

        if background:
            self._start_background_checks()

    def _start_background_checks(self):
        """Arm the periodic and startup checks.

        Previously __init__ started both unconditionally, so opening
        Help -> Check for Updates with "check on startup" turned *off*
        constructed the singleton and quietly signed the user up for a poll
        every 12 hours plus another check three seconds later. Background
        polling now only happens when startup checking asked for it.
        """
        if self._timer.isActive():
            return
        self._timer.start()
        QTimer.singleShot(_CHECK_DELAY_MS, lambda: self.check_now(silent=True))

    def check_now(self, *, silent: bool = True):
        if not self._repo:
            if not silent:
                QMessageBox.information(
                    self._parent_widget, _("Updates Unavailable"),
                    _("This build has no update source configured."),
                )
            return
        if self._reply is not None and not self._reply.isFinished():
            # A check is already on the wire. If the user asked for this one,
            # promote the in-flight request to non-silent so they get an answer
            # instead of the click doing nothing at all.
            if not silent:
                self._silent = False
            return

        self._silent = silent
        url = f"https://api.github.com/repos/{self._repo}/releases/latest"
        request = QNetworkRequest(QUrl(url))
        request.setHeader(
            QNetworkRequest.KnownHeaders.UserAgentHeader,
            f"{os.environ.get(app_info.ENV_APP_NAME, app_info.APP_NAME)}/{self._version}",
        )
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
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
            if not isinstance(release, dict):
                release = {}

            # These three outcomes used to collapse into one "No releases have
            # been published for this application yet." message, so a user with
            # no network - or behind a proxy, or rate-limited - was told the
            # project had never shipped a release.
            if http_status is None:
                self._fail(
                    reply.errorString() or _("no response"),
                    _("Could Not Check for Updates"),
                    _("Could not reach GitHub to check for updates.\n\n{detail}").format(
                        detail=reply.errorString() or _("The network is unreachable."),
                    ),
                )
                return

            if http_status == 404:
                self.no_releases.emit()
                if not self._silent:
                    QMessageBox.information(
                        self._parent_widget, _("No Releases Found"),
                        _("No releases have been published for {app} yet.").format(
                            app=os.environ.get(app_info.ENV_APP_NAME, app_info.APP_NAME),
                        ),
                    )
                return

            if http_status != 200 or "tag_name" not in release:
                detail = release.get("message") or reply.errorString() or _("HTTP {status}").format(status=http_status)
                self._fail(
                    detail,
                    _("Could Not Check for Updates"),
                    _("GitHub returned an unexpected response.\n\n{detail}").format(detail=detail),
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

    def _fail(self, detail: str, title: str, message: str):
        self.check_error.emit(detail)
        get_logger().warning("Update check failed: %s", detail)
        if not self._silent:
            QMessageBox.warning(self._parent_widget, title, message)
