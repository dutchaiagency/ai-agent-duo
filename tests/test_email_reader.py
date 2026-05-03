"""Tests for ops/email_reader.py noise filter and listing."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import email_reader  # type: ignore  # noqa: E402


def _msg(
    msg_id: str,
    subject: str,
    sender: str,
    unread: int = 1,
    time: int = 0,
    body: str = "",
):
    return SimpleNamespace(
        id=msg_id,
        subject=subject,
        sender=sender,
        unread=unread,
        time=time,
        body=body,
    )


class _FakeProton:
    def __init__(self, messages):
        self._messages = messages
        self.read_ids = []

    def get_messages(self):
        return self._messages

    def read_message(self, msg):
        self.read_ids.append(msg.id)
        return msg


class _NoisyFakeProton(_FakeProton):
    def get_messages(self):
        print("_async_get_messages: 100%", file=sys.stderr)
        return self._messages


def test_is_noise_sender_matches_known_substrings():
    assert email_reader.is_noise_sender("<UserMail [no-reply@notify.proton.me]>")
    assert email_reader.is_noise_sender("<UserMail [noreply@gumroad.com]>")
    assert email_reader.is_noise_sender("<UserMail [yo@dev.to]>")
    assert email_reader.is_noise_sender("<UserMail [notifier@farcaster.xyz]>")
    assert email_reader.is_noise_sender("<UserMail [dutchaiagents@proton.me]>")


def test_is_noise_sender_rejects_real_inbound():
    assert not email_reader.is_noise_sender("<UserMail [sam@swlock.co.uk]>")
    assert not email_reader.is_noise_sender("<UserMail [joseph.d.barrow@gmail.com]>")
    assert not email_reader.is_noise_sender("")
    assert not email_reader.is_noise_sender(None)


def test_list_messages_default_includes_noise():
    proton = _FakeProton([
        _msg("a", "smoke-test", "<UserMail [dutchaiagents@proton.me]>"),
        _msg("b", "Protect yourself", "<UserMail [no-reply@notify.proton.me]>"),
        _msg("c", "real reply", "<UserMail [sam@swlock.co.uk]>"),
    ])
    results = email_reader.list_messages(proton)
    ids = [r["id"] for r in results]
    assert ids == ["a", "b", "c"]


def test_list_messages_exclude_noise_filters_known_senders():
    proton = _FakeProton([
        _msg("a", "smoke-test", "<UserMail [dutchaiagents@proton.me]>"),
        _msg("b", "Protect yourself", "<UserMail [no-reply@notify.proton.me]>"),
        _msg("c", "Confirmation", "<UserMail [noreply@gumroad.com]>"),
        _msg("d", "real reply", "<UserMail [sam@swlock.co.uk]>"),
        _msg("e", "badge", "<UserMail [yo@dev.to]>"),
    ])
    results = email_reader.list_messages(proton, exclude_noise=True)
    ids = [r["id"] for r in results]
    assert ids == ["d"]


def test_list_messages_unread_and_exclude_noise_compose():
    proton = _FakeProton([
        _msg("read-real", "thanks", "<UserMail [sam@swlock.co.uk]>", unread=0),
        _msg("unread-noise", "badge", "<UserMail [yo@dev.to]>", unread=1),
        _msg("unread-real", "scope question", "<UserMail [joe@example.com]>", unread=1),
    ])
    results = email_reader.list_messages(proton, unread_only=True, exclude_noise=True)
    ids = [r["id"] for r in results]
    assert ids == ["unread-real"]


def test_list_messages_limit_respected_after_filter():
    msgs = [
        _msg(f"noise-{i}", "n", "<UserMail [no-reply@notify.proton.me]>")
        for i in range(10)
    ] + [
        _msg(f"real-{i}", "r", "<UserMail [user@example.com]>")
        for i in range(5)
    ]
    proton = _FakeProton(msgs)
    results = email_reader.list_messages(proton, exclude_noise=True, limit=3)
    assert len(results) == 3
    assert all(r["id"].startswith("real-") for r in results)


def test_list_messages_suppresses_client_progress_noise(capsys):
    proton = _NoisyFakeProton([
        _msg("real", "scope question", "<UserMail [joe@example.com]>"),
    ])

    results = email_reader.list_messages(proton)

    assert results[0]["id"] == "real"
    assert "_async_get_messages" not in capsys.readouterr().err


def test_search_messages_defaults_to_subject_and_sender_only():
    proton = _FakeProton([
        _msg("body-only", "Scheduling", "<UserMail [founder@example.com]>", body="Wetware call?"),
        _msg("subject", "Wetware intro", "<UserMail [founder@example.com]>"),
        _msg("sender", "hello", "<UserMail [wetware@example.com]>"),
    ])

    results = email_reader.search_messages(proton, "wetware")

    assert [r["id"] for r in results] == ["subject", "sender"]
    assert proton.read_ids == []


def test_search_messages_can_match_body_when_explicit():
    proton = _FakeProton([
        _msg(
            "body-only",
            "Scheduling",
            "<UserMail [founder@example.com]>",
            body="Could we do the Wetware demo tomorrow morning?",
        ),
    ])

    results = email_reader.search_messages(proton, "wetware", include_body=True)

    assert [r["id"] for r in results] == ["body-only"]
    assert results[0]["matched_fields"] == ["body"]
    assert "Wetware demo" in results[0]["body_snippet"]
    assert proton.read_ids == ["body-only"]


def test_search_messages_body_mode_respects_unread_and_noise_filters():
    proton = _FakeProton([
        _msg("read", "hello", "<UserMail [lead@example.com]>", unread=0, body="wetware"),
        _msg("noise", "hello", "<UserMail [yo@dev.to]>", unread=1, body="wetware"),
        _msg("real", "hello", "<UserMail [lead@example.com]>", unread=1, body="wetware"),
    ])

    results = email_reader.search_messages(
        proton,
        "wetware",
        unread_only=True,
        exclude_noise=True,
        include_body=True,
    )

    assert [r["id"] for r in results] == ["real"]
    assert proton.read_ids == ["real"]
