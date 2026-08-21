from __future__ import annotations

from pathlib import Path

import pytest

from import_linter_probe import Config, ConfigError, ContractSpec, find_config, load_config


@pytest.fixture(params=["ini_project", "toml_project"])
def project(request: pytest.FixtureRequest) -> Path:
    """Both config shapes, so every shared assertion is made about both."""
    return request.getfixturevalue(request.param)


@pytest.fixture
def config(project: Path) -> Config:
    return load_config(start=project)


def test_reads_root_packages_from_either_spelling(config: Config) -> None:
    assert config.root_packages == ["app"]


def test_reads_contracts(config: Config) -> None:
    contract = config.contracts["domain-isolation"]
    assert contract.type == "forbidden"
    assert contract.source_modules == ["app.domain.orders"]


def test_reads_unconstrained_declarations(config: Config) -> None:
    assert config.unconstrained == {"app.config": "infrastructure; settings only"}


def test_covered_modules_unions_every_contract(config: Config) -> None:
    assert config.covered_modules == {"app.domain.orders"}


def test_finds_the_config_from_a_subdirectory(project: Path) -> None:
    nested = project / "app" / "domain"
    assert find_config(nested).parent == project


def test_ignores_a_pyproject_that_does_not_configure_import_linter(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    with pytest.raises(ConfigError, match="no import-linter configuration"):
        find_config(tmp_path)


def test_adding_a_source_module_is_a_pure_insertion(config: Config) -> None:
    """Comments, key order and formatting have to survive — the file is checked in."""
    edited = config.with_module_added("domain-isolation", "app.usecases.checkout")
    assert "app.usecases.checkout" in edited
    inserted = ["    app.usecases.checkout\n", '"app.usecases.checkout", ']
    assert any(edited.replace(token, "", 1) == config.text for token in inserted)


def test_adding_a_source_module_to_an_unknown_contract_is_an_error(config: Config) -> None:
    with pytest.raises(ConfigError):
        config.with_module_added("no-such-contract", "app.util")


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (ContractSpec("forbidden", ["app.domain.billing"]), "app.domain.billing"),
        (ContractSpec("independence", ["app.domain.orders"]), "app.domain.orders"),
        (ContractSpec("layers", ["app.domain.orders"]), "app.domain.orders"),
    ],
)
def test_synthesised_contracts_name_their_modules(
    config: Config, spec: ContractSpec, expected: str
) -> None:
    edited = config.with_contract_added("probe-contract", "app.usecases.checkout", spec)
    assert edited.startswith(config.text)
    assert expected in edited
    assert "app.usecases.checkout" in edited


def test_synthesising_an_unsupported_contract_type_is_an_error(config: Config) -> None:
    with pytest.raises(ConfigError, match="known types"):
        config.with_contract_added("x", "app.util", ContractSpec("magic", ["app.domain.orders"]))


def test_a_config_without_root_packages_is_rejected(tmp_path: Path) -> None:
    (tmp_path / ".importlinter").write_text("[importlinter]\n")
    with pytest.raises(ConfigError, match="no root_package"):
        load_config(tmp_path / ".importlinter")
