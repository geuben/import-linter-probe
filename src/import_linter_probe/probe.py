"""`probe` — if I add module X, which contract can host it?

Writes a throwaway stub for a module that does not exist yet, containing
exactly the imports you say it will have, adds it to a contract, runs
lint-imports, and restores everything byte-identically.

A module's contract home is a property of its import graph, so it cannot be
looked up — only measured. This measures it in one command instead of six, and
guarantees the restore.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

from .config import Config, ConfigError, ContractSpec
from .modules import package_dir


class ProbeError(Exception):
    """The probe could not be set up. Nothing was written."""


def default_lint_command() -> list[str]:
    """The most likely way to reach lint-imports from here.

    A project's import-linter usually lives in the project's own environment,
    not next to this tool, so a bare `lint-imports` is only right when the tool
    is installed alongside it.
    """
    if shutil.which("lint-imports"):
        return ["lint-imports", "--no-cache"]
    if shutil.which("uv"):
        return ["uv", "run", "lint-imports", "--no-cache"]
    return ["lint-imports", "--no-cache"]


def resolve_lint_command(raw: str | None) -> list[str]:
    return shlex.split(raw) if raw else default_lint_command()


def module_path(config: Config, module: str, package_root: Path | None = None) -> Path:
    """Where a module of this dotted name would live on disk."""
    root = next(
        (r for r in config.root_packages if module == r or module.startswith(f"{r}.")),
        None,
    )
    if root is None:
        raise ProbeError(
            f"--module must be inside a root package"
            f" ({', '.join(config.root_packages)}), got {module!r}"
        )
    directory = package_dir(config, root, package_root)
    remainder = module[len(root) + 1 :].split(".") if module != root else []
    return directory.joinpath(*remainder).with_suffix(".py")


def stub_source(module: str, imports: list[str]) -> str:
    """A stub whose import graph matches what the real module will have.

    The imports are the entire point: an empty placeholder passes every
    contract and proves nothing.
    """
    lines = [f'"""Throwaway probe stub for {module}. Delete me."""', ""]
    lines += [f"import {name}" for name in imports]
    lines += ["", "__all__: list[str] = []", ""]
    return "\n".join(lines)


def _run(command: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    except OSError as error:
        raise ProbeError(
            f"could not run {' '.join(command)}: {error}"
            "\n       Pass --lint-cmd to say how to reach lint-imports."
        ) from error
    return result.stdout + result.stderr


def report(output: str, module: str, contract: str) -> int:
    summary = next(
        (line for line in output.splitlines() if line.startswith("Contracts:")),
        "Contracts: (no summary line — lint-imports failed to run)",
    )
    broken = output.split("Broken contracts")[1] if "Broken contracts" in output else ""

    print(f"\n{summary}")

    if not broken.strip():
        print(f"\nVERDICT: {contract} accepts {module}.")
        print("No contract broke. This is a viable home.")
        return 0

    print(f"\nVERDICT: {module} is NOT accepted as written.\n")
    print("Broken contracts" + broken.rstrip())
    print(
        "\nEach chain above is a real cross-context dependency. Prefer a different"
        "\nhost contract, or a narrower module. Reach for ignore_imports only when"
        "\nthe dependency is genuinely deliberate — and say why in a comment."
    )
    return 1


def run_probe(
    config: Config,
    module: str,
    imports: list[str],
    contract: str,
    spec: ContractSpec | None,
    lint_command: list[str],
    package_root: Path | None = None,
) -> int:
    path = module_path(config, module, package_root)
    if path.exists():
        raise ProbeError(
            f"{path} already exists. This probe is for modules that do not exist"
            " yet; it will not overwrite code."
        )
    if contract not in config.contracts and spec is None:
        known = ", ".join(sorted(config.contracts)) or "(none)"
        raise ProbeError(
            f"contract {contract!r} does not exist. Pass --forbidden/--independence/--layers"
            f" to synthesise it for the probe.\n       existing contracts: {known}"
        )

    original = config.path.read_bytes()
    created_dirs: list[Path] = []
    created_inits: list[Path] = []

    try:
        # Innermost package last, so cleanup reverses cleanly.
        missing: list[Path] = []
        parent = path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            directory.mkdir()
            created_dirs.append(directory)
            init = directory / "__init__.py"
            init.write_text("")
            created_inits.append(init)

        path.write_text(stub_source(module, imports))

        if contract in config.contracts:
            text = config.with_module_added(contract, module)
            print(f"Probing: {module} added to existing contract {contract!r}")
        else:
            assert spec is not None
            text = config.with_contract_added(contract, module, spec)
            print(f"Probing: {module} in a synthesised {spec.type} contract {contract!r}")
        print(f"Stub imports: {', '.join(imports) or '(none — this will prove nothing)'}")
        config.path.write_text(text)

        return report(_run(lint_command, config.project_root), module, contract)

    except ConfigError as error:
        raise ProbeError(str(error)) from error

    finally:
        config.path.write_bytes(original)
        path.unlink(missing_ok=True)
        for init in created_inits:
            init.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            directory.rmdir()
        assert config.path.read_bytes() == original, (
            f"FAILED TO RESTORE {config.path} — check `git diff` before doing anything else"
        )
