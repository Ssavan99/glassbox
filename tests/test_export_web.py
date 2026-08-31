import json

import pytest

import scripts.export_web as export_web_mod


def _make_artifacts(tmp_path, *, with_traces=True, extra_files=()):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    for name in ["chunks.json", "eval.json", "graph.json", "bm25.json"]:
        (artifacts / name).write_text(json.dumps({"stub": name}))
    (artifacts / "vectors.f32").write_bytes(b"\x00\x01\x02\x03")
    if with_traces:
        traces = artifacts / "traces"
        traces.mkdir()
        (traces / "naive__q01.json").write_text("{}")
        (traces / "hybrid__q01.json").write_text("{}")
    for name in extra_files:
        (artifacts / name).write_text("{}")
    return artifacts


def test_copies_all_artifact_files_and_traces(tmp_path, monkeypatch):
    artifacts = _make_artifacts(tmp_path)
    web_data = tmp_path / "web" / "public" / "data"
    monkeypatch.setattr(export_web_mod, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(export_web_mod, "WEB_DATA_DIR", web_data)

    export_web_mod.main()

    for name in ["chunks.json", "eval.json", "graph.json", "bm25.json", "vectors.f32"]:
        assert (web_data / name).exists()
    assert (web_data / "traces" / "naive__q01.json").exists()
    assert (web_data / "traces" / "hybrid__q01.json").exists()
    assert (web_data / "vectors.f32").read_bytes() == b"\x00\x01\x02\x03"


def test_skips_a_missing_optional_file_without_crashing(tmp_path, monkeypatch, capsys):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "chunks.json").write_text("{}")
    # eval.json, graph.json, bm25.json, vectors.f32 deliberately not built yet
    web_data = tmp_path / "web" / "public" / "data"
    monkeypatch.setattr(export_web_mod, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(export_web_mod, "WEB_DATA_DIR", web_data)

    export_web_mod.main()

    assert (web_data / "chunks.json").exists()
    assert not (web_data / "eval.json").exists()
    assert "skipping eval.json" in capsys.readouterr().out


def test_rerun_clears_stale_files_from_a_prior_export(tmp_path, monkeypatch):
    artifacts = _make_artifacts(tmp_path)
    web_data = tmp_path / "web" / "public" / "data"
    monkeypatch.setattr(export_web_mod, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(export_web_mod, "WEB_DATA_DIR", web_data)

    export_web_mod.main()
    # Simulate a trace that existed in a previous export but was since
    # removed from artifacts/ (e.g. a question deleted from questions.yaml).
    (web_data / "traces" / "stale__q99.json").write_text("{}")

    export_web_mod.main()

    assert not (web_data / "traces" / "stale__q99.json").exists()
    assert (web_data / "traces" / "naive__q01.json").exists()


def test_raises_if_artifacts_dir_is_missing_entirely(tmp_path, monkeypatch):
    monkeypatch.setattr(export_web_mod, "ARTIFACTS_DIR", tmp_path / "does-not-exist")
    monkeypatch.setattr(export_web_mod, "WEB_DATA_DIR", tmp_path / "web" / "public" / "data")

    with pytest.raises(SystemExit, match="does not exist"):
        export_web_mod.main()
