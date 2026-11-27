from PySide6.QtCore import QThread, Signal
from core.batch_conversion import run_batch, JobControl

class BatchJob(QThread):
    event = Signal(str, object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, sources, settings, parent=None):
        super().__init__(parent)
        self.sources, self.settings = sources, settings
        self.control = JobControl()

    def run(self):
        try:
            result = run_batch(self.sources, self.settings, self.control,
                               lambda kind, *values: self.event.emit(kind, values))
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
