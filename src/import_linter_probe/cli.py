"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audit import run_audit
from .config import ConfigError, ContractSpec, load_config
from .probe import ProbeError, resolve_lint_command, run_probe

DESCRIPTION = """
Answer two import-linter questions that otherwise cost an afternoon of
hand-rolled stubbing.

  probe   if I add module X, which contract can host it?
  audit   which modules are checked by no contract at all?

Examples:

  # An existing contract as the candidate host:
  import-linter-probe probe --module app.usecases.signing_keys \\
      --imports app.services.signing_key_deps app.services.auth_service \\
      --contract key-exchange-isolation

  # A contract that does not exist yet — synthesised, then removed:
  import-linter-probe probe --module app.usecases.signing_keys \\
      --imports app.services.signing_key_deps \\
      --contract signing-keys-isolation \\
      --forbidden app.persistence.family app.persistence.evidence

  import-linter-probe audit

Exit codes: 0 = the host contract holds (or the audit found no blind spot);
1 = a contract broke (or unchecked modules exist); 2 = bad usage.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import-linter-probe",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="import-linter config file; default is the nearest one at or above the cwd",
    )
    parser.add_argument(
        "--package-root",
        type=Path,
        help="directory containing the root packages, if it is neither . nor src/",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser(
        "probe",
        help="find a contract home for a module you have not written",
        description="Find a contract home for a module you have not written.",
    )
    probe.add_argument("--module", required=True, help="dotted name, e.g. app.usecases.evidence")
    probe.add_argument(
        "--imports",
        nargs="*",
        default=[],
        help="what the real module will import — the probe is only as honest as this list",
    )
    probe.add_argument("--contract", required=True, help="candidate host contract id")
    probe.add_argument(
        "--lint-cmd",
        help="how to run lint-imports (default: lint-imports, or uv run lint-imports)",
    )
    synth = probe.add_mutually_exclusive_group()
    synth.add_argument(
        "--forbidden",
        nargs="+",
        metavar="MODULE",
        help="forbidden_modules, when --contract names a contract that does not exist yet",
    )
    synth.add_argument(
        "--independence",
        nargs="+",
        metavar="MODULE",
        help="the other modules of a synthesised independence contract",
    )
    synth.add_argument(
        "--layers",
        nargs="+",
        metavar="MODULE",
        help="the ordered layers of a synthesised layers contract, highest first;"
        " include --module in the position you are proposing for it",
    )

    sub.add_parser(
        "audit",
        help="list modules that no contract names",
        description="List modules that no contract names.",
    )
    return parser


def _spec(args: argparse.Namespace) -> ContractSpec | None:
    for kind in ("forbidden", "independence", "layers"):
        modules = getattr(args, kind)
        if modules:
            return ContractSpec(type=kind, modules=list(modules))
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "audit":
            return run_audit(config, args.package_root)
        return run_probe(
            config,
            module=args.module,
            imports=list(args.imports),
            contract=args.contract,
            spec=_spec(args),
            lint_command=resolve_lint_command(args.lint_cmd),
            package_root=args.package_root,
        )
    except (ConfigError, ProbeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
