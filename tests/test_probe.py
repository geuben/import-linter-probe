from __future__ import annotations

from pathlib import Path

import pytest

from import_linter_probe import ContractSpec, ProbeError, load_config, run_probe, stub_source
from import_linter_probe.probe import module_path, report, resolve_lint_command

# A command that produces no output, so the probe machinery can be exercised
# without depending on import-linter being installed.
SILENT = ["python3", "-c", "pass"]


@pytest.fixture(params=["ini_project", "toml_project"])
def project(request: pytest.FixtureRequest) -> Path:
    return request.getfixturevalue(request.param)


def test_stub_imports_exactly_what_it_is_told(ini_project: Path) -> None:
    source = stub_source("app.usecases.checkout", ["app.domain.orders"])
    assert "import app.domain.orders" in source


def test_module_path_honours_layout(ini_project: Path, toml_project: Path) -> None:
    flat = load_config(start=ini_project)
    assert module_path(flat, "app.usecases.checkout") == ini_project / "app/usecases/checkout.py"
    src = load_config(start=toml_project)
    expected = toml_project / "src/app/usecases/checkout.py"
    assert module_path(src, "app.usecases.checkout") == expected


def test_a_module_outside_the_root_packages_is_rejected(ini_project: Path) -> None:
    with pytest.raises(ProbeError, match="root package"):
        module_path(load_config(start=ini_project), "other.thing")


def test_refuses_to_overwrite_existing_code(project: Path) -> None:
    config = load_config(start=project)
    with pytest.raises(ProbeError, match="already exists"):
        run_probe(config, "app.util", [], "domain-isolation", None, SILENT)


def test_an_unknown_contract_without_a_spec_is_rejected(project: Path) -> None:
    config = load_config(start=project)
    with pytest.raises(ProbeError, match="does not exist"):
        run_probe(config, "app.usecases.checkout", [], "invented", None, SILENT)


def _probe_leaves_no_trace(project: Path, **kwargs: object) -> None:
    config = load_config(start=project)
    before = {p: p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}
    run_probe(
        config,
        module="app.usecases.checkout",
        imports=["app.domain.billing"],
        contract="domain-isolation",
        spec=None,
        lint_command=SILENT,
        **kwargs,  # type: ignore[arg-type]
    )
    after = {p: p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}
    assert after == before
    assert not (project / "app" / "usecases").exists()
    assert not (project / "src" / "app" / "usecases").exists()


def test_restores_the_project_byte_identically(project: Path) -> None:
    _probe_leaves_no_trace(project)


def test_restores_even_when_lint_imports_cannot_be_run(project: Path) -> None:
    config = load_config(start=project)
    before = (config.path).read_bytes()
    with pytest.raises(ProbeError, match="could not run"):
        run_probe(
            config,
            "app.usecases.checkout",
            [],
            "domain-isolation",
            None,
            ["definitely-not-a-real-binary-9f3c"],
        )
    assert config.path.read_bytes() == before
    assert not (config.project_root / "app" / "usecases").exists()


def test_restores_after_a_synthesised_contract(project: Path) -> None:
    config = load_config(start=project)
    before = config.path.read_bytes()
    run_probe(
        config,
        "app.usecases.checkout",
        [],
        "checkout-isolation",
        ContractSpec("forbidden", ["app.domain.billing"]),
        SILENT,
    )
    assert config.path.read_bytes() == before


def test_report_reads_a_clean_run_as_a_viable_home(capsys: pytest.CaptureFixture[str]) -> None:
    assert report("Contracts: 3 kept, 0 broken.\n", "app.x", "c") == 0
    assert "viable home" in capsys.readouterr().out


def test_report_reads_a_broken_run_as_a_rejection(capsys: pytest.CaptureFixture[str]) -> None:
    output = "Contracts: 2 kept, 1 broken.\n\nBroken contracts\n----------------\napp.x -> app.y\n"
    assert report(output, "app.x", "c") == 1
    out = capsys.readouterr().out
    assert "NOT accepted" in out
    assert "app.x -> app.y" in out


def test_report_survives_lint_imports_producing_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert report("", "app.x", "c") == 0
    assert "failed to run" in capsys.readouterr().out


def test_default_lint_command_asks_for_no_cache() -> None:
    assert "--no-cache" in resolve_lint_command(None)


def test_an_explicit_lint_command_is_used_verbatim() -> None:
    assert resolve_lint_command("poetry run lint-imports") == ["poetry", "run", "lint-imports"]
