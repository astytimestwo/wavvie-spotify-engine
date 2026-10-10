"""Plain-language versions of errors from Spotify and the network."""
import re


def friendly_error(message, fallback=True):
    text = str(message or "")
    lowered = text.lower()
    if "max retries (" in lowered or re.search(r"\b429\b", text) or "rate limit" in lowered:
        return "Spotify is busy right now. Try again in a few minutes."
    if re.search(r"\b403\b", text):
        return ("Spotify refused the request. Check that your account is added to your app in the Spotify "
                "dashboard and that the app's owner has Premium.")
    if re.search(r"\b401\b", text) or "access token" in lowered or "invalid_grant" in lowered:
        return "Your Spotify sign-in has expired. Disconnect in Settings, then connect again."
    if any(word in lowered for word in ("connection", "timed out", "timeout", "resolve", "unreachable", "network")):
        return "wavvie couldn't reach Spotify. Check your internet connection and try again."
    if not fallback:
        return None
    return f"Spotify reported a problem: {text[:200]}" if text else "Something went wrong. Try again."


def keep_together(address):
    """Stop a URL from wrapping onto two lines by putting a word joiner after each slash."""
    return address.replace("/", "/\u2060")
