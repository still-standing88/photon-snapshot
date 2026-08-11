"""Small shared widgets. ``TabableLabel`` is the accessibility building
block used everywhere a QLabel shows information (image dimensions, zoom
percentage, status text, pixel color under cursor, ...): a plain QLabel is
never focusable, so a screen-reader/keyboard user can't reach it at all.
Giving it ``TabFocus`` and an accessible name/description makes every
info-bearing label reachable by Tab, per the accessibility requirements of
the snapshot rewrite. Pattern taken from playForm's
``gui_controls/common_controls.py`` (``TextLabel``).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class TabableLabel(QLabel):
    """A QLabel that participates in Tab-order navigation and exposes an
    accessible name derived from its text (or a custom one)."""

    def __init__(self, text: str = "", parent=None, accessible_name: str | None = None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(accessible_name or text)

    def setText(self, text: str):
        super().setText(text)
        if not self.accessibleDescription():
            self.setAccessibleName(text)
