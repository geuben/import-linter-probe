"""TOML edits are textual, so the array forms have to be pinned down."""

from __future__ import annotations

import tomllib

import pytest

from import_linter_probe.config import _toml_add_source_module

INLINE = """\
[[tool.importlinter.contracts]]
name = "c"
type = "forbidden"
source_modules = ["app.a"]
forbidden_modules = ["app.b"]
"""

MULTILINE = """\
[[tool.importlinter.contracts]]
name = "c"
type = "forbidden"
source_modules = [
    "app.a",
]
forbidden_modules = ["app.b"]
"""


@pytest.mark.parametrize("text", [INLINE, MULTILINE], ids=["inline", "multiline"])
def test_inserts_into_either_array_form(text: str) -> None:
    edited = _toml_add_source_module(text, "c", "app.new")
    contract = tomllib.loads(edited)["tool"]["importlinter"]["contracts"][0]
    assert contract["source_modules"] == ["app.new", "app.a"]
    assert contract["forbidden_modules"] == ["app.b"]


def test_edits_only_the_named_contract() -> None:
    text = INLINE + "\n" + INLINE.replace('name = "c"', 'name = "d"').replace("app.a", "app.z")
    edited = _toml_add_source_module(text, "d", "app.new")
    contracts = tomllib.loads(edited)["tool"]["importlinter"]["contracts"]
    assert contracts[0]["source_modules"] == ["app.a"]
    assert contracts[1]["source_modules"] == ["app.new", "app.z"]


def test_a_contract_table_stops_at_the_next_table() -> None:
    text = INLINE + '\n[tool.ruff]\nsource_modules = ["not-a-contract"]\n'
    edited = _toml_add_source_module(text, "c", "app.new")
    assert tomllib.loads(edited)["tool"]["ruff"]["source_modules"] == ["not-a-contract"]
