# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-08-21

### Added

- **`probe`** — writes a throwaway stub for a module that does not exist yet,
  containing exactly the imports you say it will have, adds it to a contract,
  runs `lint-imports`, and restores everything byte-identically. Answers "if I
  add module X, which contract can host it?" in one command instead of six.
- **`audit`** — reports the modules that no import-linter contract names in a
  `source_modules` list, so unexamined code that drifts while `lint-imports`
  stays green is surfaced. Deliberately cross-context modules are declared with
  a required reason and reported separately; stale declarations fail the audit.
- Public Python API (`audit`, `load_config`, and supporting types) so a project
  can assert on its own contract coverage from a test.
