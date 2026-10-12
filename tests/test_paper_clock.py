import pytest

from risk.paper_clock import check_windows_time

TEXT = """Leap Indicator: 0(no warning)
Stratum: 5
Root Delay: 0.05s
Root Dispersion: 0.2s
Source: time.windows.com,0x9
Poll Interval: 10 (1024s)
Last Sync Error: 0
Time since Last Good Sync Time: 30s
"""


def test_verified_sync_reports_bound_but_never_execution_permission():
    x = check_windows_time(TEXT, approved_source="time.windows.com,0x9", max_error_seconds="0.225")
    assert x["checks_passed"] and not x["execution_available"]
    assert (
        "CLOCK_REPORTED_ERROR_BOUND"
        in check_windows_time(
            TEXT, approved_source="time.windows.com,0x9", max_error_seconds="0.224"
        )["blockers"]
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        TEXT.replace("Leap Indicator: 0", "Leap Indicator: 3"),
        TEXT.replace("Last Sync Error: 0", "Last Sync Error: 1"),
        TEXT.replace("30s", "1025s"),
    ],
)
def test_missing_unsynced_failed_or_old_time_evidence_blocks(text):
    assert check_windows_time(text, approved_source="time.windows.com,0x9", max_error_seconds=1)[
        "blockers"
    ]


def test_source_and_error_policy_cannot_be_assumed():
    x = check_windows_time(TEXT)
    assert {"CLOCK_SOURCE_UNAPPROVED", "CLOCK_ERROR_POLICY_REQUIRED"} <= set(x["blockers"])
