"""Own workers until finished; cancelling never destroys a running QThread."""
from PySide6.QtCore import QObject, QThread, Signal
from core.batch_conversion import JobControl
from core.export import CancelledError

class FunctionJob(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int, int)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function
        self.control = JobControl()

    def run(self):
        try:
            result = self.function(self.control, lambda a, b: self.progress.emit(a, b))
            self.succeeded.emit(result)
        except CancelledError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

class JobManager(QObject):
    idle = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.jobs = set()

    def start(self, job):
        self.jobs.add(job)
        job.finished.connect(lambda: self._finished(job))
        job.start()
        return job

    def _finished(self, job):
        self.jobs.discard(job)
        if isinstance(job, FunctionJob):
            job.function = None
            job.deleteLater()
        if not self.jobs:
            self.idle.emit()

    @property
    def active(self):
        return any(job.isRunning() for job in self.jobs)

    def cancel_all(self):
        for job in self.jobs:
            job.control.cancel()
