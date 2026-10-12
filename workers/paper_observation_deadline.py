"""Bounded read-only observation dispatch; never admits a late result."""

from queue import Empty, Queue
from threading import Thread


def bounded_observation(read, *, timeout_seconds, on_timeout):
    """Timeout callback must durably latch the caller's control state.

    Python cannot cancel a blocked reader thread. After timeout no new worker is
    launched here, and any eventual result is discarded. Caller must stop/recover
    the service before another cycle. This is not the qualified order watchdog.
    """
    if not 0 < timeout_seconds <= 5:
        raise ValueError("Observation deadline must be within five seconds")
    result = Queue(maxsize=1)

    def work():
        try:
            result.put((True, read()))
        except Exception as exc:  # noqa: BLE001 - transport exception to caller unchanged
            result.put((False, exc))

    Thread(target=work, daemon=True).start()
    try:
        success, value = result.get(timeout=timeout_seconds)
    except Empty:
        blockers = ["OBSERVER_DEADLINE_MISSED", "SERVICE_RECOVERY_REQUIRED"]
        try:
            on_timeout("OBSERVER_DEADLINE_MISSED")
        except (RuntimeError, ValueError, TypeError, OSError):
            blockers.append("OBSERVER_PERSISTENCE_FAILED")
        return {
            "blockers": blockers,
            "execution_available": False,
            "trial_started": False,
        }
    if not success:
        raise value
    return value
