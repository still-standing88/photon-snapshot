"""Single-instance coordination on Linux, where AppGuard has no wheel."""

import os
from pathlib import Path
from time import monotonic, sleep

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class LocalAppGuard:
    def __init__(self, name):
        runtime = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation))
        self.socket_path = str(runtime / name)
        self.lock = QLockFile(self.socket_path + ".lock")
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._receive_requests)
        self.handler = None

    def start_or_forward(self, path):
        # The primary may still be starting its listener when a second
        # process observes the lock.
        deadline = monotonic() + 3
        while monotonic() < deadline:
            if self.lock.tryLock(0):
                QLocalServer.removeServer(self.socket_path)
                if self.server.listen(self.socket_path):
                    return True
                self.lock.unlock()
                raise RuntimeError(self.server.errorString())
            if self._forward(path):
                return False
            sleep(0.025)
        raise RuntimeError("Could not contact the running Photon Snapshot instance")

    def _forward(self, path):
        socket = QLocalSocket()
        socket.connectToServer(self.socket_path)
        if not socket.waitForConnected(100):
            return False
        message = os.fsencode(path) + b"\0" if path else b"\0"
        if socket.write(message) != len(message):
            return False
        while socket.bytesToWrite():
            if not socket.waitForBytesWritten(100):
                return False
        socket.disconnectFromServer()
        return True

    def set_handler(self, handler):
        self.handler = handler
        QTimer.singleShot(0, self._receive_requests)

    def _receive_requests(self):
        if self.handler is None:
            return
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket.state() == QLocalSocket.LocalSocketState.UnconnectedState:
                self._finish_request(socket)
            else:
                socket.disconnected.connect(lambda remote=socket: self._finish_request(remote))

    def _finish_request(self, socket):
        message = bytes(socket.readAll())
        socket.deleteLater()
        if message.endswith(b"\0"):
            self.handler(os.fsdecode(message[:-1]))

    def release(self):
        self.server.close()
        self.lock.unlock()
