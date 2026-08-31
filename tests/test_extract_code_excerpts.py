import json

import pytest

import scripts.extract_code_excerpts as excerpts_mod
from scripts.extract_code_excerpts import ARCHITECTURE_FILES, extract_all, extract_region


def test_markers_still_exist_in_every_architecture_file():
    """This is the test that actually makes 'docs cannot drift from code'
    true: if a future edit to any architecture file moves, renames, or
    deletes its region markers, this fails loudly instead of the tutorial
    page silently shipping a stale or empty code excerpt."""
    for architecture, rel_path in ARCHITECTURE_FILES.items():
        path = excerpts_mod.ROOT / rel_path
        assert path.exists(), f"{architecture}: {path} does not exist"
        lines = path.read_text().splitlines()
        stripped = [line.strip() for line in lines]
        assert "# region: run" in stripped, f"{architecture}: missing '# region: run' marker"
        assert "# endregion" in stripped, f"{architecture}: missing '# endregion' marker"


def test_extraction_produces_a_nonempty_excerpt_for_all_seven_architectures():
    result = extract_all()
    assert set(result) == set(ARCHITECTURE_FILES)
    for architecture, entry in result.items():
        assert entry["code"], f"{architecture}: extracted code is empty"
        # Every one of these is a `def run(...)` method, per the marker
        # placement convention -- a real sanity check that this is genuine
        # source, not an accidental empty/truncated capture.
        assert "def run(" in entry["code"], f"{architecture}: excerpt doesn't contain 'def run('"
        assert entry["architecture"] == architecture
        assert entry["region"] == "run"
        assert entry["start_line"] < entry["end_line"]


def test_extraction_is_deterministic_on_rerun():
    first = extract_all()
    second = extract_all()
    assert first == second


def test_extracted_code_is_dedented_to_column_zero():
    result = extract_all()
    for architecture, entry in result.items():
        first_line = entry["code"].splitlines()[0]
        assert first_line == first_line.lstrip(), (
            f"{architecture}: excerpt's first line is still indented -- dedent didn't strip "
            "the class-method leading whitespace"
        )


def test_region_extraction_raises_a_clear_error_when_the_start_marker_is_missing(tmp_path):
    path = tmp_path / "no_start.py"
    path.write_text("def run():\n    pass\n# endregion\n")
    with pytest.raises(ValueError, match="no '# region: run' marker found"):
        extract_region(path, "run")


def test_region_extraction_raises_a_clear_error_when_the_end_marker_is_missing(tmp_path):
    path = tmp_path / "no_end.py"
    path.write_text("# region: run\ndef run():\n    pass\n")
    with pytest.raises(ValueError, match="no matching '# endregion'"):
        extract_region(path, "run")


def test_region_extraction_raises_a_clear_error_on_an_empty_region(tmp_path):
    path = tmp_path / "empty.py"
    path.write_text("# region: run\n# endregion\n")
    with pytest.raises(ValueError, match="is empty"):
        extract_region(path, "run")


def test_region_extraction_dedents_and_trims_blank_edges(tmp_path):
    path = tmp_path / "indented.py"
    path.write_text(
        "class X:\n"
        "    # region: run\n"
        "\n"
        "    def run(self):\n"
        "        return 1\n"
        "\n"
        "    # endregion\n"
    )
    code, start_line, end_line = extract_region(path, "run")
    assert code == "def run(self):\n    return 1"
    # start_line/end_line bound the *raw* slice between the markers
    # (1-indexed), before stripping the blank lines dedent normalizes away --
    # line 3 is the blank line right after "# region: run", line 6 is the
    # blank line right before "# endregion".
    assert start_line == 3
    assert end_line == 6


def test_main_writes_code_excerpts_json_to_web_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(excerpts_mod, "WEB_DATA_DIR", tmp_path / "web" / "public" / "data")

    excerpts_mod.main()

    out = tmp_path / "web" / "public" / "data" / "code_excerpts.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert set(data) == set(ARCHITECTURE_FILES)


def test_main_does_not_clear_pre_existing_files_in_web_data_dir(tmp_path, monkeypatch):
    """extract_code_excerpts.py must run *after* export_web.py without
    wiping what it just wrote -- export_web.py is the one that clears and
    recreates web/public/data/ on every run; this script only ever adds to
    it."""
    web_data = tmp_path / "web" / "public" / "data"
    web_data.mkdir(parents=True)
    (web_data / "eval.json").write_text('{"stub": true}')
    monkeypatch.setattr(excerpts_mod, "WEB_DATA_DIR", web_data)

    excerpts_mod.main()

    assert (web_data / "eval.json").exists()
    assert (web_data / "code_excerpts.json").exists()
