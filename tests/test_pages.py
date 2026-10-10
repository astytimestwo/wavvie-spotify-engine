"""Setup and sign-in pages."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from ui.pages.setup_page import SetupPage
from ui.pages.sign_in_page import SignInPage

REDIRECT = 'http://127.0.0.1:8888/callback'


class SetupPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = SetupPage(REDIRECT)
        self.addCleanup(self.page.deleteLater)
        self.entered = []
        self.page.credentials_entered.connect(self.entered.append)

    def test_missing_or_mangled_credentials_are_explained_and_not_sent(self):
        self.page.btn_save.click()
        self.assertEqual(self.page.err_id.text(), 'Enter the Client ID')
        self.assertEqual(self.page.err_secret.text(), 'Enter the Client secret')
        self.page.txt_id.setText('abc 123')
        self.page.txt_secret.setText('secret')
        self.page.btn_save.click()
        self.assertIn("doesn't look right", self.page.err_id.text())
        self.assertTrue(self.page.err_secret.isHidden())
        self.assertEqual(self.entered, [])

    def test_valid_credentials_are_sent_with_the_redirect_uri(self):
        self.page.txt_id.setText(' abc123 ')
        self.page.txt_secret.setText('secret456')
        self.page.btn_save.click()
        self.assertEqual(self.entered, [{'SPOTIPY_CLIENT_ID': 'abc123', 'SPOTIPY_CLIENT_SECRET': 'secret456',
                                         'SPOTIPY_REDIRECT_URI': REDIRECT}])

    def test_redirect_uri_copies_and_the_dashboard_opens(self):
        opened = []
        self.page.open_url_requested.connect(opened.append)
        self.page.btn_copy.click()
        self.assertEqual(QGuiApplication.clipboard().text(), REDIRECT)
        self.assertEqual(self.page.btn_copy.text(), 'Copied')
        self.page.btn_dashboard.click()
        self.assertEqual(opened, ['https://developer.spotify.com/dashboard'])


class SignInPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_waiting_offers_cancel_instead_of_connect(self):
        page = SignInPage()
        self.addCleanup(page.deleteLater)
        page.show_waiting()
        self.assertTrue(page.btn_connect.isHidden())
        self.assertFalse(page.btn_cancel.isHidden())
        self.assertIn('Waiting', page.body.text())
        page.show_idle("Couldn't connect to Spotify.")
        self.assertFalse(page.btn_connect.isHidden())
        self.assertTrue(page.btn_cancel.isHidden())
        self.assertEqual(page.message.text(), "Couldn't connect to Spotify.")
        self.assertFalse(page.message.isHidden())


if __name__ == '__main__':
    unittest.main()
