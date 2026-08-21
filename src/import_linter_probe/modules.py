"""Enumerate a project's real modules and decide which contracts reach them.

The subtlety this module exists to handle is that a file path is not a module
name. `src/app/foo.py` is `app.foo`, not `src.app.foo`, and getting that wrong
makes every coverage answer silently false for src-layout projects.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .config import Config, ConfigError

#: Where a root package is looked for, relative to the config file's directory.
PACKAGE_PARENTS = (".", "src")


def package_dir(config: Config, root_package: str, package_root: Path | None = None) -> Path:
    """The directory holding `root_package`, honouring src-layout.

    import-linter finds the package by importing it, which needs the project's
    own environment. This tool is meant to run as a standalone command, so it
    looks on disk instead.
    """
    top = root_package.split(".")[0]
    parents = [package_root] if package_root else [config.project_root / p for p in PACKAGE_PARENTS]
    candidates = [parent / Path(*root_package.split(".")) for parent in parents]
    existing = [c for c in candidates if c.is_dir()]
    # A directory with an `__init__.py` at the top level is the real package;
    # a bare directory of the same name higher up is a coincidence.
    packages = [
        candidate
        for candidate, parent in zip(candidates, parents, strict=True)
        if candidate.is_dir() and (parent / top / "__init__.py").is_file()
    ]
    if packages:
        return packages[0]
    if existing:
        return existing[0]
    searched = ", ".join(str(p) for p in parents)
    raise ConfigError(
        f"could not find the source of root package {root_package!r}."
        f"\n       Looked under: {searched}."
        "\n       Pass --package-root if it lives somewhere else."
    )


def has_code(path: Path) -> bool:
    """True if the file holds anything but comments, blanks and a docstring.

    An empty `__init__.py` cannot import anything, so it cannot break a
    contract. Listing them all would bury the real findings.
    """
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return True  # can't tell — surface it rather than hide it
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return bool(body)


def project_modules(config: Config, package_root: Path | None = None) -> list[str]:
    """Every importable module in the root packages that contains code."""
    modules: list[str] = []
    for root_package in config.root_packages:
        directory = package_dir(config, root_package, package_root)
        # Dotted names are relative to the directory *containing* the top-level
        # package, which is the import root — not to the project root.
        import_root = directory.parents[len(root_package.split(".")) - 1]
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts or not has_code(path):
                continue
            parts = list(path.relative_to(import_root).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            if parts:
                modules.append(".".join(parts))
    return sorted(dict.fromkeys(modules))


def is_covered(module: str, covered: set[str]) -> bool:
    """True if the module, or any package above it, is named by a contract.

    import-linter treats a source_module as the root of a subtree, so naming
    `app.domain.evidence` also covers `app.domain.evidence.helpers`.
    """
    parts = module.split(".")
    return any(".".join(parts[: i + 1]) in covered for i in range(len(parts)))


def matches_any(name: str, modules: list[str]) -> bool:
    """True if `name` is a real module, or a package containing one."""
    return any(module == name or module.startswith(f"{name}.") for module in modules)
