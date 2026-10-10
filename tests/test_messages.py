"""Errors from Spotify and the network, said plainly."""
import unittest

from ui.messages import friendly_error, keep_together


class FriendlyErrorTests(unittest.TestCase):
    def test_common_spotify_and_network_errors_read_plainly(self):
        cases = {
            'http status: 429, code: -1 - https://api.spotify.com/v1/search: API rate limit exceeded':
                'Spotify is busy right now. Try again in a few minutes.',
            'Max retries (3) exceeded': 'Spotify is busy right now. Try again in a few minutes.',
            'http status: 403, code: -1 - https://api.spotify.com/v1/me: Forbidden':
                "Spotify refused the request. Check that your account is added to your app in the Spotify "
                "dashboard and that the app's owner has Premium.",
            'http status: 401, code: -1 - The access token expired':
                'Your Spotify sign-in has expired. Disconnect in Settings, then connect again.',
            "HTTPSConnectionPool(host='api.spotify.com', port=443): Max retries exceeded with url: /v1/me "
            "(Caused by NewConnectionError('Failed to establish a new connection'))":
                "wavvie couldn't reach Spotify. Check your internet connection and try again.",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw[:40]):
                self.assertEqual(friendly_error(raw), expected)

    def test_unknown_errors_keep_their_detail_unless_no_fallback_is_wanted(self):
        self.assertEqual(friendly_error('Boom'), 'Spotify reported a problem: Boom')
        self.assertIsNone(friendly_error('Boom', fallback=False))
        self.assertEqual(friendly_error(''), 'Something went wrong. Try again.')


class KeepTogetherTests(unittest.TestCase):
    def test_an_address_never_breaks_across_lines(self):
        # A word joiner after each slash removes the line-break chance before "callback".
        self.assertEqual(keep_together('http://127.0.0.1:8888/callback'),
                         'http:/⁠/⁠127.0.0.1:8888/⁠callback')


if __name__ == '__main__':
    unittest.main()
