"""Default key bindings for the akeyconfig system, grouped by section.

Mirrors playForm's ``app_constance/default_keys.py`` shape (a dict of
section -> {action: sequence}) but scoped to what an image viewer/editor
actually needs - no OS-wide global hotkeys, since nothing here needs to
fire while the app is in the background.
"""

key_dict = {
    "Main Window": {
        "Open file": "Ctrl+O",
        "Open folder": "Ctrl+Shift+O",
        "Save": "Ctrl+S",
        "Save As": "Ctrl+Shift+S",
        "Undo": "Ctrl+Z",
        "Redo": "Ctrl+Y",
        "Reset to Original": "Ctrl+R",
        "Toggle Explorer": "Ctrl+E",
        "Focus Explorer": "Alt+E",
        "Focus Viewer": "Alt+V",
        "Zoom In": "Ctrl+=",
        "Zoom Out": "Ctrl+-",
        "Fit to Window": "Ctrl+0",
        "Actual Size": "Ctrl+1",
        "Preferences": "Ctrl+,",
        "Hotkeys Dialog": "F4",
        "Check for Updates": "F2",
        "Minimize to Tray": "Ctrl+H",
        "Exit": "Alt+X",
        "Next Pane": "F6",
        "Previous Pane": "Shift+F6",
    },
    "Explorer": {
        "Search files": "Ctrl+F",
        "Go Up": "Backspace",
        "Refresh": "F5",
        "Open Selected": "Return",
        "Add to Favorites": "Ctrl+D",
        "Add Folder to Library": "Ctrl+Shift+L",
    },
    "Viewer": {
        "Toggle Grid Overlay": "G",
        "Toggle Ruler Overlay": "R",
        "Toggle Pixel Info": "I",
        "Toggle Crop Mode": "C",
        "Toggle Drawing Mode": "D",
        "Clear Overlays": "Alt+C",
        "Cancel/Escape Mode": "Escape",
    },
}
