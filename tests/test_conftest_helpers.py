"""Tests for tests/conftest.py's own live-backend-detection helper -- this
gates whether test_corrective.py's real_end_to_end tests and
test_build_graph.py's build_stats fixture run or skip, so it's worth
covering directly rather than only trusting it by inspection."""

from __future__ import annotations

import socket

import tests.conftest as conftest_mod


def test_live_backend_available_true_when_groq_key_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake_for_this_test_only")
    monkeypatch.setattr(conftest_mod, "_ollama_reachable", lambda: False)
    assert conftest_mod.live_backend_available() is True


def test_live_backend_available_true_when_ollama_reachable_even_without_groq_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(conftest_mod, "_ollama_reachable", lambda: True)
    assert conftest_mod.live_backend_available() is True


def test_live_backend_available_false_when_neither_is_available(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(conftest_mod, "_ollama_reachable", lambda: False)
    assert conftest_mod.live_backend_available() is False


def test_ollama_reachable_false_on_connection_refused(monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(socket, "create_connection", _boom)
    assert conftest_mod._ollama_reachable() is False
