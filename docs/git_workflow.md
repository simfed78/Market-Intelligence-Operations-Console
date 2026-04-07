# Git Workflow

## Default Flow

1. update `main`
2. create a focused branch
3. make one logical change set
4. run `make preflight`
5. open a pull request
6. merge back into `main`

## Suggested Commands

```bash
git checkout main
git pull --ff-only
git checkout -b feature/short-description
make preflight
git add .
git commit -m "Short clear message"
git push -u origin feature/short-description
```

## Branch Naming

- `feature/...` for new capabilities
- `fix/...` for bug fixes
- `docs/...` for documentation-only work
- `research/...` for notebooks or validation studies
- `codex/...` for AI-assisted implementation branches

## Pull Request Scope

Prefer small PRs:

- one bug fix
- one dashboard enhancement
- one reporting improvement
- one data or model module upgrade

Avoid mixing:

- refactors
- new features
- generated artifacts
- notebook churn

## Generated Files

The repo ignores runtime outputs by default. If you intentionally want to version a sample artifact, add it deliberately in a dedicated commit and mention why in the PR.

## Local Safety Checks

Use:

```bash
make status
make preflight
```

These checks help keep `main` clean and reduce accidental pushes of unverified changes.
