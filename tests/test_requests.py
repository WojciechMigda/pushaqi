"""Tests for HTTP helpers (retry session, media attach, status post)."""

import requests
import pytest

import pusher


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self._json = {'id': 'x'}

    def json(self):
        return self._json


class RecordingSession:
    """Minimal requests.Session stand-in that records calls."""

    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.calls = []

    def post(self, url, timeout=None, data=None, files=None, headers=None):
        self.calls.append({
            'url': url, 'timeout': timeout, 'data': data,
            'files': files, 'headers': headers,
        })
        if self.error is not None:
            raise self.error
        return self.response


def test_retry_session_configuration():
    session = pusher.requests_retry_session(retries=4, backoff_factor=0.7)
    http_adapter = session.get_adapter('http://')
    assert http_adapter.max_retries.total == 4
    assert http_adapter.max_retries.read == 4
    assert http_adapter.max_retries.connect == 4
    assert http_adapter.max_retries.backoff_factor == 0.7
    assert http_adapter.max_retries.status_forcelist == (500, 502, 503, 504)
    # Both schemes are mounted (adapter lookup must not raise).
    session.get_adapter('https://')


def test_status_post_success(monkeypatch):
    monkeypatch.setattr(pusher, 'MASTODON_HOST', 'https://social.example')
    monkeypatch.setattr(pusher, 'MASTODON_TOKEN', 'secret')
    session = RecordingSession()
    ok, res = pusher.status_post('hello', ['42'], session=session, timeout=5)
    assert ok and res.status_code == 200
    call = session.calls[0]
    assert call['url'] == 'https://social.example/api/v1/statuses'
    assert call['data']['status'] == 'hello'
    assert call['data']['media_ids[]'] == ['42']
    assert call['headers']['Authorization'] == 'Bearer secret'


def test_status_post_no_media(monkeypatch):
    monkeypatch.setattr(pusher, 'MASTODON_HOST', 'https://social.example')
    session = RecordingSession()
    ok, res = pusher.status_post('hello', [], session=session, timeout=5)
    assert ok
    assert session.calls[0]['data']['media_ids[]'] == []


def test_status_post_http_error(monkeypatch):
    monkeypatch.setattr(pusher, 'MASTODON_HOST', 'https://social.example')
    session = RecordingSession(response=FakeResponse(status_code=422))
    ok, res = pusher.status_post('hello', [], session=session, timeout=5)
    assert ok is False and res.status_code == 422


def test_status_post_network_error(monkeypatch):
    monkeypatch.setattr(pusher, 'MASTODON_HOST', 'https://social.example')
    session = RecordingSession(error=requests.exceptions.ConnectionError('boom'))
    ok, res = pusher.status_post('hello', [], session=session, timeout=5)
    assert ok is False and res is None


def test_attach_media_success(monkeypatch, tmp_path):
    monkeypatch.setattr(pusher, 'MASTODON_HOST', 'https://social.example')
    monkeypatch.setattr(pusher, 'MASTODON_TOKEN', 'secret')
    img = tmp_path / 'test.gif'
    img.write_bytes(b'GIF89a')
    session = RecordingSession()
    ok, res = pusher.attach_media(str(img), 'Good', session=session, timeout=5)
    assert ok and res.status_code == 200
    call = session.calls[0]
    assert call['url'] == 'https://social.example/api/v1/media'
    assert call['data']['description'] == 'Good'
    # File tuple: (filename, fileobj, content-type). The context manager
    # must have closed the handle after the request (previously leaked).
    name, fileobj, ctype = call['files']['file']
    assert name == 'test.gif'
    assert fileobj.closed


def test_attach_media_missing_file(tmp_path):
    session = RecordingSession()
    ok, res = pusher.attach_media(str(tmp_path / 'nope.gif'), 'Good',
                                  session=session, timeout=5)
    assert ok is False and res is None
    assert session.calls == []