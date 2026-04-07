# Contributing

This repository is managed as a research-first codebase. The goal is to keep `main` stable, readable, and easy to review.

## Branching

- `main` should stay deployable for local research use
- create feature branches from `main`
- preferred branch prefixes:
  - `feature/`
  - `fix/`
  - `docs/`
  - `research/`
  - `codex/`

Examples:

- `feature/dashboard-weekly-mode`
- `fix/opportunity-bubble-size`
- `codex/git-workflow-setup`

## Commits

- keep commit messages short and specific
- prefer one logical change per commit
- good examples:
  - `Add dashboard payload mode badge`
  - `Fix negative scatter bubble sizes`
  - `Document local weekly workflow`

## Before Opening A PR

Run:

```bash
make preflight
```

At minimum:

- `make test`
- verify the dashboard still launches
- avoid committing local runtime artifacts

## What Not To Commit

Do not commit:

- `.env`
- `.venv`
- `logs/`
- cached downloads
- SQLite runtime state
- generated exports and reports unless intentionally curating an example artifact

## Pull Requests

Each PR should answer:

- what changed
- why it changed
- how it was validated
- any data caveats or follow-up work

## Research Hygiene

- preserve traceability of scores and labels
- prefer config-driven changes over hard-coded behavior
- keep new signals explainable
- treat fallback/offline sample outputs as development artifacts, not market conclusions
