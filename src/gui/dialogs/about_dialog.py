"""Help/About dialog showing app identity from :mod:`app_info`."""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
from PySide6.QtCore import QUrl

import app_info


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("About {app}").format(app=app_info.APP_NAME))
        self.setAccessibleName(_("About dialog"))
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        title = QLabel(f"<h2>{app_info.APP_NAME}</h2>")
        layout.addWidget(title)

        version = os.environ.get(app_info.ENV_APP_VERSION, app_info.APP_VERSION)
        info = QLabel(
            _("Version {version}<br>{description}<br><br>{copyright}<br>License: {license}").format(
                version=version,
                description=app_info.APP_DESCRIPTION,
                copyright=app_info.APP_COPYRIGHT,
                license=app_info.APP_LICENSE,
            )
        )
        info.setWordWrap(True)
        info.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        info.setAccessibleName(_("Application information"))
        layout.addWidget(info)

        # Publisher/author/support rows, matching what playForm's About dialog
        # shows. These were absent here, so app_info.APP_PUBLISHER and
        # APP_AUTHOR had no route to the UI at all. Rendered as one focusable
        # label rather than a QGridLayout of label/value pairs so a screen
        # reader reads the block in a single stop instead of six.
        detail_rows = [
            (_("Publisher"), os.environ.get(app_info.ENV_APP_PUBLISHER, app_info.APP_PUBLISHER)),
            (_("Author"), os.environ.get(app_info.ENV_APP_AUTHOR, app_info.APP_AUTHOR)),
            (_("Support"), os.environ.get(app_info.ENV_APP_SUPPORT_EMAIL, app_info.APP_SUPPORT_EMAIL)),
        ]
        detail_html = "<br>".join(
            f"<b>{label}:</b> {value}" for label, value in detail_rows if value
        )
        if detail_html:
            details = QLabel(detail_html)
            details.setWordWrap(True)
            details.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            details.setAccessibleName(_("Publisher information"))
            layout.addWidget(details)

        link = QLabel(f'<a href="{app_info.APP_WEBSITE}">{app_info.APP_WEBSITE}</a>')
        link.setOpenExternalLinks(True)
        link.setAccessibleName(_("Project website link"))
        layout.addWidget(link)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
