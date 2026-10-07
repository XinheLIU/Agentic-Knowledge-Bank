"""Knowledge base: asset identity, admission, storage and read APIs.

``kb/`` owns the canonical asset store and the rules that decide what is
admitted into it. Collection orchestration — running the Horizon radar,
scheduling, and digests — lives with Information Assistant under
``information_assistant``; this package consumes an already-completed provider
payload through :func:`kb.ingest.ingest_horizon_payload` and exposes accepted
assets through the store, the Flask UI and the MCP server.
"""
