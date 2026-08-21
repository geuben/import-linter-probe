"""Fixture projects, built on disk because that is what the tool reads."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

INI_CONFIG = """\
[importlinter]
root_packages =
    app

[importlinter:contract:domain-isolation]
name = Domain isolation
type = forbidden
source_modules =
    app.domain.orders
forbidden_modules =
    app.domain.billing

[unconstrained]
app.config = infrastructure; settings only
"""

TOML_CONFIG = """\
[project]
name = "demo"

[tool.importlinter]
root_package = "app"

[[tool.importlinter.contracts]]
name = "domain-isolation"
type = "forbidden"
source_modules = [
    "app.domain.orders",
]
forbidden_modules = ["app.domain.billing"]

[tool.importlinter_probe.unconstrained]
"app.config" = "infrastructure; settings only"
"""

#: package-relative path -> source. `app.util` is in no contract and has no
#: unconstrained entry, so it is the fixture's one unexamined module.
SOURCES = {
    "__init__.py": "",
    "config.py": "SETTING = 1\n",
    "util.py": "def helper() -> int:\n    return 1\n",
    "empty.py": '"""Docstring only — no code, so not a module worth auditing."""\n',
    "domain/__init__.py": "",
    "domain/orders.py": "ORDERS = []\n",
    "domain/billing.py": "BILLING = []\n",
}


def _write_package(package_dir: Path) -> None:
    for relative, source in SOURCES.items():
        path = package_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source))


@pytest.fixture
def ini_project(tmp_path: Path) -> Path:
    """A flat-layout project configured by `.importlinter`."""
    root = tmp_path / "flat"
    root.mkdir()
    (root / ".importlinter").write_text(INI_CONFIG)
    _write_package(root / "app")
    return root


@pytest.fixture
def toml_project(tmp_path: Path) -> Path:
    """A src-layout project configured by `pyproject.toml`."""
    root = tmp_path / "src-layout"
    root.mkdir()
    (root / "pyproject.toml").write_text(TOML_CONFIG)
    _write_package(root / "src" / "app")
    return root
