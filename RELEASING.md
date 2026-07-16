# Public Release Checklist

A repository maintainer must complete and record each item in the release pull request before changing repository visibility to public.

## Rights and attribution

- [ ] Confirm in writing that the publishing account is authorized to distribute every repository file, including files bearing `Copyright 2026 David Galindo`.
- [ ] Preserve all applicable copyright notices and the Apache-2.0 `LICENSE`.
- [ ] Update [NOTICE](NOTICE) if third-party attribution requirements change.

## Security

- [ ] Run a full-repository, full-history secret scan with an up-to-date scanner such as Gitleaks.
- [ ] Review ignored local artifacts (`.env`, logs, state, reports) for accidental publication.
- [ ] Rotate any credential found in source, history, issues, artifacts, or CI logs before publication.
- [ ] Verify GitHub secret scanning, push protection, and private vulnerability reporting are enabled.

## Quality and GitHub configuration

- [ ] Run `uv lock --check`, `uv run ruff check .`, and `uv run python -m unittest discover -s tests -v`.
- [ ] Require pull requests, review, and successful CI for `main`; disallow force pushes.
- [ ] Confirm default GitHub Actions permissions are read-only and Dependabot is enabled.
- [ ] Review repository description, topics, support links, issue templates, and social preview.
