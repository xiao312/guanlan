# Composition layer

Responsibility: CLI composition, no solver-specific logic. Inputs: `check` or
`demo`, `--recipes <directory>`, and optional `--port`. Outputs: validation JSON or
a loopback HTTP server. Dependencies: contracts and delivery; dependent: scripts.
No secrets or external services are required. Invalid inputs fail before binding.

Example: with `PYTHONPATH=src`, `python -m guanlan check --recipes examples/recipes`.
Verification: `./scripts/verify.ps1`; all recipes validate and HTTP tests pass.

`live.py` composes the real-case route: profile -> session -> liveweb. Its
`--check` path validates and prints the remote allocation plan, while normal
execution deploys the worker and serves the configured case. See module READMEs
and `docs/architecture.md` for the added dependency graph and security boundaries.
