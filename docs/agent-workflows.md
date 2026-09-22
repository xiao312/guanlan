# Agent workflows

Two repository-scoped skills live under `.agents/skills` on the project drive:

- `guanlan-paraview`: bounded allocation, strict SSH tunnel, visible matching
  desktop startup and an application-level connection receipt, then explicit stop.
- `guanlan-share`: validated engineer preset, ParaView PNG preparation, bounded
  media-only fetch, offline blocks and optional local MP4 compilation.

They are discoverable when an agent opens this repository. Agents without automatic
skill discovery can read the corresponding SKILL.md directly. No global installer
or coding-agent vendor is required. Keep machine-specific profiles ignored.

The design borrows prerequisite checks, focused task routing, command discovery,
and structured success/error handling from [Lark CLI](https://github.com/larksuite/cli)
and [WeCom CLI skills](https://github.com/WecomTeam/wecom-cli/tree/main/skills).
It does not copy their business rules or introduce messaging/auth dependencies.
Job identity is intentionally visible because it is useful for scheduler operations.

ParaView desktop startup uses the documented
[`--url` and `--script` options](https://docs.paraview.org/en/latest/UsersGuide/commandLineArguments.html).
The native desktop connection and the frozen media route use the same engine but
different resource lifetimes. This is not a claim that either always transfers fewer
bytes or renders faster than the other.
