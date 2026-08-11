"""Startup splash screen, ported from playForm's ``loading.py``."""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

import app_info


class LoadingSplash(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap(420, 260)
        pixmap.fill(QColor(30, 30, 30))

        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        painter.setFont(font)
        app_name = os.environ.get(app_info.ENV_APP_NAME, app_info.APP_NAME)
        painter.drawText(pixmap.rect().adjusted(0, -20, 0, -20), Qt.AlignmentFlag.AlignCenter, app_name)

        subtitle_font = QFont("Segoe UI", 10)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(0, 120, 212))
        painter.drawText(pixmap.rect().adjusted(0, 30, 0, 30), Qt.AlignmentFlag.AlignCenter, _("Loading..."))
        painter.end()

        super().__init__(pixmap)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)

    def update_message(self, message: str):
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor(200, 200, 200),
        )
        QApplication.processEvents()
