"""About dialog with the app's identity and project website."""

import os
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFrame, QGridLayout, QLabel, QVBoxLayout

import app_info


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("About {app}").format(app=app_info.APP_NAME))
        self.setAccessibleName(_("About dialog"))
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        title = QLabel(app_info.APP_NAME)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        version = os.environ.get(app_info.ENV_APP_VERSION, app_info.APP_VERSION)
        version_label = QLabel(_("Version {version}").format(version=version))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        layout.addWidget(version_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        description = QLabel(
            _("An accessible, cross-platform image viewer and editor with customizable hotkeys.")
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        description.setAccessibleName(_("Application information"))
        layout.addWidget(description)
        layout.addSpacing(4)

        website = escape(app_info.APP_WEBSITE)
        link = QLabel(f'<a href="{website}">GitHub</a>')
        link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        link.setOpenExternalLinks(True)
        link.setAccessibleName(_("Project website link"))

        details = QGridLayout()
        details.setColumnStretch(1, 1)
        layout.addLayout(details)
        for row, (caption, value) in enumerate((
            (_("Publisher"), QLabel(app_info.APP_PUBLISHER)),
            (_("License"), QLabel(app_info.APP_LICENSE)),
            (_("Copyright"), QLabel(app_info.APP_COPYRIGHT)),
            (_("Website"), link),
        )):
            label = QLabel(f"<b>{escape(caption)}</b>")
            value.setWordWrap(True)
            if value is not link:
                value.setFocusPolicy(Qt.FocusPolicy.TabFocus)
                value.setAccessibleName(f"{caption}: {value.text()}")
            details.addWidget(label, row, 0, Qt.AlignmentFlag.AlignTop)
            details.addWidget(value, row, 1)

        layout.addSpacing(8)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(_("Close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
