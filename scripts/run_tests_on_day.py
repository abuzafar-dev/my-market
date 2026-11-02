"""Run the test suite as if today were the given day (Asia/Tashkent noon).

    .venv/bin/python scripts/run_tests_on_day.py 2026-11-02 apps.reports apps.sales
    TZ=UTC .venv/bin/python scripts/run_tests_on_day.py 2026-11-02 --at 02:00 apps.reports

``--at HH:MM`` (Tashkent time, default 12:00) covers the night: with the
server on UTC, 00:00–05:00 in Tashkent is still "yesterday" for date.today(),
so only timezone.localdate() gives the shop's day.

The whole process clock is moved (time-machine, dev-only), starting at noon
in Tashkent and ticking on — so model defaults bound at import time
(``default=timezone.now``), timezone.localdate(), date.today() all agree.
Patching only django.utils.timezone.now does not work: field defaults keep a
reference to the original function. CI runs this for a Monday, the 1st, New
Year's Day and 29 February — the days on which week/month/year boundaries
collapse to a single day, where the "by day on a Monday" report bug hid.
"""

import os
import sys
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    day = date.fromisoformat(argv[1])
    labels = argv[2:]
    at = time(12)
    if labels[:1] == ["--at"]:
        at = time.fromisoformat(labels[1])
        labels = labels[2:]

    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    import django
    import time_machine

    django.setup()
    from django.conf import settings
    from django.test.utils import get_runner

    start = datetime.combine(day, at, tzinfo=ZoneInfo("Asia/Tashkent"))
    print(f"--- tests on {start.isoformat()} ({day.strftime('%A')}) ---", flush=True)
    with time_machine.travel(start, tick=True):
        runner = get_runner(settings)(verbosity=1)
        failures = runner.run_tests(labels)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
