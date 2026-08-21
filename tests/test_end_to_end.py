"""The one test that runs real import-linter against a real project.

Everything else stubs the lint command, which proves the plumbing but not the
verdict. This proves the verdict — and that the config it wrote was one
import-linter could actually read.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from import_linter_probe import ContractSpec, load_config, run_probe
from import_linter_probe.cli import main

pytestmark = pytest.mark.skipif(
    shutil.which("lint-imports") is None, reason="import-linter is not installed"
)


@pytest.fixture(params=["ini_project", "toml_project"])
def project(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Path:
    path: Path = request.getfixturevalue(request.param)
    # import-linter imports the root package, so it has to be on the path of
    # the subprocess the probe spawns.
    import_root = path / "src" if (path / "src").is_dir() else path
    monkeypatch.setenv("PYTHONPATH", str(import_root))
    return path


LINT = ["lint-imports", "--no-cache"]


def test_a_module_that_breaks_the_contract_is_rejected(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = load_config(start=project)
    # domain-isolation forbids app.domain.orders from importing app.domain.billing,
    # and the probed module joins that contract's source_modules.
    exit_code = run_probe(
        config,
        module="app.domain.checkout",
        imports=["app.domain.billing"],
        contract="domain-isolation",
        spec=None,
        lint_command=LINT,
    )
    assert exit_code == 1
    assert "NOT accepted" in capsys.readouterr().out


def test_a_module_that_respects_the_contract_is_accepted(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = load_config(start=project)
    exit_code = run_probe(
        config,
        module="app.domain.checkout",
        imports=["app.config"],
        contract="domain-isolation",
        spec=None,
        lint_command=LINT,
    )
    assert exit_code == 0
    assert "viable home" in capsys.readouterr().out


def test_a_synthesised_contract_is_readable_by_import_linter(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = load_config(start=project)
    exit_code = run_probe(
        config,
        module="app.domain.checkout",
        imports=["app.domain.billing"],
        contract="checkout-isolation",
        spec=ContractSpec("forbidden", ["app.domain.billing"]),
        lint_command=LINT,
    )
    out = capsys.readouterr().out
    assert "no summary line" not in out  # the config parsed; lint-imports ran
    assert exit_code == 1


def test_cli_probe_end_to_end(
    project: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(project)
    exit_code = main(
        [
            "probe",
            "--module",
            "app.domain.checkout",
            "--imports",
            "app.config",
            "--contract",
            "domain-isolation",
            "--lint-cmd",
            "lint-imports --no-cache",
        ]
    )
    assert exit_code == 0
    assert "viable home" in capsys.readouterr().out


def test_cli_audit_end_to_end(
    project: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(project)
    assert main(["audit"]) == 1
    assert "app.util" in capsys.readouterr().out


def test_cli_reports_a_missing_config_as_bad_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["audit"]) == 2
    assert "no import-linter configuration" in capsys.readouterr().err
