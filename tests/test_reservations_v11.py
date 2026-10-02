import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk.reservations_v11 import ReservationError, ReservationIntent, SyntheticReservations


def intent(name="p1", amount="250", digest="a"*64):
    return ReservationIntent(proposal_id=name, proposal_digest=digest, amount=amount)


def store(tmp_path, cash="1000", sleeve="750"):
    return SyntheticReservations.initialize(tmp_path/"synthetic.db", cash=Decimal(cash), sleeve=Decimal(sleeve))


def test_reserve_replay_and_idempotency(tmp_path):
    s = store(tmp_path)
    a = s.reserve(intent())
    assert s.reserve(intent()) == a
    assert a.committed == 250 and a.sleeve_available == 500 and not a.execution_available
    assert SyntheticReservations(s.path).snapshot() == a
    for changed in [intent(amount="251"), intent(digest="b"*64)]:
        with pytest.raises(ReservationError):
            s.reserve(changed)


@pytest.mark.parametrize("cash,sleeve", [("249", "1000"), ("1000", "249")])
def test_each_capacity_blocks_independently(tmp_path, cash, sleeve):
    s = store(tmp_path, cash, sleeve)
    with pytest.raises(ReservationError):
        s.reserve(intent())
    assert s.snapshot().committed == 0


@pytest.mark.parametrize("status", ["PARTIAL", "PENDING_CANCEL", "UNKNOWN", "CANCELED", "FILLED"])
def test_unverified_status_never_releases_capacity(tmp_path, status):
    s = store(tmp_path); s.reserve(intent())
    snap = s.reconcile("p1", cumulative_filled=Decimal(100), status=status)
    assert snap.committed == 250
    assert SyntheticReservations(s.path).snapshot() == snap


@pytest.mark.parametrize("status", ["CANCELED", "REJECTED", "FILLED"])
def test_verified_terminal_releases_only_unfilled_and_keeps_cost(tmp_path, status):
    s = store(tmp_path); s.reserve(intent())
    s.reconcile("p1", cumulative_filled=Decimal(100), status="PARTIAL")
    snap = s.reconcile("p1", cumulative_filled=Decimal(100), status=status, synthetic_terminal_verified=True)
    assert snap.committed == 100 and snap.sleeve_available == 650
    assert s.reconcile("p1", cumulative_filled=Decimal(100), status=status, synthetic_terminal_verified=True) == snap
    with pytest.raises(ReservationError):
        s.reserve(intent())
    with pytest.raises(ReservationError):
        s.reconcile("p1", cumulative_filled=Decimal(100), status="OPEN")


def test_invalid_fill_does_not_release(tmp_path):
    s = store(tmp_path); s.reserve(intent())
    s.reconcile("p1", cumulative_filled=Decimal(100), status="PARTIAL")
    for fill in [Decimal(99), Decimal(251), Decimal("NaN")]:
        with pytest.raises(ReservationError):
            s.reconcile("p1", cumulative_filled=fill, status="CANCELED", synthetic_terminal_verified=True)
    assert s.snapshot().committed == 250


def test_concurrent_proposals_cannot_overreserve(tmp_path):
    s = store(tmp_path, "250", "250")
    def reserve(i):
        try:
            SyntheticReservations(s.path).reserve(intent(str(i)))
            return True
        except ReservationError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(4))) == 1
    assert s.snapshot().committed == 250


def test_missing_and_corrupt_store_fail_closed(tmp_path):
    with pytest.raises(ReservationError):
        SyntheticReservations(tmp_path/"missing.db").snapshot()
    assert not (tmp_path/"missing.db").exists()
    s = store(tmp_path); s.reserve(intent())
    with sqlite3.connect(s.path) as db:
        db.execute("UPDATE events SET digest='bad' WHERE seq=2")
    with pytest.raises(ReservationError):
        s.snapshot()


def test_failed_append_is_atomic(tmp_path):
    s = store(tmp_path)
    with sqlite3.connect(s.path) as db:
        db.execute("CREATE TRIGGER fail BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'fixture'); END")
    with pytest.raises(ReservationError):
        s.reserve(intent())
    assert s.snapshot().committed == 0


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity"])
def test_invalid_amount_rejected(amount):
    with pytest.raises(ValidationError):
        intent(amount=amount)


def test_concurrent_duplicate_is_exactly_once(tmp_path):
    s = store(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: SyntheticReservations(s.path).reserve(intent()), range(4)))
    assert all(result.committed == 250 for result in results)
    with sqlite3.connect(s.path) as db:
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 2


def test_partial_fill_restart_then_terminal_release(tmp_path):
    s = store(tmp_path); s.reserve(intent())
    s.reconcile("p1", cumulative_filled=Decimal(100), status="PARTIAL")
    recovered = SyntheticReservations(s.path)
    assert recovered.snapshot().committed == 250
    result = recovered.reconcile("p1", cumulative_filled=Decimal(150), status="CANCELED",
                                 synthetic_terminal_verified=True)
    assert result.committed == 150
    assert SyntheticReservations(s.path).snapshot() == result


def test_existing_database_and_unknown_order_refused(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ReservationError):
        SyntheticReservations.initialize(s.path, cash=Decimal(1000), sleeve=Decimal(750))
    with pytest.raises(ReservationError):
        s.reconcile("missing", cumulative_filled=Decimal(0), status="CANCELED",
                    synthetic_terminal_verified=True)
    assert s.snapshot().committed == 0
