from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QTabWidget, QPlainTextEdit, QComboBox, QPushButton

class JobProgressDialog(QDialog):
    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.finished_run = False
        self.paused = False
        self.setWindowTitle(_('Image Conversion Progress'))
        self.resize(650, 450)
        layout = QVBoxLayout(self)
        self.detail = QLabel(_('Preparing...'))
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        self.tabs = QTabWidget()
        self.results = QPlainTextEdit()
        self.log = QPlainTextEdit()
        for widget in (self.results, self.log):
            widget.setReadOnly(True)
            widget.document().setMaximumBlockCount(1000)
        self.tabs.addTab(self.results, _('Progress'))
        self.tabs.addTab(self.log, _('Live Log'))
        layout.addWidget(self.tabs)
        row = QHBoxLayout()
        row.addWidget(QLabel(_('When finished:')))
        self.notify = QComboBox()
        self.notify.addItem(_('No notification'), False)
        self.notify.addItem(_('Tray notification'), True)
        row.addWidget(self.notify)
        row.addStretch()
        self.pause = QPushButton(_('Pause'))
        self.cancel = QPushButton(_('Cancel'))
        self.hide_button = QPushButton(_('Hide'))
        row.addWidget(self.pause)
        row.addWidget(self.cancel)
        row.addWidget(self.hide_button)
        layout.addLayout(row)
        self.pause.clicked.connect(self._pause)
        self.cancel.clicked.connect(self._cancel)
        self.hide_button.clicked.connect(self.hide)
        job.event.connect(self.on_event)
        job.completed.connect(self.on_complete)
        job.failed.connect(self.on_failure)

    def _pause(self):
        self.paused = not self.paused
        self.job.control.pause() if self.paused else self.job.control.resume()
        self.pause.setText(_('Resume') if self.paused else _('Pause'))

    def _cancel(self):
        if self.finished_run:
            self.hide()
        else:
            self.job.control.cancel()
            self.detail.setText(_('Cancelling... Waiting for the current encoder to finish.'))
            self.pause.setEnabled(False)
            self.cancel.setEnabled(False)

    def on_event(self, kind, values):
        if kind == 'progress':
            done, total, path = values
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(done)
            self.detail.setText(path)
        elif kind == 'phase':
            self.detail.setText(values[0])
            self.log.appendPlainText(values[0])
        elif kind == 'result':
            record = values[0]
            text = f'{record.status}: {record.source}\n{record.message}'
            self.results.appendPlainText(text)
            self.log.appendPlainText(text)
        elif kind == 'log':
            self.log.appendPlainText(values[0])

    def on_complete(self, result):
        self.finished_run = True
        self.detail.setText(result.summary)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.pause.setEnabled(False)
        self.cancel.setEnabled(True)
        self.cancel.setText(_('Close'))
        self.log.appendPlainText(result.summary)
        if self.notify.currentData():
            window = self.parent().window()
            tray = getattr(window, 'taskbar_icon', None)
            if tray:
                tray.show_message(_('Batch conversion finished'), result.summary)
            else:
                self.log.appendPlainText(_('Tray notification unavailable'))

    def on_failure(self, message):
        self.finished_run = True
        self.detail.setText(message)
        self.pause.setEnabled(False)
        self.cancel.setEnabled(True)
        self.cancel.setText(_('Close'))

    def reject(self):
        self.hide()

    def closeEvent(self, event):
        self.hide()
        event.ignore()
