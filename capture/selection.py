"""Transparent selection overlay with green rectangle."""
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QGuiApplication


class SelectionOverlay(QWidget):
    """Transparent overlay for region selection with green border."""

    # Signal emitted when selection is complete
    selection_complete = pyqtSignal(QRect)

    def __init__(self):
        super().__init__()

        # Window flags for transparent overlay
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # No taskbar entry
        )

        # Enable transparency
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Cover all screens
        self._set_fullscreen_geometry()

        # Selection state
        self.origin = None
        self.selection = QRect()

        # Set cursor
        self.setCursor(Qt.CrossCursor)

    def _set_fullscreen_geometry(self):
        """Cover all connected screens."""
        total_rect = QRect()
        for screen in QGuiApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        self.setGeometry(total_rect)

    def paintEvent(self, event):
        """Draw semi-transparent overlay with selection cutout."""
        painter = QPainter(self)

        # Semi-transparent dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if not self.selection.isNull():
            # Clear the selection area
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(self.selection, QColor(0, 0, 0, 0))

            # Draw green border
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 255, 0), 3)
            painter.setPen(pen)
            painter.drawRect(self.selection)

    def mousePressEvent(self, event):
        """Start selection on left click."""
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.selection = QRect(self.origin, self.origin)
            self.update()

    def mouseMoveEvent(self, event):
        """Update selection rectangle while dragging."""
        if self.origin:
            self.selection = QRect(self.origin, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        """Finalize selection on release."""
        if event.button() == Qt.LeftButton and self.origin:
            self.selection = QRect(self.origin, event.pos()).normalized()
            self.close()
            if self.selection.width() > 10 and self.selection.height() > 10:
                self.selection_complete.emit(self.selection)

    def keyPressEvent(self, event):
        """Cancel selection on Escape."""
        if event.key() == Qt.Key_Escape:
            self.close()
