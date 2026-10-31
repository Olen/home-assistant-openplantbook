# Contributing

Thanks for helping improve the **OpenPlantbook** integration! This guide covers the
pull-request workflow and the **PR labels** that drive our release notes.

## Development

```bash
uv venv
uv pip install pytest pytest-cov pytest-homeassistant-custom-component black ruff
python -m pytest tests/ -q       # tests
black . --check --diff           # formatting (CI enforces this)
ruff check .                     # linting (CI enforces this)
```

## Pull requests

- Branch from `main`, open your PR against `main`.
- CI must pass: formatting (Black), linting (Ruff), and the test suite on the
  supported Home Assistant versions.
- Add tests for new behavior and bug fixes.

## PR labels (please add one)

Release notes are generated automatically from **merged-PR labels** (GitHub's
native generator, configured in [`.github/release.yml`](.github/release.yml)).
Add a label so your change lands in the right section of the changelog:

| Label | Release-notes section |
|-------|-----------------------|
| `enhancement` or `feature` | 🚀 Features & Enhancements |
| `bug` or `fix` | 🐛 Bug Fixes |
| `documentation` | 📚 Documentation |
| `chore` | 🧹 Maintenance |
| `ci`, `github_actions`, `dependencies` | _(excluded — build plumbing)_ |
| `release` | _(excluded — see Releases below)_ |
| _(no label)_ | Other Changes |

Pick the single label that best describes the PR's primary intent. Unlabeled PRs
still appear under **Other Changes**, but a label makes the changelog readable.

### For automated agents (Claude Code, etc.)

When you open a PR, apply the matching label in the same step, e.g.:

```bash
gh pr edit <number> --add-label enhancement   # or bug / documentation / dependencies ...
```

## Releases (maintainers)

**Never bump the version in a fix PR.** The bump gets its own PR so several
changes can ship in one release.

To cut a release, open a PR that changes only the version in
`custom_components/openplantbook/manifest.json`, title it `chore: release <version>`,
and label it `release` — that label keeps the bump itself out of the changelog.

On the next green CI run after it merges, the **Auto Release** workflow tags
`v<version>` and publishes a GitHub release (prerelease when the version contains
`beta`), with notes categorized from the merged-PR labels.
Version format: `X.Y.Z` (stable) or `X.Y.Z-betaN` (beta).
