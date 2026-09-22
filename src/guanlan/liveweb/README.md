# Block-based case page and sharing

Serves one configured real case at `/case/<case_id>`. The path maps to the profile's
exact server directory, never an arbitrary path from a URL. Geometry and mesh lead;
editable result blocks select plane, offset, field, color scale and camera.
The desktop layout borrows compact rails, subdued panels and theme tokens from
OpenCode/Pi/Paseo. No upstream implementation code is copied.

API: GET `/api/state`, POST `/api/document`, GET `/image/<generation>/<block>.png`,
GET `/snapshot.html`. Snapshot is a standalone HTML page embedding immutable PNGs
and captions, independent of SSH or a running service. Live links continue updating.
POST requests require same-origin checks and are bounded to 64 KiB; the single
page has optimistic revision checks. No shell commands or filesystem paths come
from browser input. The server initially binds loopback; private-network exposure
requires explicit configured bind/public URL, and shared live routes are read-only.

Dependencies: session, casepage, standard library. Dependents: browser.
All assets are local (no CDN or tracking). The service never serves arbitrary files.
POST `/api/reconnect` lets the local owner request a new bounded allocation after
idle/exit; active workers cannot be duplicated. Cached previews stay available.
Verification: unit tests for snapshot immutability, traversal and stale edits;
manual/browser check for field changes, block additions and automatic refresh.
