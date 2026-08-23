# Releasing

Do **not** publish to PyPI from a laptop. Do **not** move or recreate tag `v1.0.0` (it points at `a757617`). Do **not** create a floating `v1` tag.

## Trusted Publisher (PyPI)

Create a pending Trusted Publisher on pypi.org for a project that is not published yet:

| Field | Value |
| --- | --- |
| PyPI project | `noellipsis` |
| Owner | `hoodbroskillson` |
| Repository | `NoEllipsis` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

The GitHub Environment name is exactly `pypi`. No PyPI API token is stored in the repository. The publish job uses `id-token: write` only and `pypa/gh-action-pypi-publish@release/v1`.

Once a version is on PyPI it is **immutable**. Fix forward with a new version.

## Tag

1. Version is `1.1.0` in `pyproject.toml` and `src/noellipsis/__init__.py`.
2. `CHANGELOG.md` and `docs/release-notes-1.1.0.md` are dated.
3. Tests, ruff, `python -m build`, and `twine check` pass locally.
4. A human creates `v1.1.0` on GitHub matching the pyproject version. The workflow verifies the tag.

## What `release.yml` does

1. **build** job (one build): checkout, test, `python -m build`, `twine check`, `SHA256SUMS` for the wheel and sdist, upload those **same bytes** as an artifact, attest them with `actions/attest-build-provenance@v3` (`id-token: write` + `attestations: write`), attach the same files to the GitHub Release.
2. **publish** job: `environment: pypi`, download the same artifact, publish to PyPI. No `PYPI_TOKEN`.

Checksums live in `dist/SHA256SUMS` on the release. Attestations are GitHub artifact attestations (Sigstore).
