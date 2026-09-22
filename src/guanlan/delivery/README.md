# Local fixture delivery

Responsibility: serve a visualization-first fixture UI, current preview envelopes,
images and portable frozen SVG downloads. Non-goals: production publishing, auth,
CFD workers, geometry streaming, persistence, or unrestricted static file serving.

API: `create_server(recipes, port) -> HTTPServer`, bound to `127.0.0.1`.
GET `/` serves the viewer; `/api/views` lists saved recipes;
`/api/preview?view=<id>` describes current synthetic output;
`/image?view=<id>&frame=<n>` and `/snapshot?...` render an exact fixture frame.
Only fixed browser assets are served. Unknown paths/views return errors.
Dependencies: contracts, preview, standard library. Dependent: CLI/browser.

Input schema is `docs/contracts.md`. Envelopes identify view, digest, frame, time,
polling cadence and synthetic origin. Memory is bounded by one response render;
there is no growing history or persistent cache. The server is serial and supports
at most two small panels per request. This is intentionally a local development
server, not an exposed sharing endpoint. Images have bounded immutable content;
envelopes are not cached. No credentials or arbitrary filesystem paths are served.

Example: `./scripts/demo.ps1`, then open the printed URL. Verification:
`./scripts/verify.ps1` checks HTTP envelopes, snapshots and invalid routes.
