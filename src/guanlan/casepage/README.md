# Case page contracts

One document identifies one server-side case directory through a configured case
ID. Geometry and mesh occupy the first two blocks. Up to six additional slice
blocks specify a field, axis-aligned plane, normalized offset, camera, palette
and automatic or fixed color range. Unknown fields/keys and oversized requests
are rejected. Geometry means the CFD domain boundary, not original CAD.

API: `validate_document(document, fields=None)`, `default_document(case_id)`.
Inputs/outputs are JSON mappings. No I/O, credentials, inference or solver writes.
Dependencies: Python standard library. Dependents: worker, session, live web server.
Example: `default_document('example-case')`. Verification: local case-page contract tests.
