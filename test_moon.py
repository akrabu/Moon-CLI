# Copyright (C) 2026 akrabu
# SPDX-License-Identifier: AGPL-3.0-only
# See LICENSE for the full license text.

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import moon


class MoonReportTests(unittest.TestCase):
    def test_known_sagittarius_void_and_capricorn_ingress(self):
        report = moon.moon_report(
            datetime(2026, 7, 25, 17, 0, tzinfo=timezone.utc),
            color=False,
        )
        self.assertEqual(
            report,
            "Moon in Sagittarius, "
            "void Saturday, July 25, 2026 at 2:58 PM UTC, "
            "next transit Sunday, July 26, 2026 at 1:44 PM UTC",
        )

    def test_report_uses_yellow_text_and_green_values(self):
        report = moon.moon_report(
            datetime(2026, 7, 25, 17, 0, tzinfo=timezone.utc)
        )
        self.assertTrue(report.startswith(f"{moon.YELLOW}Moon in "))
        self.assertIn(f"{moon.GREEN}Sagittarius{moon.YELLOW}, void ", report)
        self.assertIn(
            f"{moon.GREEN}Saturday, July 25, 2026 at 2:58 PM UTC"
            f"{moon.YELLOW}, next transit ",
            report,
        )
        self.assertTrue(
            report.endswith(
                f"{moon.GREEN}Sunday, July 26, 2026 at 1:44 PM UTC"
                f"{moon.YELLOW}{moon.RESET}"
            )
        )

    def test_utc_time_includes_weekday(self):
        moment = datetime(2026, 8, 5, 22, 33, tzinfo=timezone.utc)
        self.assertEqual(
            moon.format_time(moon.to_julian_day(moment)),
            "Wednesday, August 5, 2026 at 10:33 PM UTC",
        )

    def test_naive_cli_time_is_utc(self):
        parsed = moon.parse_time("2026-07-25T17:00")
        self.assertEqual(
            parsed, datetime(2026, 7, 25, 17, 0, tzinfo=timezone.utc)
        )

    def test_explicit_offset_is_respected(self):
        self.assertEqual(
            moon.parse_time("2000-01-01T14:00+02:00"),
            datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        )

    def test_display_timezone_changes_event_times(self):
        report = moon.moon_report(
            datetime(2026, 7, 25, 17, 0, tzinfo=timezone.utc),
            color=False,
            display_timezone=timezone(timedelta(hours=2)),
        )
        self.assertIn("Saturday, July 25, 2026 at 4:58 PM UTC+02:00", report)
        self.assertIn("Sunday, July 26, 2026 at 3:44 PM UTC+02:00", report)

    def test_rounding_across_daylight_saving_transition(self):
        moment = datetime(2026, 3, 29, 0, 59, 40, tzinfo=timezone.utc)
        self.assertEqual(
            moon.format_time(moon.to_julian_day(moment), ZoneInfo("Europe/London")),
            "Sunday, March 29, 2026 at 2:00 AM BST",
        )

    def test_invalid_timezone_is_an_argument_error(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            moon.parse_timezone("Invalid/Example")


class MoonStartupTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.script = self.directory / "moon.py"
        shutil.copy2(moon.__file__, self.script)

    def run_cli(self, script=None, python=None, isolated=True, extra_env=None, extra_args=()):
        command = [str(python or sys._base_executable)]
        if isolated:
            # Exclude installed packages so startup must handle the dependency.
            command.extend(("-I", "-S"))
        command.extend((str(script or self.script), "--at", "2026-07-25T17:00Z"))
        command.extend(extra_args)
        environment = os.environ.copy()
        environment.pop("NO_COLOR", None)
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            command,
            cwd=self.directory,
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )

    def test_cli_uses_project_environment_from_another_directory(self):
        result = self.run_cli(script=Path(moon.__file__).resolve())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            moon.moon_report(datetime(2026, 7, 25, 17, 0, tzinfo=timezone.utc)) + "\n",
        )
        self.assertEqual(result.stderr, "")

    def test_no_color_environment_is_respected(self):
        result = self.run_cli(
            script=Path(moon.__file__).resolve(), extra_env={"NO_COLOR": "1"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            moon.moon_report(
                datetime(2026, 7, 25, 17, 0, tzinfo=timezone.utc), color=False
            ) + "\n",
        )

    def test_cli_timezone_changes_display_without_changing_naive_input(self):
        result = self.run_cli(
            script=Path(moon.__file__).resolve(),
            extra_args=("--at", "2026-07-25T17:00", "--timezone", "Etc/GMT-2", "--no-color"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Saturday, July 25, 2026 at 4:58 PM +02", result.stdout)
        self.assertNotIn("\033[", result.stdout)

    def test_missing_environment_explains_setup(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("Missing dependency.", result.stderr)
        self.assertIn("python3 -m venv .venv", result.stderr)
        self.assertIn("pip install -r requirements.txt", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_environment_without_dependency_exits_without_restarting(self):
        environment = self.directory / ".venv"
        venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
        result = self.run_cli(python=environment / "bin" / "python", isolated=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing dependency.", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unusable_environment_explains_setup(self):
        project_python = self.directory / ".venv" / "bin" / "python"
        project_python.parent.mkdir(parents=True)
        project_python.write_text("unusable interpreter\n")
        project_python.chmod(0o644)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn(f"Cannot run {project_python}:", result.stderr)
        self.assertIn("pip install -r requirements.txt", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
