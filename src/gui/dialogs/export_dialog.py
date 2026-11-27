"""Shared format-specific encoder form, also used by batch conversion."""
from dataclasses import asdict
from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox, QSpinBox, QCheckBox, QPushButton, QColorDialog, QDialog, QVBoxLayout, QDialogButtonBox, QLabel
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from core.formats import FORMATS, animation_available
from core.export import ExportOptions

class ExportOptionsWidget(QWidget):
    def __init__(self, parent=None, animation_only=False):
        super().__init__(parent)
        self.form = QFormLayout(self)
        self.format = QComboBox()
        self.format.setAccessibleName(_('Output image format'))
        for fmt in FORMATS:
            if fmt.writable and (not animation_only or animation_available(fmt.id)):
                self.format.addItem(fmt.label, fmt.id)
        self.form.addRow(_('Format:'), self.format)
        self.controls = {}
        specs = (('quality', _('Quality:'), 0, 100, 90), ('png_compression', _('PNG compression:'), 0, 9, 6),
                 ('effort', _('WebP effort:'), 0, 6, 4), ('palette_size', _('GIF palette colours:'), 2, 256, 256),
                 ('alpha_threshold', _('Transparency threshold:'), 0, 255, 128))
        for key, label, low, high, value in specs:
            control = QSpinBox()
            control.setRange(low, high)
            control.setValue(value)
            self.controls[key] = control
            control.setAccessibleName(label.rstrip(':'))
            self.form.addRow(label, control)
        for key, label, default in (('optimize', _('Optimize JPEG'), True), ('lossless', _('Lossless WebP'), False),
                                    ('dither', _('GIF dithering'), True), ('gif_transparency', _('GIF binary transparency'), True),
                                    ('preserve_metadata', _('Preserve supported metadata'), False)):
            control = QCheckBox(label)
            control.setChecked(default)
            self.controls[key] = control
            self.form.addRow('', control)
        self.compression = QComboBox()
        self.compression.setAccessibleName(_('TIFF compression'))
        for label, value in ((_('None'), 'raw'), ('LZW', 'tiff_lzw'), ('Deflate', 'tiff_adobe_deflate')):
            self.compression.addItem(label, value)
        self.compression.setCurrentIndex(1)
        self.form.addRow(_('TIFF compression:'), self.compression)
        self.background_value = (255, 255, 255)
        self.background = QPushButton(_('Choose background...'))
        self.form.addRow(_('Transparency background:'), self.background)
        self.background.clicked.connect(self._background)
        self.note = QLabel(_('Metadata is removed by default. GIF supports transparent or opaque pixels; partial alpha is thresholded.'))
        self.note.setWordWrap(True)
        self.form.addRow(self.note)
        self.format.currentIndexChanged.connect(self._update_rows)
        self._update_rows()

    def _background(self):
        colour = QColorDialog.getColor(QColor(*self.background_value), self)
        if colour.isValid():
            self.background_value = colour.red(), colour.green(), colour.blue()
            self.background.setText(colour.name())

    def _update_rows(self):
        fmt = self.format.currentData()
        applicable = {'quality': ('JPEG', 'WEBP'), 'optimize': ('JPEG',), 'png_compression': ('PNG',),
                      'lossless': ('WEBP',), 'effort': ('WEBP',), 'palette_size': ('GIF',),
                      'dither': ('GIF',), 'alpha_threshold': ('GIF',), 'gif_transparency': ('GIF',)}
        for key, formats in applicable.items():
            self.form.setRowVisible(self.controls[key], fmt in formats)
        self.form.setRowVisible(self.compression, fmt == 'TIFF')
        self.form.setRowVisible(self.background, fmt in ('JPEG', 'BMP', 'GIF'))
        self.controls['quality'].setRange(1 if fmt == 'JPEG' else 0, 95 if fmt == 'JPEG' else 100)

    def values(self):
        values = {key: control.isChecked() if isinstance(control, QCheckBox) else control.value() for key, control in self.controls.items()}
        options = ExportOptions(format_id=self.format.currentData(), tiff_compression=self.compression.currentData(),
                                background=self.background_value, **values)
        options.validate()
        return options

    def load(self, values):
        options = ExportOptions(**values)
        options.validate()
        index = self.format.findData(options.format_id)
        if index < 0:
            raise ValueError('The preset encoder is unavailable')
        self.format.setCurrentIndex(index)
        for key, control in self.controls.items():
            if isinstance(control, QCheckBox):
                control.setChecked(getattr(options, key))
            else:
                control.setValue(getattr(options, key))
        self.compression.setCurrentIndex(self.compression.findData(options.tiff_compression))
        self.background_value = tuple(options.background)

class ExportDialog(QDialog):
    def __init__(self, parent=None, animation_only=False, document=None):
        super().__init__(parent)
        self.setWindowTitle(_('Export Animation') if animation_only else _('Image Encoding Settings'))
        layout = QVBoxLayout(self)
        self.options = ExportOptionsWidget(self, animation_only)
        layout.addWidget(self.options)
        if document:
            label = QLabel(_('{count} frames, {width} × {height}, {duration} ms. GIF timing rounds to 10 ms; identical frames may merge.').format(
                count=len(document.frames), width=document.canvas_size[0], height=document.canvas_size[1],
                duration=sum(f.duration_ms for f in document.frames)))
            label.setWordWrap(True)
            layout.addWidget(label)
            preview = QPushButton(_('Preview Encoded Output...'))
            preview.clicked.connect(lambda: self.preview(document))
            layout.addWidget(preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def preview(self, document):
        from core.export import encode_images
        from gui.artwork_renderer import render_frame
        from core.utils import pil_to_qpixmap
        from PIL import Image
        import io
        import time
        snapshot = document.snapshot()
        options = self.options.values()
        if len(snapshot.frames) > 1 and options.format_id not in ('GIF', 'WEBP'):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, _('Animation Preview'), _('Choose GIF or WebP to preview an animation.'))
            return
        def encoded(control, progress):
            images = []
            for frame in snapshot.frames:
                control.checkpoint()
                images.append(render_frame(frame))
            return encode_images(images, [f.duration_ms for f in snapshot.frames], snapshot.total_plays, options, snapshot.metadata, control.cancelled.is_set)
        output = self.parent()._run_worker(_('Preparing Export Preview'), encoded)
        if output is None:
            return
        frames, durations = [], []
        with Image.open(io.BytesIO(output)) as decoded:
            for index in range(getattr(decoded, 'n_frames', 1)):
                decoded.seek(index)
                pixels = decoded.convert('RGBA')
                pixels.thumbnail((640, 480))
                frames.append(pil_to_qpixmap(pixels))
                durations.append(int(decoded.info.get('duration', 100) or 100))
        preview = QDialog(self)
        preview.setWindowTitle(_('Encoded Output Preview'))
        layout = QVBoxLayout(preview)
        label = QLabel()
        label.setPixmap(frames[0])
        layout.addWidget(label)
        summary = QLabel(_('{bytes} bytes; {count} decoded frames; {duration} ms total.').format(bytes=len(output), count=len(frames), duration=sum(durations)))
        summary.setWordWrap(True)
        layout.addWidget(summary)
        timer = QTimer(preview)
        timer.setSingleShot(True)
        position = [0]
        deadline = [time.monotonic()+durations[0]/1000]
        def tick():
            position[0] = (position[0]+1)%len(frames)
            label.setPixmap(frames[position[0]])
            deadline[0] += durations[position[0]]/1000
            timer.start(max(1, int((deadline[0]-time.monotonic())*1000)))
        timer.timeout.connect(tick)
        if len(frames) > 1:
            timer.start(durations[0])
        preview.exec()
        timer.stop()
