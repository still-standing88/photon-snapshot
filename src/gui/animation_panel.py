"""Model-backed frame strip with scoped keyboard controls."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListView, QPushButton, QLabel, QSpinBox, QComboBox, QCheckBox, QAbstractItemView, QMenu
from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QItemSelectionModel, Signal, QSignalBlocker, QSize, QMimeData, QTimer
import json
from PySide6.QtGui import QIcon, QAction
from app_config import key_config
from .managers.job_manager import FunctionJob
from core.utils import pil_to_qpixmap

class FrameModel(QAbstractListModel):
    reordered = Signal(list)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames = []
        self.icons = {}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frames)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.frames):
            return None
        frame = self.frames[index.row()]
        text = _('Frame {number} of {count}, {duration} milliseconds').format(number=index.row()+1, count=len(self.frames), duration=frame.duration_ms)
        if role == Qt.ItemDataRole.DisplayRole:
            return _('Frame {number} · {duration} ms').format(number=index.row()+1, duration=frame.duration_ms)
        if role in (Qt.ItemDataRole.AccessibleTextRole, Qt.ItemDataRole.ToolTipRole):
            return text
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(135, 100)
        if role == Qt.ItemDataRole.DecorationRole:
            return self.icons.get(frame.id)
        if role == Qt.ItemDataRole.UserRole:
            return frame.id

    def reset(self, frames):
        if [f.id for f in self.frames] == [f.id for f in frames]:
            self.frames = list(frames)
            if self.frames:
                self.dataChanged.emit(self.index(0), self.index(len(self.frames)-1))
            return
        self.beginResetModel()
        self.frames = list(frames)
        self.endResetModel()

    def flags(self, index):
        flags = super().flags(index)
        return flags | (Qt.ItemFlag.ItemIsDragEnabled if index.isValid() else Qt.ItemFlag.ItemIsDropEnabled)

    def mimeTypes(self):
        return ['application/x-photon-frames']

    def mimeData(self, indexes):
        mime = QMimeData()
        mime.setData(self.mimeTypes()[0], json.dumps([self.frames[i.row()].id for i in indexes]).encode())
        return mime

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.DropAction.IgnoreAction:
            return True
        if not data.hasFormat(self.mimeTypes()[0]):
            return False
        ids = json.loads(bytes(data.data(self.mimeTypes()[0])))
        current = [f.id for f in self.frames]
        if not set(ids) <= set(current):
            return False
        row = len(current) if row < 0 else row
        selected = [frame_id for frame_id in current if frame_id in ids]
        insertion = len([frame_id for frame_id in current[:row] if frame_id not in ids])
        remaining = [frame_id for frame_id in current if frame_id not in ids]
        self.reordered.emit(remaining[:insertion] + selected + remaining[insertion:])
        return True

class AnimationPanel(QWidget):
    import_requested = Signal()
    blank_requested = Signal()
    onion_changed = Signal(bool)

    def __init__(self, editor, playback, jobs, parent=None):
        super().__init__(parent)
        self.editor, self.playback, self.jobs = editor, playback, jobs
        self._refreshing = False
        self._thumbnail_key = None
        self._thumbnail_job = None
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.timeout.connect(self._commit_selection)
        self.setAccessibleName(_('Animation frames'))
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.previous = QPushButton(_('Previous'))
        self.next = QPushButton(_('Next'))
        self.play = QPushButton(_('Play'))
        for button in (self.previous, self.next, self.play):
            row.addWidget(button)
        self.position = QSpinBox()
        self.position.setAccessibleName(_('Frame position'))
        row.addWidget(QLabel(_('Frame:')))
        row.addWidget(self.position)
        row.addStretch()
        row = QHBoxLayout()
        layout.addLayout(row)
        self.duration = QSpinBox()
        self.duration.setRange(1, 3600000)
        self.duration.setSuffix(_(' ms'))
        self.duration.setAccessibleName(_('Frame duration in milliseconds'))
        row.addWidget(QLabel(_('Duration:')))
        row.addWidget(self.duration)
        self.loop = QSpinBox()
        self.loop.setRange(0, 65535)
        self.loop.setSpecialValueText(_('Infinite'))
        self.loop.setAccessibleName(_('Total plays; zero means infinite'))
        row.addWidget(QLabel(_('Total plays:')))
        row.addWidget(self.loop)
        self.onion = QCheckBox(_('Onion skin'))
        row.addWidget(self.onion)
        self.list_mode = QCheckBox(_('Text list'))
        row.addWidget(self.list_mode)
        row.addStretch()
        self.strip = QListView()
        self.strip.setViewMode(QListView.ViewMode.IconMode)
        self.strip.setAccessibleName(_('Animation frame strip'))
        self.strip.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.strip.setFlow(QListView.Flow.LeftToRight)
        self.strip.setWrapping(False)
        self.strip.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.strip.setMinimumHeight(110)
        self.strip.setIconSize(QSize(80, 64))
        self.strip.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.strip.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.model = FrameModel(self)
        self.strip.setModel(self.model)
        self.model.reordered.connect(lambda ids: self._edit(lambda: self.editor.reorder_frames(ids)))
        layout.addWidget(self.strip)
        self.setFocusProxy(self.strip)
        self.frame_actions = {}
        for key, label, callback in (
            ('add', _('Add Blank'), self.blank_requested.emit), ('import', _('Import Frames...'), self.import_requested.emit),
            ('duplicate', _('Duplicate'), self.editor.duplicate_frames), ('delete', _('Delete'), self.editor.delete_frames),
            ('earlier', _('Move Earlier'), lambda: self.editor.move_frames(-1)), ('later', _('Move Later'), lambda: self.editor.move_frames(1))):
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, cb=callback: self._edit(cb))
            self.frame_actions[key] = action
        self.strip.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.strip.customContextMenuRequested.connect(self.show_frame_menu)
        self.previous.clicked.connect(lambda: self.navigate(-1))
        self.next.clicked.connect(lambda: self.navigate(1))
        self.play.clicked.connect(playback.toggle)
        self.position.valueChanged.connect(self._position_changed)
        self.duration.editingFinished.connect(self._duration_changed)
        self.loop.editingFinished.connect(self._loop_changed)
        self.onion.toggled.connect(self.onion_changed)
        self.list_mode.toggled.connect(self._list_mode)
        self.strip.selectionModel().selectionChanged.connect(self._selection_changed)
        self.strip.selectionModel().currentChanged.connect(self._selection_changed)
        playback.state_changed.connect(lambda playing: self.play.setText(_('Pause') if playing else _('Play')))
        context = Qt.ShortcutContext.WidgetShortcut
        for action, callback in (('Previous Frame', lambda: self.navigate(-1)), ('Next Frame', lambda: self.navigate(1)),
                                 ('Play/Pause', playback.toggle), ('First Frame', lambda: self.navigate_to(0)),
                                 ('Last Frame', lambda: self.navigate_to(len(self.model.frames)-1)),
                                 ('Duplicate Frames', lambda: self._edit(self.editor.duplicate_frames)),
                                 ('Delete Frames', lambda: self._edit(self.editor.delete_frames)),
                                 ('Move Earlier', lambda: self._edit(lambda: self.editor.move_frames(-1))),
                                 ('Move Later', lambda: self._edit(lambda: self.editor.move_frames(1)))):
            key_config.make_shortcut('Animation', action, self.strip, callback, context)
        for action, callback in (('Previous Frame', lambda: self.navigate(-1)), ('Next Frame', lambda: self.navigate(1)), ('Play/Pause', playback.toggle)):
            key_config.make_shortcut('Animation', action, self.parent().viewer, callback, context)

    def _edit(self, callback):
        self.playback.stop()
        callback()

    def update_context_actions(self):
        document = self.editor.document
        frames = document.frames if document else []
        ids = self.editor.state.selected_frame_ids if document else set()
        indices = [i for i, frame in enumerate(frames) if frame.id in ids]
        self.frame_actions['add'].setEnabled(bool(document))
        self.frame_actions['import'].setEnabled(bool(document))
        self.frame_actions['duplicate'].setEnabled(bool(indices))
        self.frame_actions['delete'].setEnabled(bool(indices) and len(indices) < len(frames))
        self.frame_actions['earlier'].setEnabled(any(i > 0 and frames[i-1].id not in ids for i in indices))
        self.frame_actions['later'].setEnabled(any(i < len(frames)-1 and frames[i+1].id not in ids for i in indices))

    def create_frame_menu(self):
        self.update_context_actions()
        menu = QMenu(self.strip)
        for action in self.frame_actions.values():
            menu.addAction(action)
        return menu

    def show_frame_menu(self, position):
        menu = self.create_frame_menu()
        menu.exec(self.strip.mapToGlobal(position))
        menu.deleteLater()

    def _list_mode(self, checked):
        self.strip.setViewMode(QListView.ViewMode.ListMode if checked else QListView.ViewMode.IconMode)
        self.strip.setFlow(QListView.Flow.TopToBottom if checked else QListView.Flow.LeftToRight)
        self.strip.setWrapping(False)

    def navigate(self, step):
        if not self.editor.document:
            return
        index = next(i for i, f in enumerate(self.editor.document.frames) if f.id == self.editor.state.active_frame_id)
        self.navigate_to(max(0, min(len(self.model.frames)-1, index+step)))

    def navigate_to(self, index):
        if 0 <= index < len(self.model.frames):
            self.playback.stop()
            self.editor.set_active_frame(self.model.frames[index].id)

    def _position_changed(self, value):
        if not self._refreshing:
            self.navigate_to(value-1)

    def _selection_changed(self, *args):
        if not self._refreshing:
            self._selection_timer.start(0)

    def _commit_selection(self):
        if self._refreshing or not self.strip.currentIndex().isValid():
            return
        ids = {self.model.frames[i.row()].id for i in self.strip.selectionModel().selectedIndexes()}
        active = self.model.frames[self.strip.currentIndex().row()].id
        self.playback.stop()
        self.editor.set_active_frame(active, ids)

    def _duration_changed(self):
        if self.editor.document and self.duration.value() != self.editor.document.frame(self.editor.state.active_frame_id).duration_ms:
            self._edit(lambda: self.editor.set_duration(self.duration.value()))

    def _loop_changed(self):
        if self.editor.document and self.loop.value() != self.editor.document.total_plays:
            self._edit(lambda: self.editor.set_loop(self.loop.value()))

    def refresh(self):
        document = self.editor.document
        if not document:
            return
        self._refreshing = True
        self.model.reset(document.frames)
        active_index = next(i for i, f in enumerate(document.frames) if f.id == self.editor.state.active_frame_id)
        self.position.setRange(1, len(document.frames))
        self.position.setValue(active_index+1)
        self.duration.setValue(document.frames[active_index].duration_ms)
        self.loop.setValue(document.total_plays)
        flags = QItemSelectionModel.SelectionFlag.Select
        self.strip.selectionModel().clearSelection()
        for i, frame in enumerate(document.frames):
            if frame.id in self.editor.state.selected_frame_ids:
                self.strip.selectionModel().select(self.model.index(i), flags)
        self.strip.selectionModel().setCurrentIndex(self.model.index(active_index), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.strip.scrollTo(self.model.index(active_index))
        self.update_context_actions()
        self._refreshing = False
        key = document.id, document.revision, active_index//64
        if self._thumbnail_key != key and document.animation:
            self._thumbnail_key = key
            if self._thumbnail_job:
                self._thumbnail_job.control.cancel()
            snapshot = document.snapshot()
            def thumbnails(control, progress):
                from .artwork_renderer import render_frame
                results = {}
                # Bounded visible-neighbour cache, avoiding 10,000 thumbnails.
                for frame in snapshot.frames[max(0, active_index-64):active_index+65]:
                    control.checkpoint()
                    pixels = render_frame(frame) if frame.artwork else frame.image.current
                    pixels.thumbnail((80, 64))
                    results[frame.id] = pixels
                return results
            job = FunctionJob(thumbnails, self)
            self._thumbnail_job = job
            job.succeeded.connect(lambda result: self._thumbnails_ready(key, result))
            self.jobs.start(job)

    def _thumbnails_ready(self, key, result):
        if key != self._thumbnail_key:
            return
        self.model.icons = {frame_id: QIcon(pil_to_qpixmap(pixels)) for frame_id, pixels in result.items()}
        if self.model.frames:
            self.model.dataChanged.emit(self.model.index(0), self.model.index(len(self.model.frames)-1))

    def sync_playback(self):
        if not self.editor.document:
            return
        self._refreshing = True
        index = next(i for i, f in enumerate(self.editor.document.frames) if f.id == self.editor.state.active_frame_id)
        self.position.setValue(index+1)
        self.duration.setValue(self.editor.document.frames[index].duration_ms)
        self.strip.selectionModel().setCurrentIndex(self.model.index(index), QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.strip.scrollTo(self.model.index(index))
        self._refreshing = False
