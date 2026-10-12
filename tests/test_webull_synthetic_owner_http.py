"""Real loopback HTTP with synthetic signing and injected guardian dispatch."""

import socket

from scripts.webull_signed_host_fixture import synthetic_http_review
from security.webull_guardian_reference import GuardianReference
from security.webull_owner_review_app import create_app
from security.webull_review_journal import ReviewJournal
from tests.test_webull_review_signature import signed_review


def test_http_cookie_challenge_signature_confirmation_and_listener_close(tmp_path):
    receipt, credential, envelope, now, _ = signed_review()
    journal = ReviewJournal.initialize(tmp_path / "review.sqlite", expected_envelope=envelope)
    directory = tmp_path.parent / (tmp_path.name + "-guardian")
    directory.mkdir()
    guardian = GuardianReference(directory, journal, credential)
    actions = []

    def exchange(raw):
        actions.append(raw)
        return guardian.handle(raw, now=now) | {"owner_pipe_identity_observed": True}

    app = create_app(
        None, None, None,
        context_loader=lambda: (envelope, credential, journal),
        now=lambda: now, guardian_exchange=exchange,
    )
    readiness = []

    def ready():
        assert actions == []
        assert journal.verify(credential)["retained_review_count"] == 0
        readiness.append("HTTP_CHALLENGE_READY_BEFORE_GUARDIAN_EXCHANGE")

    result = synthetic_http_review(app, receipt, envelope, before_complete=ready)
    assert readiness == ["HTTP_CHALLENGE_READY_BEFORE_GUARDIAN_EXCHANGE"]
    assert result["synthetic_http_roundtrip_verified"] is True
    assert result["guardian_reference_confirmed"] is True
    assert result["reset_authorized"] is False
    assert len(actions) == 2
    assert journal.verify(credential)["retained_review_count"] == 1
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", 8767)) != 0
