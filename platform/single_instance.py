"""Single-instance application guard using QLocalServer and QLocalSocket.

Ensures only one instance of FreeNetMeter runs at any time. When a second
launch occurs, it notifies the running instance over local IPC to raise
its interface and bring it to the foreground, then terminates cleanly.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from core.constants import SINGLE_INSTANCE_SERVER_NAME

logger = logging.getLogger("FreeNetMeter.SingleInstance")


class SingleInstanceGuard(QObject):
    """Enforces single-instance execution via local inter-process communication."""

    # Signal emitted when a secondary instance requests activation
    activation_requested = pyqtSignal()

    def __init__(
        self,
        server_name: str = SINGLE_INSTANCE_SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        """Initialize single-instance guard.

        Args:
            server_name: Named pipe / domain socket identifier.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self.server_name = server_name
        self._server: QLocalServer | None = None

    def try_acquire(self) -> bool:
        """Attempt to acquire the single-instance lock.

        If another instance is already running:
        Sends an 'ACTIVATE' notification to the primary instance and returns False.

        If no instance is running:
        Starts listening on the local server socket and returns True.

        Returns:
            True if this is the primary instance and lock was acquired;
            False if another instance is already active.
        """
        # Test connection to an existing instance
        test_socket = QLocalSocket()
        test_socket.connectToServer(self.server_name)

        if test_socket.waitForConnected(500):
            # Another instance responded: notify it to activate
            logger.info("Found running FreeNetMeter instance. Requesting activation...")
            test_socket.write(b"ACTIVATE\n")
            test_socket.flush()
            test_socket.waitForBytesWritten(500)
            test_socket.waitForDisconnected(300)
            test_socket.disconnectFromServer()
            return False

        # No active instance found. Clear any stale server file from a previous unclean shutdown.
        QLocalServer.removeServer(self.server_name)

        # Create the local server for this primary instance
        server = QLocalServer(self)
        server.newConnection.connect(self._handle_new_connection)

        if not server.listen(self.server_name):
            logger.warning(
                "Failed to start local server '%s': %s",
                self.server_name,
                server.errorString(),
            )
            # Even if server listen failed, proceed as primary
            return True

        self._server = server
        logger.debug("Acquired single-instance server lock: %s", self.server_name)
        return True

    def _handle_new_connection(self) -> None:
        """Handle incoming connection from a secondary instance launch."""
        if not self._server:
            return

        client_socket = self._server.nextPendingConnection()
        if not client_socket:
            return

        def process_data() -> None:
            data = bytes(client_socket.readAll()).decode("utf-8", errors="ignore")
            if "ACTIVATE" in data:
                logger.info("Received activation request from secondary launch.")
                self.activation_requested.emit()
            client_socket.disconnectFromServer()

        if client_socket.bytesAvailable() > 0:
            process_data()
        else:
            client_socket.readyRead.connect(process_data)

    def release(self) -> None:
        """Release the local server and remove socket cleanly on shutdown."""
        if self._server:
            self._server.close()
            self._server = None
        QLocalServer.removeServer(self.server_name)
        logger.debug("Released single-instance server: %s", self.server_name)
