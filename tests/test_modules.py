from __future__ import annotations

from pathlib import Path

import pytest

from import_linter_probe import ConfigError, is_covered, load_config, matches_any, project_modules
from import_linter_probe.modules import has_code, package_dir

# `app/__init__.py` is empty, so the package itself is not a module worth auditing.
EXPECTED = ["app.config", "app.domain.billing", "app.domain.orders", "app.util"]


def test_flat_layout_modules(ini_project: Path) -> None:
    assert project_modules(load_config(start=ini_project)) == EXPECTED


def test_src_layout_does_not_leak_src_into_module_names(toml_project: Path) -> None:
    # The whole point: `src/app/util.py` is `app.util`, never `src.app.util`.
    assert project_modules(load_config(start=toml_project)) == EXPECTED


def test_docstring_only_modules_are_not_listed(ini_project: Path) -> None:
    assert "app.empty" not in project_modules(load_config(start=ini_project))


def test_unparseable_modules_are_surfaced_rather_than_hidden(tmp_path: Path) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("def (\n")
    assert has_code(broken)


def test_package_root_override(ini_project: Path, tmp_path: Path) -> None:
    config = load_config(start=ini_project)
    assert package_dir(config, "app", package_root=ini_project) == ini_project / "app"


def test_a_missing_package_says_where_it_looked(tmp_path: Path) -> None:
    (tmp_path / ".importlinter").write_text("[importlinter]\nroot_package = ghost\n")
    config = load_config(tmp_path / ".importlinter")
    with pytest.raises(ConfigError, match="could not find the source"):
        project_modules(config)


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("app.domain.orders", True),
        ("app.domain.orders.helpers", True),  # a source_module covers its subtree
        ("app.domain.billing", False),
        ("app.domain", False),  # covering a child does not cover the parent
    ],
)
def test_is_covered(module: str, expected: bool) -> None:
    assert is_covered(module, {"app.domain.orders"}) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [("app.util", True), ("app.domain", True), ("app.missing", False)],
)
def test_matches_any(name: str, expected: bool) -> None:
    assert matches_any(name, EXPECTED) is expected
