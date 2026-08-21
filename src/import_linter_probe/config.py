"""Locate and read an import-linter configuration, in either of its two shapes.

import-linter accepts its configuration as INI (`.importlinter`, `setup.cfg`,
`tox.ini`) or as TOML (`pyproject.toml`, under `[tool.importlinter]`). The two
are different enough that reading them needs two code paths and *editing* them
needs two more — but everything above this module works against one `Config`.

Editing is a first-class concern here: `probe` works by writing a modified
config, running lint-imports against it, and restoring the original bytes. The
edits are therefore textual rather than a parse-and-reserialise round trip: a
reserialised config would come back with comments stripped and keys reordered,
which is an unacceptable thing to do to a file that lives in version control
even when the restore is guaranteed.
"""

from __future__ import annotations

import configparser
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONTRACT_PREFIX = "importlinter:contract:"

#: Where import-linter itself looks, in the order it looks.
CONFIG_FILENAMES = ("setup.cfg", ".importlinter", "tox.ini", "pyproject.toml")

#: INI section holding module -> reason. `[unconstrained]` is the short form;
#: the namespaced form is for `setup.cfg`/`tox.ini`, which are shared files
#: where a bare top-level section name is a poor citizen.
INI_UNCONSTRAINED_SECTIONS = ("unconstrained", "importlinter-probe:unconstrained")

#: TOML table holding module -> reason. Deliberately *outside*
#: `[tool.importlinter]` so import-linter never sees a key it did not define.
TOML_UNCONSTRAINED_TABLE = ("tool", "importlinter_probe", "unconstrained")


class ConfigError(Exception):
    """The configuration could not be found, read, or edited as asked."""


@dataclass(frozen=True)
class Contract:
    """One contract, reduced to the parts a probe cares about."""

    id: str
    name: str
    type: str
    source_modules: list[str]


@dataclass(frozen=True)
class ContractSpec:
    """A contract to synthesise for the duration of a probe."""

    type: str
    #: `forbidden_modules` for a forbidden contract, `modules` for an
    #: independence contract, the ordered `layers` for a layers contract.
    modules: list[str]


@dataclass
class Config:
    """An import-linter configuration, parsed and re-editable."""

    path: Path
    project_root: Path
    kind: str  # "ini" | "toml"
    text: str
    root_packages: list[str]
    contracts: dict[str, Contract] = field(default_factory=dict)
    unconstrained: dict[str, str] = field(default_factory=dict)

    @property
    def covered_modules(self) -> set[str]:
        """Every module named in any contract's source_modules."""
        return {
            module for contract in self.contracts.values() for module in contract.source_modules
        }

    def with_module_added(self, contract_id: str, module: str) -> str:
        """This config's text, with `module` appended to a contract's sources."""
        if contract_id not in self.contracts:
            raise ConfigError(f"no contract with id {contract_id!r}")
        if self.kind == "ini":
            return _ini_add_source_module(self.text, contract_id, module)
        return _toml_add_source_module(self.text, contract_id, module)

    def with_contract_added(self, contract_id: str, module: str, spec: ContractSpec) -> str:
        """This config's text, with a probe-only contract appended."""
        if self.kind == "ini":
            return _ini_add_contract(self.text, contract_id, module, spec)
        return _toml_add_contract(self.text, contract_id, module, spec)


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------


def find_config(start: Path | None = None) -> Path:
    """The nearest import-linter config at or above `start`.

    Walks upwards so the tool can be run from anywhere inside a project, the
    way git is. Only files that actually declare import-linter count — a
    `pyproject.toml` with no `[tool.importlinter]` is somebody else's file.
    """
    start = (start or Path.cwd()).resolve()
    for directory in (start, *start.parents):
        for filename in CONFIG_FILENAMES:
            candidate = directory / filename
            if candidate.is_file() and _declares_import_linter(candidate):
                return candidate
    raise ConfigError(
        f"no import-linter configuration found in {start} or any parent."
        f"\n       Looked for: {', '.join(CONFIG_FILENAMES)}."
        "\n       Pass --config to point at one explicitly."
    )


def _declares_import_linter(path: Path) -> bool:
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return False
    if path.name == "pyproject.toml":
        return "[tool.importlinter]" in text
    return "[importlinter]" in text


def load_config(path: Path | None = None, start: Path | None = None) -> Config:
    """Read the config at `path`, or the nearest one found from `start`."""
    path = (path or find_config(start)).resolve()
    if not path.is_file():
        raise ConfigError(f"no such config file: {path}")
    text = path.read_text()
    kind = "toml" if path.name.endswith(".toml") else "ini"
    parsed = _parse_toml(text) if kind == "toml" else _parse_ini(text)
    root_packages, contracts, unconstrained = parsed
    if not root_packages:
        raise ConfigError(
            f"{path} declares no root_package/root_packages;"
            " import-linter cannot run against it either."
        )
    return Config(
        path=path,
        project_root=path.parent,
        kind=kind,
        text=text,
        root_packages=root_packages,
        contracts=contracts,
        unconstrained=unconstrained,
    )


# ---------------------------------------------------------------------------
# INI
# ---------------------------------------------------------------------------


class _CaseSensitiveParser(configparser.ConfigParser):
    """ConfigParser lowercases option names; ours are module names."""

    def optionxform(self, optionstr: str) -> str:
        return optionstr


def _ini_list(raw: str) -> list[str]:
    return [line.strip() for line in raw.split("\n") if line.strip()]


def _parse_ini(text: str) -> tuple[list[str], dict[str, Contract], dict[str, str]]:
    parser = _CaseSensitiveParser()
    try:
        parser.read_string(text)
    except configparser.Error as error:
        raise ConfigError(f"could not parse config: {error}") from error

    root_packages: list[str] = []
    if parser.has_section("importlinter"):
        root = parser["importlinter"]
        root_packages = _ini_list(root.get("root_packages", ""))
        single = root.get("root_package", "").strip()
        if single and single not in root_packages:
            root_packages.insert(0, single)

    contracts: dict[str, Contract] = {}
    for section in parser.sections():
        if not section.startswith(CONTRACT_PREFIX):
            continue
        contract_id = section[len(CONTRACT_PREFIX) :]
        body = parser[section]
        contracts[contract_id] = Contract(
            id=contract_id,
            name=body.get("name", contract_id).strip(),
            type=body.get("type", "").strip(),
            source_modules=_ini_list(body.get("source_modules", "")),
        )

    unconstrained: dict[str, str] = {}
    for name in INI_UNCONSTRAINED_SECTIONS:
        if parser.has_section(name):
            unconstrained.update(
                {module: (reason or "").strip() for module, reason in parser[name].items()}
            )
    return root_packages, contracts, unconstrained


def _ini_add_source_module(text: str, contract_id: str, module: str) -> str:
    section = re.escape(f"[{CONTRACT_PREFIX}{contract_id}]")
    match = re.search(rf"{section}.*?^source_modules =\n((?:[ \t]+\S+\n)+)", text, re.M | re.S)
    if match is None:
        raise ConfigError(
            f"could not locate an indented source_modules block for contract"
            f" {contract_id!r}. Only the multi-line form is editable."
        )
    return text[: match.end(1)] + f"    {module}\n" + text[match.end(1) :]


def _ini_add_contract(text: str, contract_id: str, module: str, spec: ContractSpec) -> str:
    key, values = _spec_fields(module, spec)
    body = "\n".join(f"    {name}" for name in values)
    prefix = "" if text.endswith("\n") else "\n"
    section = (
        f"\n[{CONTRACT_PREFIX}{contract_id}]\nname = {contract_id} (probe)\ntype = {spec.type}\n"
    )
    if spec.type != "layers":
        section += f"source_modules =\n    {module}\n"
    return f"{text}{prefix}{section}{key} =\n{body}\n"


# ---------------------------------------------------------------------------
# TOML
# ---------------------------------------------------------------------------


def _parse_toml(text: str) -> tuple[list[str], dict[str, Contract], dict[str, str]]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"could not parse config: {error}") from error

    section = data.get("tool", {}).get("importlinter", {})
    root_packages = list(section.get("root_packages", []))
    single = section.get("root_package")
    if single and single not in root_packages:
        root_packages.insert(0, single)

    contracts: dict[str, Contract] = {}
    for raw in section.get("contracts", []):
        # TOML contracts are an array of tables with no section header, so the
        # name is the only thing that can address one.
        name = str(raw.get("name", "")).strip()
        contract_id = str(raw.get("id", name)).strip()
        if not contract_id:
            continue
        contracts[contract_id] = Contract(
            id=contract_id,
            name=name or contract_id,
            type=str(raw.get("type", "")).strip(),
            source_modules=[str(m) for m in raw.get("source_modules", [])],
        )

    table: object = data
    for key in TOML_UNCONSTRAINED_TABLE:
        table = table.get(key, {}) if isinstance(table, dict) else {}
    unconstrained = {}
    if isinstance(table, dict):
        unconstrained = {module: str(reason).strip() for module, reason in table.items()}
    return root_packages, contracts, unconstrained


def _toml_contract_blocks(text: str) -> list[tuple[int, int]]:
    """(start, end) spans of each `[[tool.importlinter.contracts]]` table."""
    spans = []
    header = re.compile(r"^\[\[tool\.importlinter\.contracts\]\]\s*$", re.M)
    next_table = re.compile(r"^\[", re.M)
    for match in header.finditer(text):
        following = next_table.search(text, match.end())
        spans.append((match.end(), following.start() if following else len(text)))
    return spans


def _toml_add_source_module(text: str, contract_id: str, module: str) -> str:
    for start, end in _toml_contract_blocks(text):
        block = text[start:end]
        identifiers = re.findall(r'^\s*(?:name|id)\s*=\s*"([^"]*)"', block, re.M)
        if contract_id not in identifiers:
            continue
        array = re.search(r"^\s*source_modules\s*=\s*\[", block, re.M)
        if array is None:
            raise ConfigError(f"contract {contract_id!r} has no source_modules array to extend")
        insert_at = start + array.end()
        # Valid for both the inline and the multi-line array form: TOML allows
        # a value on the same line as the opening bracket either way.
        return f'{text[:insert_at]}"{module}", {text[insert_at:]}'
    raise ConfigError(f"no contract named {contract_id!r} in the config")


def _toml_add_contract(text: str, contract_id: str, module: str, spec: ContractSpec) -> str:
    key, values = _spec_fields(module, spec)
    body = ", ".join(f'"{name}"' for name in values)
    prefix = "" if text.endswith("\n") else "\n"
    table = f'\n[[tool.importlinter.contracts]]\nname = "{contract_id}"\ntype = "{spec.type}"\n'
    if spec.type != "layers":
        table += f'source_modules = ["{module}"]\n'
    return f"{text}{prefix}{table}{key} = [{body}]\n"


# ---------------------------------------------------------------------------
# shared
# ---------------------------------------------------------------------------

#: Contract type -> the key naming the modules it is checked against, and
#: whether the probed module belongs in that list rather than in source_modules.
_SPEC_KEYS = {
    "forbidden": ("forbidden_modules", False),
    "independence": ("modules", True),
    "layers": ("layers", True),
}


def _spec_fields(module: str, spec: ContractSpec) -> tuple[str, list[str]]:
    try:
        key, includes_module = _SPEC_KEYS[spec.type]
    except KeyError:
        raise ConfigError(
            f"cannot synthesise a {spec.type!r} contract;"
            f" known types: {', '.join(sorted(_SPEC_KEYS))}"
        ) from None
    values = list(spec.modules)
    if includes_module and module not in values:
        # For independence the order is irrelevant; for layers it is everything,
        # so a caller who cares must place the module themselves.
        values.append(module)
    return key, values
