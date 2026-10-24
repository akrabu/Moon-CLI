#!/usr/bin/env python3
# Copyright (C) 2026 akrabu
# SPDX-License-Identifier: AGPL-3.0-only
# See LICENSE for the full license text.
"""Print the Moon's sign, void-of-course start, and next sign ingress."""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import swisseph as swe
except ImportError as error:
    project_env = Path(__file__).resolve().parent / ".venv"
    project_python = project_env / "bin" / "python"
    dependency_error = (
        "Missing dependency. From the Moon-CLI directory, create and install "
        "the project environment with:\n"
        "  python3 -m venv .venv\n"
        "  .venv/bin/python -m pip install -r requirements.txt\n"
        "Then run ./moon.py."
    )
    if (
        __name__ == "__main__"
        and project_python.is_file()
        and Path(sys.prefix).resolve() != project_env
    ):
        try:
            os.execv(
                str(project_python),
                [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]],
            )
        except OSError as environment_error:
            raise SystemExit(
                f"Cannot run {project_python}: {environment_error.strerror}\n"
                f"{dependency_error}"
            ) from environment_error
    raise SystemExit(dependency_error) from error


UTC = timezone.utc
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)
CLASSICAL_BODIES = (
    swe.SUN,
    swe.MERCURY,
    swe.VENUS,
    swe.MARS,
    swe.JUPITER,
    swe.SATURN,
)
# Both directions for sextiles, squares, and trines.
MAJOR_ASPECTS = (0.0, 60.0, 90.0, 120.0, 180.0, 240.0, 270.0, 300.0)
CALC_FLAGS = swe.FLG_MOSEPH
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# Initialize Swiss Ephemeris without an ephemeris-file path. FLG_MOSEPH above
# explicitly selects its built-in, offline Moshier calculations.
swe.set_ephe_path(None)


def to_julian_day(moment: datetime) -> float:
    moment = moment.astimezone(UTC)
    return 2440587.5 + (moment - EPOCH).total_seconds() / 86400.0


def from_julian_day(julian_day: float) -> datetime:
    return EPOCH + timedelta(days=julian_day - 2440587.5)


def longitude(body: int, julian_day: float) -> float:
    return swe.calc_ut(julian_day, body, CALC_FLAGS)[0][0] % 360.0


def bisect_time(function, start: float, end: float, target: float) -> float:
    """Find a target of a monotonic function to substantially under one second."""
    start_value = function(start)
    end_value = function(end)
    low, high = sorted((start_value, end_value))
    if not low - 1e-8 <= target <= high + 1e-8:
        raise ValueError("The requested event is not bracketed")

    ascending = end_value >= start_value
    while (end - start) * 86400.0 > 0.25:
        middle = (start + end) / 2.0
        below = function(middle) < target
        if below == ascending:
            start = middle
        else:
            end = middle
    return (start + end) / 2.0


def moon_ingress(now: float, forward: bool) -> float:
    """Find the next or previous 30-degree tropical-zodiac boundary."""
    current_longitude = longitude(swe.MOON, now)

    if forward:
        target = 30.0 - current_longitude % 30.0

        def progress(julian_day: float) -> float:
            return (longitude(swe.MOON, julian_day) - current_longitude) % 360.0

        start, end = now, now + 0.25
        for _ in range(16):
            if progress(end) >= target:
                return bisect_time(progress, start, end, target)
            end += 0.25
    else:
        target = current_longitude % 30.0
        if target < 1e-10:
            return now

        def progress(julian_day: float) -> float:
            return (current_longitude - longitude(swe.MOON, julian_day)) % 360.0

        start, end = now - 0.25, now
        for _ in range(16):
            if progress(start) >= target:
                return bisect_time(progress, start, end, target)
            start -= 0.25

    raise RuntimeError("Could not bracket the Moon's sign ingress")


def void_start(sign_start: float, sign_end: float) -> float:
    """Return the last exact classical major aspect in the Moon's current sign."""
    last_aspect = sign_start
    moon_at_start = longitude(swe.MOON, sign_start)

    for body in CLASSICAL_BODIES:
        relative_start = (moon_at_start - longitude(body, sign_start)) % 360.0

        def relative_longitude(julian_day: float) -> float:
            relative = (
                longitude(swe.MOON, julian_day) - longitude(body, julian_day)
            ) % 360.0
            return relative_start + (relative - relative_start) % 360.0

        relative_end = relative_longitude(sign_end)
        for aspect in MAJOR_ASPECTS:
            first_cycle = math.ceil((relative_start - aspect - 1e-9) / 360.0)
            last_cycle = math.floor((relative_end - aspect + 1e-9) / 360.0)
            for cycle in range(first_cycle, last_cycle + 1):
                target = aspect + 360.0 * cycle
                last_aspect = max(
                    last_aspect,
                    bisect_time(
                        relative_longitude, sign_start, sign_end, target
                    ),
                )

    # A sign with no exact major aspect is void from its ingress.
    return last_aspect


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "use an ISO 8601 time, for example 2000-01-01T12:00Z"
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise argparse.ArgumentTypeError("use a valid IANA timezone, for example UTC") from error


def format_time(julian_day: float, display_timezone: tzinfo = UTC) -> str:
    # Round the instant in UTC first so DST transitions remain unambiguous.
    rounded = (from_julian_day(julian_day) + timedelta(seconds=30)).replace(
        second=0, microsecond=0
    )
    local = rounded.astimezone(display_timezone)
    hour = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return (
        f"{local:%A, %B} {local.day}, {local.year} at "
        f"{hour}:{local.minute:02d} {meridiem} {local.tzname()}"
    )


def moon_report(
    moment: datetime, color: bool = True, display_timezone: tzinfo = UTC
) -> str:
    now = to_julian_day(moment)
    sign = SIGNS[int(longitude(swe.MOON, now) // 30.0)]
    sign_start = moon_ingress(now, forward=False)
    sign_end = moon_ingress(now, forward=True)
    void = void_start(sign_start, sign_end)
    yellow, green, reset = (YELLOW, GREEN, RESET) if color else ("", "", "")
    return (
        f"{yellow}Moon in {green}{sign}{yellow}, void "
        f"{green}{format_time(void, display_timezone)}{yellow}, next transit "
        f"{green}{format_time(sign_end, display_timezone)}{yellow}{reset}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--at",
        type=parse_time,
        help="ISO 8601 calculation time; a time without an offset is UTC",
    )
    parser.add_argument(
        "--timezone", type=parse_timezone, default=UTC,
        help="IANA timezone for displayed events (default: UTC)",
    )
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    args = parser.parse_args()
    print(moon_report(
        args.at or datetime.now(UTC),
        color=not args.no_color and "NO_COLOR" not in os.environ,
        display_timezone=args.timezone,
    ))


if __name__ == "__main__":
    main()
