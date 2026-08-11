"""Options menu -> Preferences dialog: language, theme, and general
behavior toggles, all backed by :mod:`app_config.prefs` (SQLite)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from app_config.prefs import prefs
from utilities.i18n import SUPPORTED_LANGUAGES


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Preferences"))
        self.setAccessibleName(_("Preferences dialog"))
        self.setModal(True)
        self.resize(420, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.language_combo = QComboBox()
        self.language_combo.setAccessibleName(_("Application language"))
        self.language_combo.addItem(_("System Default"), "")
        for code, name in SUPPORTED_LANGUAGES.items():
            self.language_combo.addItem(name, code)
        current_lang = prefs.get("language", "")
        idx = self.language_combo.findData(current_lang)
        self.language_combo.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow(_("Language:"), self.language_combo)

        self.theme_combo = QComboBox()
        self.theme_combo.setAccessibleName(_("Application theme"))
        self.theme_combo.addItem(_("Dark"), "dark")
        self.theme_combo.addItem(_("Light"), "light")
        idx = self.theme_combo.findData(prefs.get("theme", "dark"))
        self.theme_combo.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow(_("Theme:"), self.theme_combo)

        layout.addLayout(form)

        self.check_updates_cb = QCheckBox(_("Check for updates on startup"))
        self.check_updates_cb.setChecked(bool(prefs.get("check_for_updates_on_startup", True)))
        layout.addWidget(self.check_updates_cb)

        self.minimize_to_tray_cb = QCheckBox(_("Minimize to tray when window is closed"))
        self.minimize_to_tray_cb.setChecked(bool(prefs.get("minimize_to_tray_on_close", False)))
        layout.addWidget(self.minimize_to_tray_cb)

        self.confirm_overwrite_cb = QCheckBox(_("Confirm before overwriting files"))
        self.confirm_overwrite_cb.setChecked(bool(prefs.get("confirm_on_overwrite", True)))
        layout.addWidget(self.confirm_overwrite_cb)

        restart_note = QLabel(_("Changing the language requires restarting the application."))
        restart_note.setWordWrap(True)
        restart_note.setStyleSheet("color: #999999; font-size: 11px;")
        layout.addWidget(restart_note)

        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        previous_language = prefs.get("language", "")
        new_language = self.language_combo.currentData()

        prefs["language"] = new_language
        prefs["theme"] = self.theme_combo.currentData()
        prefs["check_for_updates_on_startup"] = self.check_updates_cb.isChecked()
        prefs["minimize_to_tray_on_close"] = self.minimize_to_tray_cb.isChecked()
        prefs["confirm_on_overwrite"] = self.confirm_overwrite_cb.isChecked()

        if new_language != previous_language:
            QMessageBox.information(
                self, _("Restart Required"),
                _("Please restart {app} for the language change to take effect.").format(
                    app=_("Photon Snapshot")
                ),
            )

        super().accept()
