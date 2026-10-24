# Moon-CLI

A small offline command-line tool that reports the Moon's current tropical
zodiac sign, its void-of-course start, and the next sign ingress.

## Install and run

Requires Python 3.11 or newer on Linux or macOS.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./moon.py
```

The script automatically uses the project-local `.venv` when the current
interpreter cannot import its dependency. All calculations work offline after
installation. A compiler may be needed if `pysweph` has no wheel for your
Python version and platform.

## Options

```sh
./moon.py --at 2000-01-01T12:00Z --no-color
./moon.py --timezone Europe/London
```

`--at` accepts an ISO 8601 timestamp. A timestamp without an offset is always
interpreted as UTC. Displayed event times also default to UTC; `--timezone`
selects an IANA timezone for display, including daylight-saving transitions.
Changing the display timezone does not change how a naive `--at` is parsed.

Times include the weekday and are rounded to the nearest minute. Output uses
yellow text with green values; `--no-color` or the `NO_COLOR` environment
variable disables ANSI colors. No location, account, or configuration file is
required.

## Convention

Calculations are geocentric and use the tropical zodiac. Void of course begins
after the final exact conjunction, sextile, square, trine, or opposition to
the Sun, Mercury, Venus, Mars, Jupiter, or Saturn before the Moon enters its
next sign. If no such aspect occurs in a sign, that sign is void from ingress.
The reported void start can therefore be in the past. `next transit` means
the next sign ingress.

Swiss Ephemeris's built-in Moshier model is selected explicitly, so runtime
needs no downloaded ephemeris files. Numerical event roots are resolved to
under one second before minute rounding; this numerical tolerance is separate
from the underlying model's astronomical accuracy.

## Tests

```sh
.venv/bin/python -m unittest -v
```

Tests cover known events, UTC parsing, timezone display, and startup with
missing or unusable environments. Fixtures are fixed example timestamps.

## License

Copyright (C) 2026 akrabu. Licensed under GNU AGPL version 3 only, without
warranty. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
