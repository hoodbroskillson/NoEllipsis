# Releasing

Do **not** publish to PyPI from a laptop. Do **not** move or recreate tags `v1.0.0` (`a757617`) or `v1.1.0` (`99d7456`). Do **not** create a floating `v1` tag.

## Trusted Publisher (PyPI)

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

Let `VERSION` be the value of `project.version` in `pyproject.toml` (also in `src/noellipsis/__init__.py`).

1. `CHANGELOG.md` has a dated `## [VERSION]` section.
2. `docs/release-notes-VERSION.md` exists and contains the marker `{{SHA256SUMS}}` exactly once. The release workflow derives the filename from the verified pyproject version; it does not hardcode a release number.
3. Tests, ruff, `python -m build`, and `twine check` pass locally.
4. A human creates tag `vVERSION` on GitHub. The workflow verifies the tag matches pyproject.

`scripts/render_release_notes.py` writes `dist/SHA256SUMS` first, injects those lines into the notes, and fails if the notes file is missing, the marker is missing/duplicated, or any `{{...}}` placeholder remains. That happens **before** `gh release create`.

## What `release.yml` does

1. **build** job (one build): checkout, test, `python -m build`, `twine check`, render notes + `SHA256SUMS`, upload those **same bytes** as an artifact, attest them with `actions/attest-build-provenance@v4` (`id-token: write` + `attestations: write`), attach the same files to the GitHub Release.
2. **publish** job: `environment: pypi`, download the same artifact, publish to PyPI. No `PYPI_TOKEN`.

Checksums live in `dist/SHA256SUMS` on the release. Attestations are GitHub artifact attestations (Sigstore).
