# Contributing

PRs welcome — see below for the workflow. AI-assisted contributions are
encouraged; please document the model and version used in the PR description.

## Development setup

```bash
git clone https://github.com/chenhk1113/z-pinch-postproc.git
cd z-pinch-postproc
python -m venv .venv
source .venv/Scripts/activate   # MSYS / git-bash on Windows
# .venv\Scripts\activate        # cmd.exe / PowerShell
pip install -r requirements.txt
```

## Code style

- Python 3.11+ (project uses 3.11.15 in CI).
- PEP 8 with line length 100 (configured in `pyproject.toml`).
- All public functions must have docstrings (Numpy style).
- All new code must come with a corresponding test in `tests/`.

## Testing

```bash
pytest tests/ -q                    # full suite (~20s)
pytest tests/test_zpp_tbr.py -v     # single module
pytest tests/ --cov=code            # coverage
```

The pre-commit hook (`py_compile` + 5 MB file size limit) runs
automatically. Big data artifacts (`*.h5`, `*.zip`, `statepoint.*`)
must NOT be committed.

## Tier-based development

The codebase is organized by **Tiers** — each Tier adds one feature
or one validation. See `CHANGELOG.md` for the full Tier history.
To add a new Tier:

1. Plan in `MODEL_ASSUMPTIONS_AND_LIMITATIONS.md` (what new capability,
   what physics, what validation).
2. Implement the feature in `code/` with a clear API.
3. Write tests in `tests/test_zpp_tier<N>.py`.
4. Run the full suite, ensure all pass.
5. Update `CHANGELOG.md` with the Tier entry.
6. Commit with the convention:
   `feat(v<N+0.1>.0): Tier <N+1> — <one-line summary>`
7. Tag with `git tag -a v<N+0.1>.0 -m "..."`.

## Honest negative findings

This project follows the principle that **honest negative results are
features, not bugs**. If a feature doesn't work as expected:

1. Document the failure in `MODEL_ASSUMPTIONS_AND_LIMITATIONS.md`.
2. Document the attempted approach, the failure mode, and the alternative.
3. Add a test that asserts the known limit (so it doesn't get re-attempted).

Examples: Tier 15 smooth closed-form honest failure (documented in
`tests/test_zpp_tier15.py`), Tier 9 Furuta benchmark +106% overshoot
on pure-Li sphere (documented in `tests/test_zpp_tier9_furuta.py`).

## Commit message convention

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`.

Scope: `v<N.M>` for release, `tier<N>` for a specific Tier, or module
name (`tbr`, `geometry`, `transport`).

Subject: imperative mood, ≤ 72 chars, no period.

Body: explain WHAT and WHY, not HOW.

Footer: reference issues, document breaking changes.

## Pull request workflow

1. Fork the repo.
2. Create a feature branch: `git checkout -b feat/v1.5-tier18`.
3. Commit your changes (one logical change per commit).
4. Run the full test suite locally: `pytest tests/ -q`.
5. Push to your fork: `git push origin feat/v1.5-tier18`.
6. Open a PR against `master` on the upstream repo.
7. Reference any related issues.
8. Wait for review. The maintainer will run the test suite again.

## Reporting bugs

Use the GitHub Issues tab. Include:

- Python version (`python --version`)
- OS (Windows / macOS / Linux)
- Exact reproduction steps
- Expected vs actual behavior
- Full traceback if applicable

## License

By contributing, you agree that your contributions will be licensed
under the MIT License.