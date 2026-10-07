# Knowledge domain invariants

Last updated: 2026-10-04

- Asset identity is minted by KB mapping: preserve the opaque Horizon ID and its namespace; do not infer identity from URLs or colons.
- Reason codes and enum vocabulary are owned by `kb/model.py`; schema CHECK values derive from them.
- Accepted assets, admission decisions and run accounting retain provenance. Replays and duplicates preserve the existing store invariants.
- UI/MCP/Information consume the public AssetStore reader interface. Product consumers do not issue direct SQL or use `_conn`.
- Empty collection is an explicit empty result; partial failures remain visible. Missing SMTP configuration is not successful delivery.
- Real knowledge data is external; do not silently fall back to retired JSON articles.
- The legacy LangGraph production path is retired. Do not reconstruct its workflows, prompts or hooks.
- Fixture tests and the pending plan distinguish implemented source from unverified runtime behavior.
