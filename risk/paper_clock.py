"""Fail-closed Windows Time evidence diagnostics; no clock or execution mutation."""

import re
from decimal import Decimal


def check_windows_time(text, *, approved_source=None, max_error_seconds=None):
    reasons = []

    def numeric(label):
        match = re.search(r"^" + re.escape(label) + r": ([0-9]+(?:\.[0-9]+)?)", text, re.MULTILINE)
        return Decimal(match.group(1)) if match else None

    leap, stratum = numeric("Leap Indicator"), numeric("Stratum")
    delay, dispersion = numeric("Root Delay"), numeric("Root Dispersion")
    age, poll = numeric("Time since Last Good Sync Time"), numeric("Poll Interval")
    error = numeric("Last Sync Error")
    source = re.search(r"^Source: (.+)$", text, re.MULTILINE)
    source = source.group(1).strip() if source else None
    if leap != 0 or stratum is None or not 1 <= stratum <= 15 or error != 0:
        reasons.append("CLOCK_UNSYNCHRONIZED_OR_ERROR")
    if not approved_source or source != approved_source:
        reasons.append("CLOCK_SOURCE_UNAPPROVED")
    bound = dispersion + delay / 2 if dispersion is not None and delay is not None else None
    limit = Decimal(str(max_error_seconds)) if max_error_seconds is not None else None
    if limit is None:
        reasons.append("CLOCK_ERROR_POLICY_REQUIRED")
    elif not limit.is_finite() or limit <= 0:
        raise ValueError("Positive finite error policy required")
    elif bound is None or bound > limit:
        reasons.append("CLOCK_REPORTED_ERROR_BOUND")
    # Do not parse localized calendar timestamps; use the verbose age field.
    if (
        age is None
        or poll is None
        or not 0 <= poll <= 17
        or poll != poll.to_integral_value()
        or age > Decimal(2) ** poll
    ):
        reasons.append("CLOCK_SYNC_AGE")
    return {
        "checks_passed": not reasons,
        "blockers": reasons,
        "reported_error_bound_seconds": str(bound) if bound is not None else None,
        "execution_available": False,
    }
