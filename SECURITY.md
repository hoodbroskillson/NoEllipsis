# Security policy

NoEllipsis is a local static checker. It should never execute the files it reads and never send them anywhere.

## Reporting a vulnerability

Please open a GitHub security advisory (or an issue marked confidential if advisories are unavailable) rather than a public bug if:

- Scanned code can be executed through the tool
- A crafted file can write outside the destination you asked it to read
- The Git integration can mutate the repository

Include a minimal file that reproduces the problem. Do not attach production secrets.

## Non-goals

NoEllipsis is not a vulnerability scanner for the projects you point it at. Findings about placeholders and truncation are quality checks, not CVEs.

Supported versions: the latest `v*.*.*` tag on this repository.
