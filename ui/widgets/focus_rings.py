"""Focus rings for keyboard users only, like the web's :focus-visible."""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

MODIFIER_KEYS = {Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_AltGr, Qt.Key_Meta}


class FocusRings(QObject):
    """Set focusRing=true on the focused widget after a key press, and clear it after a click.

    Qt moves focus on its own when the focused widget hides, so styling plain :focus puts a ring on
    whatever a mouse user's click left behind. The stylesheet styles [focusRing="true"] instead.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard = False
        self.ringed = None
        app = QApplication.instance()
        app.installEventFilter(self)
        app.focusChanged.connect(self.update_ring)

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.KeyPress and event.key() not in MODIFIER_KEYS:
            self.set_keyboard(True)
        elif kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            self.set_keyboard(False)
        return False

    def set_keyboard(self, keyboard):
        if keyboard != self.keyboard:
            self.keyboard = keyboard
            self.update_ring()

    def update_ring(self, *_):
        target = QApplication.focusWidget() if self.keyboard else None
        if target is self.ringed:
            return
        if self.ringed is not None and isValid(self.ringed):
            self.mark(self.ringed, False)
        if target is not None:
            self.mark(target, True)
        self.ringed = target

    @staticmethod
    def mark(widget, ringed):
        widget.setProperty("focusRing", ringed)
        # Dynamic properties only restyle after a re-polish.
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
