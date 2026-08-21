"""`audit` — which modules is no contract looking at?

import-linter only reports on modules named in a source_modules list. Code that
lives outside every list is not "passing" — it is unexamined, and lint-imports
stays green while it drifts. This finds that blind spot.

Some modules are deliberately cross-context and no contract can honestly
describe them. Those are declared with a reason (see `config`), and reported
separately rather than as a blind spot. The reason is required: a bare list is
a mute button, a reason is a record of a decision. The audit also fails on
entries that have gone stale (the module is gone) or contradict themselves (a
contract covers it after all), so the list cannot rot quietly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .modules import is_covered, matches_any, project_modules


@dataclass(frozen=True)
class Audit:
    """A snapshot of what each module's contract situation is."""

    modules: list[str]
    covered: set[str]
    declared: dict[str, str]
    problems: list[str]
    excused: list[str]
    unexamined: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems and not self.unexamined


def declaration_problems(
    declared: dict[str, str], modules: list[str], covered: set[str]
) -> list[str]:
    """The ways a declared-unconstrained entry can be wrong."""
    problems = []
    for module, reason in sorted(declared.items()):
        if not matches_any(module, modules):
            problems.append(f"{module} — declared unconstrained, but no such module exists")
        elif is_covered(module, covered):
            problems.append(f"{module} — declared unconstrained, but a contract covers it")
        elif not reason:
            problems.append(f"{module} — declared unconstrained with no reason given")
    return problems


def audit(config: Config, package_root: Path | None = None) -> Audit:
    """Classify every module as contracted, excused, or unexamined."""
    modules = project_modules(config, package_root)
    covered = config.covered_modules
    declared = config.unconstrained

    uncovered = [m for m in modules if not is_covered(m, covered)]
    excused = [m for m in uncovered if is_covered(m, set(declared))]
    excused_set = set(excused)
    return Audit(
        modules=modules,
        covered=covered,
        declared=declared,
        problems=declaration_problems(declared, modules, covered),
        excused=excused,
        unexamined=[m for m in uncovered if m not in excused_set],
    )


def _by_package(unexamined: list[str], root_packages: list[str]) -> dict[str, int]:
    """Tally one level below each root package, to show where the gaps cluster."""
    depths = {root: len(root.split(".")) for root in root_packages}
    tally: dict[str, int] = {}
    for module in unexamined:
        parts = module.split(".")
        root = next((r for r in root_packages if module == r or module.startswith(f"{r}.")), None)
        depth = depths.get(root, 1) + 1 if root else 2
        package = ".".join(parts[:depth])
        tally[package] = tally.get(package, 0) + 1
    return tally


def run_audit(config: Config, package_root: Path | None = None) -> int:
    result = audit(config, package_root)
    scope = ", ".join(config.root_packages)

    print(
        f"{len(result.modules)} code modules under {scope}: "
        f"{len(result.modules) - len(result.excused) - len(result.unexamined)} in a contract, "
        f"{len(result.excused)} declared unconstrained, {len(result.unexamined)} unexamined."
    )

    if result.problems:
        print(f"\n{len(result.problems)} stale or contradictory unconstrained entries:\n")
        for problem in result.problems:
            print(f"    {problem}")

    if result.unexamined:
        print("\nlint-imports is green on these by omission, not by inspection:\n")
        for module in result.unexamined:
            print(f"    {module}")

        print("\nBy package:")
        tally = _by_package(result.unexamined, config.root_packages)
        for package, count in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"    {count:>3}  {package}")

        print(
            "\nA blind spot, not necessarily a bug — some of these are deliberately"
            "\ncross-context. Decide each one; do not bulk-add. Give a module a"
            "\ncontract, or an unconstrained entry saying why it has none."
        )

    if result.ok:
        print("\nEvery module is either in a contract or declared unconstrained with a reason.")
        return 0
    return 1
