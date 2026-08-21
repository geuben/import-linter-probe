# Contributing

Thanks for your interest in import-linter-probe.

## AI contributions are welcome

Contributions authored by coding agents — autonomously or supervised — are
welcome and held to the same bar as any other: the ground rules below, a test
for every behaviour change, and a PR that explains itself. You don't need to
disclose that a contribution is AI-authored, though noting the model in the PR
is appreciated.

## Development setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/geuben/import-linter-probe
cd import-linter-probe
uv sync
uv run pytest
```

## Ground rules

- Every behaviour change needs a test. The suite is fast; run all of it.
- `probe` must restore the working tree byte-identically — the stub and config
  edit are undone in a `finally`, and the restore is asserted. Any change to
  the probe path must preserve that guarantee and keep its test.
- Lint with `uv run ruff check src tests` and type-check with `uv run mypy src`
  (the project is `strict`). Both run in CI.
- Touching `.github/` means running `uv run zizmor .` too — CI audits the
  workflows with [zizmor](https://github.com/zizmorcore/zizmor) and fails on any
  finding. Actions are hash-pinned with a `# vN` comment; Dependabot moves the
  pins. If a finding is a deliberate choice rather than a bug, suppress it with
  a `# zizmor: ignore[audit-name]` comment that says why, don't loosen the gate.

## Pull requests

- Keep PRs focused — one concern per PR.
- Write commit messages that state the behaviour change, not the mechanics.
- CI must pass (tests on Python 3.11–3.14, lint, type-check, workflow audit,
  build + wheel smoke test).

## Reporting bugs

Open an issue with the command you ran, the config it ran against (redacted as
needed), and what you expected versus what happened.
