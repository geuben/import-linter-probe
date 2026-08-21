"""Probe and audit an import-linter configuration.

The command line is `import-linter-probe`; everything it uses is public, so a
project can also assert on its own coverage from a test:

    from import_linter_probe import audit, load_config

    result = audit(load_config())
    assert not result.problems
    assert len(result.unexamined) <= MAX_UNEXAMINED
"""

from .audit import Audit, audit, declaration_problems, run_audit
from .config import (
    Config,
    ConfigError,
    Contract,
    ContractSpec,
    find_config,
    load_config,
)
from .modules import has_code, is_covered, matches_any, package_dir, project_modules
from .probe import ProbeError, module_path, run_probe, stub_source

__all__ = [
    "Audit",
    "Config",
    "ConfigError",
    "Contract",
    "ContractSpec",
    "ProbeError",
    "audit",
    "declaration_problems",
    "find_config",
    "has_code",
    "is_covered",
    "load_config",
    "matches_any",
    "module_path",
    "package_dir",
    "project_modules",
    "run_audit",
    "run_probe",
    "stub_source",
]

__version__ = "0.1.0"
