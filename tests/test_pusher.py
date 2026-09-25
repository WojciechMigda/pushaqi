"""Tests for the push_aqi_status posting state machine (offline, mocked)."""

import pytest

import pusher


class FakeMediaResponse:
    def json(self):
        return {'id': '42'}


class FakeStatusResponse:
    def json(self):
        return {'id': '1337', 'url': 'https://example.social/@bot/1337'}


def _run(measurements, former_bad_aqi, tmp_path, monkeypatch, status_ok=True,
         media_ok=True):
    """Run push_aqi_status with mocked Mastodon calls; return recorded calls."""
    calls = []

    def fake_attach_media(path, description, session, timeout):
        calls.append(('media', path, description))
        return (True, FakeMediaResponse()) if media_ok else (False, None)

    def fake_status_post(status, media_ids, session, timeout):
        calls.append(('status', status, list(media_ids)))
        return (True, FakeStatusResponse()) if status_ok else (False, None)

    monkeypatch.setattr(pusher, 'attach_media', fake_attach_media)
    monkeypatch.setattr(pusher, 'status_post', fake_status_post)
    monkeypatch.chdir(tmp_path)

    pusher.push_aqi_status(measurements, former_bad_aqi=former_bad_aqi)
    return calls


GOOD = {'Mikolajska': {'pm2.5': '5', 'pm10': '10'}}
MODERATE = {'Mikolajska': {'pm2.5': '25.5', 'pm10': '40'}}   # 25.5 > 12 → Moderate (was USG before the breakpoint fix)
USG = {'Mikolajska': {'pm2.5': '45', 'pm10': '70'}}
CLEAN = {'Mikolajska': {'pm2.5': '8', 'pm10': '12'}}


def _state(tmp_path):
    return (tmp_path / 'aqi_flag.txt').read_text(), (tmp_path / 'aqi_status.txt').read_text()


def test_first_run_posts_even_when_good(tmp_path, monkeypatch):
    # Regression: bool(None) == False used to kill the "unknown state"
    # branch, so a fresh bot with clean air never announced itself.
    calls = _run(GOOD, None, tmp_path, monkeypatch)
    assert [c[0] for c in calls] == ['media', 'status']
    assert 'back to normal' in calls[1][1]
    assert _state(tmp_path) == ('0', 'Good')


def test_good_to_good_is_quiet(tmp_path, monkeypatch):
    calls = _run(GOOD, False, tmp_path, monkeypatch)
    assert calls == []
    assert _state(tmp_path) == ('0', 'Good')


def test_good_to_polluted_alerts(tmp_path, monkeypatch):
    calls = _run(USG, False, tmp_path, monkeypatch)
    assert [c[0] for c in calls] == ['media', 'status']
    status = calls[1][1]
    assert 'UNHEALTHY FOR SENSITIVE GROUPS' in status
    assert '45' in status
    assert '#SMOG' in status
    assert _state(tmp_path) == ('1', 'Unhealthy for Sensitive Groups')


def test_polluted_to_good_recovery(tmp_path, monkeypatch):
    calls = _run(CLEAN, True, tmp_path, monkeypatch)
    assert 'back to normal' in calls[1][1]
    assert _state(tmp_path) == ('0', 'Good')


def test_polluted_to_polluted_repeats_hourly(tmp_path, monkeypatch):
    # While the air is bad the bot re-posts every run (alert cadence).
    calls = _run(USG, True, tmp_path, monkeypatch)
    assert [c[0] for c in calls] == ['media', 'status']
    assert _state(tmp_path) == ('1', 'Unhealthy for Sensitive Groups')


def test_moderate_band_uses_fixed_breakpoint(tmp_path, monkeypatch):
    # 25.5 µg/m³ must be classified Moderate (EPA 24-h band 12.1–35.4).
    # Anything not "Good" still triggers the bot's alert + flag (author's
    # design: alerts fire for every level above Good), but the status must
    # now read MODERATE instead of the old false "UNHEALTHY FOR SENSITIVE
    # GROUPS" alarm.
    calls = _run(MODERATE, False, tmp_path, monkeypatch)
    assert [c[0] for c in calls] == ['media', 'status']
    assert 'MODERATE' in calls[1][1]
    assert 'UNHEALTHY' not in calls[1][1]
    assert _state(tmp_path) == ('1', 'Moderate')


def test_average_over_all_reporting_sensors(tmp_path, monkeypatch):
    # The PM2.5 mean is computed over every reporting sensor (the old code
    # silently dropped all but the first three).
    measurements = {
        'A': {'pm2.5': '10'},
        'B': {'pm2.5': '40'},
    }
    calls = _run(measurements, False, tmp_path, monkeypatch)
    assert [c[0] for c in calls] == ['media', 'status']
    assert '25' in calls[1][1]             # avg (10+40)/2 = 25 → Moderate alert
    assert _state(tmp_path) == ('1', 'Moderate')


def test_unparseable_value_is_skipped_not_fatal(tmp_path, monkeypatch):
    # Junk from undecodable glyphs (e.g. decimal point) must not crash a run.
    measurements = {
        'A': {'pm2.5': '12M* *L* *Z5'},    # unparseable junk
        'B': {'pm2.5': '40'},              # fine → avg over valid sensors only
    }
    calls = _run(measurements, False, tmp_path, monkeypatch)
    assert [c[0] for c in calls] == ['media', 'status']


def test_all_unparseable_no_post(tmp_path, monkeypatch):
    measurements = {'A': {'pm2.5': 'junk'}}
    calls = _run(measurements, None, tmp_path, monkeypatch)
    assert calls == []
    assert not (tmp_path / 'aqi_flag.txt').exists()
    assert not (tmp_path / 'aqi_status.txt').exists()


def test_failed_post_keeps_previous_state(tmp_path, monkeypatch):
    # State files must only advance after a successful post so the transition
    # is retried on the next run.
    calls = _run(USG, False, tmp_path, monkeypatch, status_ok=False)
    assert calls and calls[0][0] == 'media' and calls[1][0] == 'status'
    assert not (tmp_path / 'aqi_flag.txt').exists()
    assert not (tmp_path / 'aqi_status.txt').exists()


def test_media_failure_still_posts_without_media(tmp_path, monkeypatch):
    calls = _run(USG, False, tmp_path, monkeypatch, media_ok=False)
    assert calls[1] == ('status', calls[1][1], [])
    assert _state(tmp_path) == ('1', 'Unhealthy for Sensitive Groups')


def test_missing_pm25_sensor_skipped(tmp_path, monkeypatch):
    measurements = {'A': {'pm10': '100'}}   # PM10 only — no PM2.5 → skipped
    calls = _run(measurements, None, tmp_path, monkeypatch)
    assert calls == []