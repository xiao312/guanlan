# View contracts

Responsibility: validate the supported recipe subset and compute canonical recipe
digests. Non-goals: infer units, resolve unknown fields, interpret CFD results.

Inputs: JSON mappings described in `docs/contracts.md`; outputs: validated mapping
or actionable `ValueError`. Public API: `validate_recipe(value)`, `digest(recipe)`.
Dependencies: Python standard library only. Dependents: preview, delivery, CLI.
Reject unsupported keys, non-finite numbers, wrong units/associations and budgets.
No secrets or filesystem access. Validation is read-only and does not authorize work.

Example: validate parsed `examples/recipes/velocity.json`.
Verification: `./scripts/verify.ps1`; malformed recipes fail and all examples pass.
