# pushaqi

A small Mastodon bot that watches the air in Kraków and posts a US AQI alert
when the PM2.5 level turns unhealthy — and lets the city know when it clears
up. 🍃

It reads live readings from six [Airly](https://airly.org) monitoring stations
(Mikolajska, Szpitalna, Franciszkanska, Warszawska, Studencka,
Straszewskiego), computes the PM2.5 average, maps it to the US AQI category,
and posts the result with an AQI-colored image to Mastodon. The whole thing is
designed to run unattended on a cron schedule (a GitHub Actions workflow here)
and to persist its state between runs in the repository itself.

## How it works

Airly's public widget renders live values as **SVG paths** — the digits are
vector glyphs, not text. The Airly API requires an API key, but the widget
page is public, so the bot fetches the widget HTML and decodes the numbers out
of the SVG path data:

1. `pull_measurements()` downloads each station's widget page and extracts the
   PM10 / PM2.5 / PM1 measurement blocks with `lxml`.
2. Each value is an SVG path (`d` attribute) like
   `M5.40 18.23L5.40 18.23Q3.13 ... Z`. `svg_path_reduce()` normalizes all
   coordinates to `*`, producing a compact *glyph signature*.
3. `svg_path_to_number()` matches each signature against `CHAR_MAP` (a lookup
   table of digit and minus signatures) and concatenates the decoded digits.

If Airly changes the widget markup, the glyph signatures may no longer match —
check `--test-chars` / `--test-nums`, which run the bundled recognition test
vectors.

### AQI computation

The PM2.5 readings from all reporting stations are averaged and mapped to the
US AQI category using the EPA 24-hour PM2.5 breakpoints (the same bands the
`AIRLY_US_AQI` widget index uses):

| PM2.5 average (µg/m³) | Category |
|---|---|
| 0.0 – 12.0 | Good |
| 12.1 – 35.4 | Moderate |
| 35.5 – 55.4 | Unhealthy for Sensitive Groups |
| 55.5 – 150.4 | Unhealthy |
| 150.5 – 250.4 | Very Unhealthy |
| 250.5 – 500.4 | Hazardous |

> **Caveat:** AQI is formally defined for 24-hour averages. This bot uses
> instantaneous widget readings, which is the common community practice for
> "now" air-quality bots, but treat the numbers as indicative rather than a
> formal regulatory measurement.

### Posting state machine

To avoid spamming, the bot only posts when the *state* changes, with one
exception: while the air is polluted it posts an hourly alert. State is
persisted in the repository as two files:

- `aqi_flag.txt` — `1` when the last published state was polluted, `0` otherwise
- `aqi_status.txt` — last published AQI category, e.g. `Moderate`

The previous flag is passed back into the next run as the positional
`former_aqi` argument (`python3 pusher.py $(cat aqi_flag.txt)`), so a run
knows whether the air quality changed:

| previous | current | posts? |
|---|---|---|
| unknown (first run) | any | yes (announces state) |
| good | good | no |
| good | polluted | yes (alert) |
| polluted | polluted | yes (hourly alert) |
| polluted | good | yes (back to normal) |

State files are only updated **after** a successful post, so a failed post is
retried on the next run instead of being silently forgotten.

## Setup

```bash
pip install .          # or: pip install -e ".[dev]"
```

The bot authentication comes from environment variables:

- `SERVER` — your Mastodon instance, e.g. `https://mastodon.social`
- `TOKEN` — an access token with `write:media` and `write:statuses` scopes

### Run

```bash
# Post the current AQI (previous flag from the last run, or omit on first run)
python3 pusher.py $(cat aqi_flag.txt)

# Preview what the stations report right now
python3 pusher.py --report

# Self-test the SVG digit decoder
python3 pusher.py --test-chars
python3 pusher.py --test-nums
```

### Deployment

The included GitHub Actions workflow (`.github/workflows/pusher.yml`) runs the
bot every hour at minute 55:

- `SERVER` and `TOKEN` are configured as repository secrets.
- `aqi_flag.txt` is committed back after each run so the next invocation knows
  the previous state. (`commit.sh` handles the commit-and-push.)

### Tests

```bash
pip install -e ".[dev]"
pytest
```

The test suite is fully offline — network and Mastodon calls are mocked.

## Disclaimer

This project is not affiliated with or endorsed by Airly. The widget-scraping
approach works on the current public widget markup and may break if Airly
changes it. The status posts are not medical advice.