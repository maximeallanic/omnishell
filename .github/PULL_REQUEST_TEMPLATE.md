## What and why

<!-- What does this change, and what problem does it solve? -->

Fixes #

## Type of change

<!-- feat / fix / docs / refactor / test / ci / chore. The PR title must be a Conventional Commit, e.g. "fix(search): ..." -->

## How I checked it

<!-- Commands you ran, GNOME Shell version, distribution, session language. -->

## Screenshots (visual changes)

<!-- Before / after, taken in the nested Shell (dev/screenshots/run.sh) or with no personal data in them. -->

## Checklist

- [ ] `tests/run.sh` passes (and `tests/run.sh --nested` if I touched the extension)
- [ ] New user-facing strings use `_()` / `ngettext()` and `scripts/update-po.sh` was run; `po/fr.po` is translated
- [ ] Code, comments and messages are in English; no language, locale or script is hard-coded
- [ ] No source file over 500 lines
- [ ] I fixed the cause, not the symptom (no swallowed errors, no special cases)
- [ ] I read [CONTRIBUTING.md](https://github.com/maximeallanic/omnishell/blob/main/CONTRIBUTING.md) and the PR title is a Conventional Commit
