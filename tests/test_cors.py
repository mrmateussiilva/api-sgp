import re

from config import settings


def test_cors_regex_allows_ngrok_https_origin():
    origin = "https://frontend-123.ngrok-free.app"
    pattern = settings.BACKEND_CORS_ALLOW_ORIGIN_REGEX

    assert pattern is not None
    assert re.fullmatch(pattern, origin)


def test_cors_regex_allows_localhost_any_port():
    origin = "http://localhost:5173"
    pattern = settings.BACKEND_CORS_ALLOW_ORIGIN_REGEX

    assert pattern is not None
    assert re.fullmatch(pattern, origin)


def test_cors_regex_allows_null_origin():
    origin = "null"
    pattern = settings.BACKEND_CORS_ALLOW_ORIGIN_REGEX

    assert pattern is not None
    assert re.fullmatch(pattern, origin)
