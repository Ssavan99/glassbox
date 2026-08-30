import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_index import _atomic_write_bytes, _atomic_write_text


def test_atomic_write_text_produces_correct_content_and_no_leftover_tmp(tmp_path):
    target = tmp_path / "out.json"
    _atomic_write_text(target, '{"a": 1}')
    assert target.read_text() == '{"a": 1}'
    assert not (tmp_path / "out.json.tmp").exists()


def test_atomic_write_bytes_produces_correct_content_and_no_leftover_tmp(tmp_path):
    target = tmp_path / "out.f32"
    _atomic_write_bytes(target, b"\x00\x01\x02\x03")
    assert target.read_bytes() == b"\x00\x01\x02\x03"
    assert not (tmp_path / "out.f32.tmp").exists()


def test_atomic_write_text_leaves_prior_content_intact_if_write_fails(tmp_path, monkeypatch):
    target = tmp_path / "out.json"
    target.write_text("original content")

    def _boom(*args, **kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr(Path, "write_text", _boom)
    import contextlib

    with contextlib.suppress(OSError):
        _atomic_write_text(target, "new content")

    # The failure happened writing the .tmp file, before os.replace() ever
    # ran, so the real target path must still hold its original content --
    # never a truncated or partial write.
    monkeypatch.undo()
    assert target.read_text() == "original content"
