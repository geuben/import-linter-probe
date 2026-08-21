# import-linter-probe

Two answers [import-linter](https://import-linter.readthedocs.io) does not give you:

- **`probe`** — *if I add module X, which contract can host it?*
- **`audit`** — *which modules is no contract looking at?*

Both exist because import-linter is a checker, not a planner. It tells you
whether the code you have obeys the contracts you wrote. It has nothing to say
about code you are about to write, and nothing at all to say about code no
contract mentions.

```bash
pip install import-linter-probe    # or: uv tool install import-linter-probe
```

Python 3.11+. No runtime dependencies — `probe` shells out to whichever
`lint-imports` your project already has, and `audit` needs nothing but the
config and the filesystem.

---

## `probe` — find a contract home for a module you have not written

A module's contract home is a property of its import graph, so it cannot be
looked up. It can only be measured. Doing that by hand means writing a stub,
editing the config, running the linter, reading the output, and then undoing
two edits correctly — which is the step people get wrong.

`probe` does all five, and guarantees the undo:

```bash
import-linter-probe probe \
    --module app.usecases.signing_keys \
    --imports app.services.signing_key_deps app.services.auth_service \
    --contract key-exchange-isolation
```

```
Probing: app.usecases.signing_keys added to existing contract 'key-exchange-isolation'
Stub imports: app.services.signing_key_deps, app.services.auth_service

Contracts: 11 kept, 1 broken.

VERDICT: app.usecases.signing_keys is NOT accepted as written.

Broken contracts
----------------
...
```

`--imports` is the whole experiment. An empty stub passes every contract and
proves nothing, so the answer is only as honest as that list.

### Probing a contract that does not exist yet

Pass the constraints and the contract is synthesised for the run, then removed:

```bash
# forbidden
import-linter-probe probe --module app.usecases.signing_keys \
    --imports app.services.signing_key_deps \
    --contract signing-keys-isolation \
    --forbidden app.persistence.family app.persistence.evidence

# independence
import-linter-probe probe --module app.usecases.billing \
    --imports app.domain.billing \
    --contract context-independence \
    --independence app.domain.orders app.domain.shipping

# layers — highest first, with --module in the position you are proposing
import-linter-probe probe --module app.usecases.billing \
    --imports app.domain.billing \
    --contract app-layers \
    --layers app.api app.usecases.billing app.domain
```

### Nothing is left behind

The probe writes a stub module (plus any missing package directories and their
`__init__.py` files) and one config edit. Every one of those is undone in a
`finally`, and the config is asserted byte-identical afterwards — if the
restore ever failed, you would get a loud message telling you to check
`git diff` before doing anything else, not a quiet mess.

Config edits are textual inserts rather than a parse-and-reserialise round
trip, so even mid-probe the file keeps its comments, key order and formatting.

Exit code `0` means the host contract held; `1` means something broke; `2`
means the probe could not be set up and nothing was written.

---

## `audit` — find the modules no contract is looking at

import-linter only reports on modules named in some contract's
`source_modules`. A module in no contract is not passing — it is *unexamined*,
and `lint-imports` stays green while it drifts.

```bash
import-linter-probe audit
```

```
84 code modules under app: 71 in a contract, 12 declared unconstrained, 1 unexamined.

lint-imports is green on these by omission, not by inspection:

    app.workflows.reconcile

By package:
      1  app.workflows

A blind spot, not necessarily a bug — some of these are deliberately
cross-context. Decide each one; do not bulk-add. Give a module a
contract, or an unconstrained entry saying why it has none.
```

Empty `__init__.py` files and docstring-only modules are skipped: they cannot
import anything, so they cannot break a contract, and listing them would bury
the real findings.

### Declaring a module unconstrained

Some modules genuinely are cross-context, and no contract can describe them
honestly — settings, the database session factory, an exception-to-status map.
Declare those with a reason, and the audit reports them separately instead of
as a blind spot.

The reason is required. A bare list is a mute button; a reason is a record of a
decision.

In `.importlinter`, `setup.cfg` or `tox.ini`:

```ini
[unconstrained]
app.config = infrastructure; settings only, imports no context
app.database = infrastructure; engine and session factory, imports no context
app.exception_map = maps every context's exceptions to status codes; one table by design
```

In `pyproject.toml`:

```toml
[tool.importlinter_probe.unconstrained]
"app.config" = "infrastructure; settings only, imports no context"
"app.database" = "infrastructure; engine and session factory, imports no context"
```

The audit also fails on declarations that have gone stale (the module was
deleted) or contradict themselves (a contract covers it after all), so the list
cannot rot silently.

> **A note on the INI form.** `[unconstrained]` sits in import-linter's own
> config file, and works because import-linter ignores sections it does not
> recognise. That holds for every version tested, but it is not a documented
> guarantee. `[importlinter-probe:unconstrained]` is accepted as an equivalent,
> slightly better-behaved spelling — worth preferring in a shared `setup.cfg`
> or `tox.ini`. The `pyproject.toml` form is outside `[tool.importlinter]`
> entirely and carries no such risk.

---

## Wiring the audit into your test suite

The audit is most useful as a ratchet: a number that may fall and must never
rise. Everything the CLI uses is public API.

```python
# tests/test_import_contract_coverage.py
from import_linter_probe import audit, load_config

# Every module is accounted for. A new module must arrive with a contract or an
# unconstrained entry saying why it has none; this must never rise.
MAX_UNEXAMINED = 0


def test_contract_coverage_does_not_regress() -> None:
    result = audit(load_config())
    assert result.problems == []
    assert len(result.unexamined) <= MAX_UNEXAMINED, result.unexamined
```

Asserting an exact number rather than zero is deliberate when you are adopting
this on an existing codebase: it turns the blind spot into a worklist you burn
down, without blocking the first commit.

Or just add it to your lint step:

```
lint = "ruff check . && lint-imports && import-linter-probe audit"
```

---

## Project layouts and configuration

The config is found the way `git` finds a repo — the nearest `setup.cfg`,
`.importlinter`, `tox.ini` or `pyproject.toml` at or above the working
directory that actually declares import-linter. Override with `--config`.

Root packages come from `root_package` / `root_packages` in that config, and
are looked for in `./<pkg>` and `./src/<pkg>`, so flat and src layouts both
work. `src/app/util.py` is reported as `app.util`, never `src.app.util`.
Override with `--package-root`.

`probe` runs `lint-imports --no-cache`, falling back to
`uv run lint-imports --no-cache` when the former is not on `PATH`. For anything
else — Poetry, Hatch, tox, a venv path — pass it explicitly:

```bash
import-linter-probe probe ... --lint-cmd "poetry run lint-imports --no-cache"
```

Note that `--lint-cmd` is used verbatim, so include `--no-cache` yourself: a
cached run will happily answer a question about the code as it was before the
stub existed.

## Limitations

- `probe` edits the config textually. For INI, `source_modules` must be in the
  indented multi-line form. For TOML, contracts are addressed by their `name`,
  since an array-of-tables entry has no other identity.
- `--layers` builds the contract from the list you give; the probed module must
  be one of the layers, and where you put it is the proposal being tested.
- The verdict is parsed from `lint-imports` console output. It is pinned by
  tests against real import-linter, but it is not a stable API.

## Development

```bash
uv sync
uv run pytest      # the end-to-end tests run real import-linter
uv run ruff check .
uv run mypy src
```

## License

MIT.
