"""The CLI, driven through Typer's runner with no network involved."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from boatswain.cli import app
from tests.conftest import api_payload

runner = CliRunner()


def fixture_file(tmp_path, payloads):
    path = tmp_path / "items.json"
    path.write_text(json.dumps(payloads), encoding="utf-8")
    return path


def test_report_runs_from_a_fixture(tmp_path):
    path = fixture_file(tmp_path, [api_payload(1), api_payload(2)])

    result = runner.invoke(app, ["report", "--repo", "ab00bae/demo",
                                 "--fixture", str(path)])

    assert result.exit_code == 0
    assert "ab00bae/demo" in result.stdout


def test_a_missing_fixture_exits_with_code_two(tmp_path):
    result = runner.invoke(app, ["report", "--repo", "ab00bae/demo",
                                 "--fixture", str(tmp_path / "nope.json")])

    assert result.exit_code == 2


def test_markdown_is_written_when_out_is_given(tmp_path):
    path = fixture_file(tmp_path, [api_payload(1)])
    out = tmp_path / "reports" / "sprint.md"

    result = runner.invoke(
        app,
        ["report", "--repo", "ab00bae/demo", "--fixture", str(path),
         "--out", str(out)],
    )

    assert result.exit_code == 0
    assert out.exists()
    assert "# Sprint report" in out.read_text(encoding="utf-8")


def test_the_output_directory_is_created(tmp_path):
    path = fixture_file(tmp_path, [api_payload(1)])
    out = tmp_path / "deeply" / "nested" / "sprint.md"

    runner.invoke(
        app,
        ["report", "--repo", "ab00bae/demo", "--fixture", str(path),
         "--out", str(out)],
    )

    assert out.exists()


def test_repo_is_required():
    result = runner.invoke(app, ["report"])

    assert result.exit_code != 0


def test_version_flag():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "boatswain" in result.stdout


def test_sprint_days_must_be_positive(tmp_path):
    path = fixture_file(tmp_path, [api_payload(1)])

    result = runner.invoke(
        app,
        ["report", "--repo", "ab00bae/demo", "--fixture", str(path),
         "--sprint-days", "0"],
    )

    assert result.exit_code != 0
