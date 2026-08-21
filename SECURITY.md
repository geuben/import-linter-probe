# Security

## Trust model

**`probe` runs `lint-imports` (import-linter) against your project.** To answer
"which contract can host this module?", `probe` writes a throwaway stub into
your source tree, appends it to a contract in your config file, and invokes the
`lint-imports` command — which imports your project's modules, exactly as
running import-linter yourself would. The stub and the config edit are both
undone in a `finally`, and the config is asserted byte-identical to the
original before the probe returns. Run `probe` only against a
repository you trust, for the same reason you would not run its test suite or
its `lint-imports` blindly. There is no sandbox; sandboxing belongs to the
agent harness, not this tool.

Other properties worth knowing:

- `probe` mutates the filesystem transiently: it writes a stub module and an
  edited config, runs the linter, then restores both byte-identically. A crash
  or a `SIGKILL` mid-probe can leave the stub or the edited config behind —
  inspect `git status` if a probe is interrupted.
- `audit` is pure config plus filesystem reads. It parses your import-linter
  config and walks the package tree; it never executes your code and never
  edits anything.
- import-linter-probe makes no network calls.

## Reporting a vulnerability

Report privately via GitHub's
[private vulnerability reporting](https://github.com/geuben/import-linter-probe/security/advisories/new)
rather than a public issue. Reports are acknowledged on a best-effort basis;
this is a solo-maintained project.
