"""First run: connect wavvie to a Spotify app without editing files by hand."""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QWidget

from ui.widgets.controls import button, label, scroll_column

DASHBOARD_URL = "https://developer.spotify.com/dashboard"


class SetupPage(QWidget):
    credentials_entered = Signal(dict)
    open_url_requested = Signal(str)

    def __init__(self, redirect_uri, parent=None):
        super().__init__(parent)
        self.redirect_uri = redirect_uri
        self.scroll, layout = scroll_column(self, top=56)
        layout.addWidget(label("Connect wavvie to Spotify", "headline"))
        layout.addWidget(label("wavvie needs its own Spotify app. Setting it up takes a couple of minutes.", "body"))
        layout.addSpacing(8)

        layout.addWidget(label("1. Create an app in the Spotify developer dashboard."))
        self.btn_dashboard = button("Open dashboard", "quiet", "openDashboard")
        layout.addWidget(self.btn_dashboard, 0, Qt.AlignLeft)

        layout.addWidget(label("2. Add this redirect URI to the app:"))
        uri_row = QHBoxLayout()
        self.lbl_uri = label(redirect_uri, "code", wrap=False, selectable=True)
        self.btn_copy = button("Copy", "quiet", "copyRedirect")
        uri_row.addWidget(self.lbl_uri)
        uri_row.addWidget(self.btn_copy)
        uri_row.addStretch()
        layout.addLayout(uri_row)

        layout.addWidget(label("3. Paste the app's Client ID and Client secret."))
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
        self.txt_id = QLineEdit()
        self.txt_id.setObjectName("clientId")
        self.txt_secret = QLineEdit()
        self.txt_secret.setObjectName("clientSecret")
        self.txt_secret.setEchoMode(QLineEdit.Password)
        self.err_id = label("", "note")
        self.err_secret = label("", "note")
        for row, (text, field, error) in enumerate((("Client ID", self.txt_id, self.err_id),
                                                    ("Client secret", self.txt_secret, self.err_secret))):
            caption = label(text, wrap=False)
            caption.setBuddy(field)
            field.setAccessibleName(text)
            error.hide()
            form.addWidget(caption, row * 2, 0)
            form.addWidget(field, row * 2, 1)
            form.addWidget(error, row * 2 + 1, 1)
        layout.addLayout(form)

        layout.addSpacing(8)
        self.btn_save = button("Save and continue", "primary", "saveCredentials")
        layout.addWidget(self.btn_save, 0, Qt.AlignLeft)
        self.err_save = label("", "note")
        self.err_save.hide()
        layout.addWidget(self.err_save)
        layout.addWidget(label("These stay on this computer, in a .env file next to wavvie.", "secondary"))
        layout.addStretch()

        self.btn_dashboard.clicked.connect(lambda: self.open_url_requested.emit(DASHBOARD_URL))
        self.btn_copy.clicked.connect(self.copy_redirect_uri)
        self.btn_save.clicked.connect(self.submit)
        self.txt_secret.returnPressed.connect(self.submit)

    def set_redirect_uri(self, uri):
        self.redirect_uri = uri
        self.lbl_uri.setText(uri)

    def copy_redirect_uri(self):
        QGuiApplication.clipboard().setText(self.redirect_uri)
        self.btn_copy.setText("Copied")
        QTimer.singleShot(2000, self, lambda: self.btn_copy.setText("Copy"))

    def submit(self):
        values = {'SPOTIPY_CLIENT_ID': self.txt_id.text().strip(),
                  'SPOTIPY_CLIENT_SECRET': self.txt_secret.text().strip()}
        id_problem = self.problem(values['SPOTIPY_CLIENT_ID'], "Client ID")
        secret_problem = self.problem(values['SPOTIPY_CLIENT_SECRET'], "Client secret")
        for error, message in ((self.err_id, id_problem), (self.err_secret, secret_problem)):
            error.setText(message or "")
            error.setVisible(bool(message))
        if id_problem or secret_problem:
            (self.txt_id if id_problem else self.txt_secret).setFocus()
            return
        self.err_save.hide()
        values['SPOTIPY_REDIRECT_URI'] = self.redirect_uri
        self.credentials_entered.emit(values)

    @staticmethod
    def problem(value, name):
        if not value:
            return f"Enter the {name}"
        if any(character.isspace() or character in "'\"" for character in value):
            return f"That {name} doesn't look right. Copy it again from your app's settings."
        return None

    def show_error(self, message):
        self.err_save.setText(message)
        self.err_save.show()
