from __future__ import annotations

from pathlib import Path

import pytest

from import_linter_probe import audit, declaration_problems, load_config, run_audit


@pytest.fixture(params=["ini_project", "toml_project"])
def project(request: pytest.FixtureRequest) -> Path:
    return request.getfixturevalue(request.param)


def test_classifies_every_module(project: Path) -> None:
    result = audit(load_config(start=project))
    assert result.excused == ["app.config"]
    # Being named in `forbidden_modules` is not being examined: only a
    # contract's source_modules puts a module under inspection.
    assert result.unexamined == ["app.domain.billing", "app.util"]
    assert result.problems == []
    assert not result.ok


def test_a_module_in_a_contract_is_neither_excused_nor_unexamined(project: Path) -> None:
    result = audit(load_config(start=project))
    assert "app.domain.orders" not in result.unexamined
    assert "app.domain.orders" not in result.excused


def test_a_fully_accounted_for_project_is_ok(ini_project: Path) -> None:
    path = ini_project / ".importlinter"
    path.write_text(
        path.read_text().replace(
            "[unconstrained]\n",
            "[unconstrained]\napp.util = shared helper\napp.domain.billing = leaf\n",
        )
    )
    result = audit(load_config(start=ini_project))
    assert result.unexamined == []
    assert result.ok


def test_run_audit_exit_codes(ini_project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_audit(load_config(start=ini_project)) == 1
    assert "unexamined" in capsys.readouterr().out


MODULES = ["app.config", "app.domain.orders", "app.util"]
COVERED = {"app.domain.orders"}


@pytest.mark.parametrize(
    ("declared", "fragment"),
    [
        ({"app.gone": "why"}, "no such module exists"),
        ({"app.domain.orders": "why"}, "a contract covers it"),
        ({"app.util": ""}, "no reason given"),
    ],
)
def test_declaration_problems(declared: dict[str, str], fragment: str) -> None:
    (problem,) = declaration_problems(declared, MODULES, COVERED)
    assert fragment in problem


def test_a_sound_declaration_has_no_problems() -> None:
    assert declaration_problems({"app.config": "infrastructure"}, MODULES, COVERED) == []
