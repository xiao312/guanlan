# Synthetic preview fixture

Responsibility: generate visibly synthetic small SVG images for UI development.
Non-goals: CFD parsing, physical interpretation, three-dimensional rendering.

API: `render(recipe, frame) -> bytes`; frame is a bounded nonnegative integer.
Recipe input follows contracts; output is an SVG with complete recipe metadata,
simulation time and a synthetic watermark. No disk cache or solver data is used.
Dependencies: contracts and Python standard library. Dependent: delivery.
Only the declared fixture plane and camera are supported; field/range changes
affect the deterministic rendering. Payloads exceeding the recipe limit fail.

Security: text and metadata are XML-escaped. No external SVG resources or scripts.
Example: `render(validated_recipe, 10)`. Verification: `./scripts/verify.ps1`;
same recipe/frame produces identical bytes and snapshot metadata remains frozen.
