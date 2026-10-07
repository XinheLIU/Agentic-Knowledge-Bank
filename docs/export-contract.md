# Export contract

Last updated: 2026-10-04

The canonical source tree can link to another product's owned format. Build with the independent `agent_tools.skills.export` command, passing `--repo`, `--output` and one `--dependency-root` per referenced source repository. These are explicit build inputs; installed skills must not resolve sibling checkout paths.

The exporter copies referenced files transitively, rewrites their links into the output, and names embedded Skill bodies `PROCEDURE.md` so they are not additional discoverable skills. Ownership remains in the source repository; exported files are generated artifacts.

P2 must verify an export in a directory where source checkouts are unavailable and confirm license notices, namespacing and all script/resource paths. Host behavior is not established by copying files successfully.
