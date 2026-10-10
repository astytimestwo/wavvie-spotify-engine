"""Connect to Spotify through the browser, with a way out if the browser never comes back."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ui.resources import resource_path
from ui.widgets.controls import button, label, scroll_column

IDLE_TEXT = "wavvie checks who you follow on Spotify and saves their new songs to a private playlist."
WAITING_TEXT = "Waiting for you to approve wavvie in your browser…"


class SignInPage(QWidget):
    connect_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scroll, layout = scroll_column(self, top=72)
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap(str(resource_path("wavvie_wordmark_white.png")))
                            .scaledToHeight(64, Qt.SmoothTransformation))
        self.logo.setAccessibleName("wavvie")
        layout.addWidget(self.logo, 0, Qt.AlignLeft)
        layout.addSpacing(12)
        # The no-break space keeps "you follow" together, so "follow" never wraps onto a line alone.
        self.headline = label("New music from the artists you follow", "headline")
        layout.addWidget(self.headline)
        self.body = label(IDLE_TEXT, "body")
        layout.addWidget(self.body)
        self.message = label("", "note")
        self.message.hide()
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        actions.setSpacing(24)
        self.btn_connect = button("Connect Spotify", "primary", "connectSpotify")
        self.btn_cancel = button("Cancel", "quiet", "cancelSignIn")
        self.btn_cancel.hide()
        actions.addWidget(self.btn_connect)
        actions.addWidget(self.btn_cancel)
        actions.addStretch()
        layout.addSpacing(8)
        layout.addLayout(actions)
        layout.addStretch()
        self.btn_connect.clicked.connect(self.connect_requested.emit)
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)

    def show_idle(self, error=None):
        self.body.setText(IDLE_TEXT)
        self.message.setText(error or "")
        self.message.setVisible(bool(error))
        self.btn_cancel.hide()
        self.btn_connect.show()

    def show_waiting(self):
        self.body.setText(WAITING_TEXT)
        self.message.hide()
        self.btn_connect.hide()
        self.btn_cancel.show()
