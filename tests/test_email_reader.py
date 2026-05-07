"""Tests for ops/email_reader.py noise filter and listing."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

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


class _FakeSessionProton:
    def __init__(self, fail_paths=()):
        self.fail_paths = {str(path) for path in fail_paths}
        self.loaded_paths = []

    def load_session(self, path: str):
        self.loaded_paths.append(path)
        if path in self.fail_paths:
            raise RuntimeError("bad session")

    def get_messages(self):
        return []


class _ValidatingFakeSessionProton(_FakeSessionProton):
    def __init__(self, fail_paths=(), expired_paths=()):
        super().__init__(fail_paths=fail_paths)
        self.expired_paths = {str(path) for path in expired_paths}

    def get_messages(self):
        current_path = self.loaded_paths[-1]
        if current_path in self.expired_paths:
            raise RuntimeError(
                "Can't update tokens, status: 400 json: {'Error': 'Invalid refresh token'}"
            )
        return []


class _FreshLoginFakeProton:
    def __init__(self, fail_validation=False):
        self.fail_validation = fail_validation
        self.login_args = None
        self.saved_paths = []
        self.get_messages_calls = 0

    def login(self, username: str, password: str):
        self.login_args = (username, password)

    def save_session(self, path: str):
        self.saved_paths.append(path)

    def get_messages(self):
        self.get_messages_calls += 1
        if self.fail_validation:
            raise RuntimeError(
                "Can't update tokens, status: 400 json: {'Error': 'Invalid refresh token'}"
            )
        return []


def _install_fake_protonmail(monkeypatch, proton):
    monkeypatch.setitem(
        sys.modules,
        "protonmail",
        SimpleNamespace(ProtonMail=lambda: proton),
    )


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


def test_session_candidates_include_current_then_newest_backups(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        secrets = Path(tmp)
        current = secrets / "proton_session.pickle"
        older = secrets / "proton_session.pickle.bak-old"
        newer = secrets / "proton_session.pickle.bak-new"
        current.write_text("current", encoding="utf-8")
        older.write_text("older", encoding="utf-8")
        newer.write_text("newer", encoding="utf-8")
        older_time = 1_700_000_000
        newer_time = 1_700_000_100
        older.touch()
        newer.touch()
        import os

        os.utime(older, (older_time, older_time))
        os.utime(newer, (newer_time, newer_time))

        monkeypatch.setattr(email_reader, "SECRETS_DIR", secrets)
        monkeypatch.setattr(email_reader, "SESSION_FILE", current)

        candidates = email_reader.session_candidates()

    assert candidates == (current, newer, older)


def test_load_saved_session_tries_backup_and_restores_canonical_file(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        secrets = Path(tmp)
        current = secrets / "proton_session.pickle"
        backup = secrets / "proton_session.pickle.bak-20260503-184102"
        current.write_text("bad", encoding="utf-8")
        backup.write_text("good", encoding="utf-8")
        monkeypatch.setattr(email_reader, "SECRETS_DIR", secrets)
        monkeypatch.setattr(email_reader, "SESSION_FILE", current)
        proton = _FakeSessionProton(fail_paths=(current,))

        loaded = email_reader.load_saved_session(proton)

        assert loaded == backup
        assert proton.loaded_paths == [str(current), str(backup)]
        assert current.read_text(encoding="utf-8") == "good"


def test_load_saved_session_skips_expired_backup_when_validating(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        secrets = Path(tmp)
        expired = secrets / "proton_session.pickle.bak-expired"
        valid = secrets / "proton_session.pickle.bak-valid"
        current = secrets / "proton_session.pickle"
        expired.write_text("expired", encoding="utf-8")
        valid.write_text("valid", encoding="utf-8")
        import os

        os.utime(expired, (1_700_000_100, 1_700_000_100))
        os.utime(valid, (1_700_000_000, 1_700_000_000))
        monkeypatch.setattr(email_reader, "SECRETS_DIR", secrets)
        monkeypatch.setattr(email_reader, "SESSION_FILE", current)
        proton = _ValidatingFakeSessionProton(expired_paths=(expired,))

        loaded = email_reader.load_saved_session(
            proton,
            validate=email_reader.validate_saved_session,
        )

        assert loaded == valid
        assert proton.loaded_paths == [str(expired), str(valid)]
        assert not expired.exists()
        assert current.read_text(encoding="utf-8") == "valid"


def test_get_client_validates_fresh_login_before_saving(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        secrets = Path(tmp)
        current = secrets / "proton_session.pickle"
        monkeypatch.setattr(email_reader, "SECRETS_DIR", secrets)
        monkeypatch.setattr(email_reader, "SESSION_FILE", current)
        monkeypatch.setattr(email_reader, "get_credentials", lambda: ("user", "pass"))
        proton = _FreshLoginFakeProton()
        _install_fake_protonmail(monkeypatch, proton)

        client = email_reader.get_client()

        assert client is proton
        assert proton.login_args == ("user", "pass")
        assert proton.get_messages_calls == 1
        assert proton.saved_paths == [str(current)]


def test_get_client_blocks_when_fresh_login_session_is_revoked(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        secrets = Path(tmp)
        current = secrets / "proton_session.pickle"
        monkeypatch.setattr(email_reader, "SECRETS_DIR", secrets)
        monkeypatch.setattr(email_reader, "SESSION_FILE", current)
        monkeypatch.setattr(email_reader, "get_credentials", lambda: ("user", "pass"))
        proton = _FreshLoginFakeProton(fail_validation=True)
        _install_fake_protonmail(monkeypatch, proton)

        with pytest.raises(email_reader.EmailLoginBlocked):
            email_reader.get_client()

        assert proton.login_args == ("user", "pass")
        assert proton.get_messages_calls == 1
        assert proton.saved_paths == []
        assert not current.exists()


def test_captcha_errors_are_classified_without_importing_protonmail():
    assert email_reader.is_captcha_error(RuntimeError("Validate CAPTCHA returns code: 404"))
    assert not email_reader.is_captcha_error(RuntimeError("network timeout"))


def test_invalid_refresh_token_errors_are_classified():
    assert email_reader.is_session_expired_error(
        RuntimeError("Can't update tokens, status: 400 json: {'Error': 'Invalid refresh token'}")
    )
    assert not email_reader.is_session_expired_error(RuntimeError("network timeout"))
