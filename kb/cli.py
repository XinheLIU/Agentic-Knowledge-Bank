"""KB storage operator CLI.

Storage commands retain the pre-existing prototype semantics; the canonical
AssetStore API and MCP remain the production storage surfaces. Collection
orchestration is not a KB command — the run/ingest/digest entries live with
Information Assistant (``information-run`` / ``information-assistant``), and
KB accepts their payload through :func:`kb.ingest.ingest_horizon_payload`.
"""
from __future__ import annotations
import argparse
from kb.horizon.contract import BackupSummary, ExportSummary, RestoreSummary, ServeSummary, ExitCode, summary
from kb.store_proto import PrototypeStore
from kb.paths import data_root

def _serve(mode: str, host: str, port: int) -> tuple[int, ServeSummary]:
    # Declares the transport; launching MCP-over-SQLite is ticket 11's surface.
    return ExitCode.OK, ServeSummary(mode=mode, host=host, port=port)


def _export(store: PrototypeStore, path: str) -> tuple[int, ExportSummary]:
    return ExitCode.OK, ExportSummary(path=path, item_count=len(store.items))


def _backup(store: PrototypeStore, path: str) -> tuple[int, BackupSummary]:
    return ExitCode.OK, BackupSummary(
        path=path, size_bytes=0, item_count=len(store.items)
    )


def _restore(path: str, *, dry_run: bool) -> tuple[int, RestoreSummary]:
    return ExitCode.OK, RestoreSummary(
        path=path, restored=not dry_run, dry_run=dry_run, item_count=0
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kb")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--mode", default="mcp-sqlite")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=5051)
    for command in ("export", "backup"):
        child = sub.add_parser(command)
        child.add_argument("--path", default=str(data_root() / ("export/kb.jsonl" if command == "export" else "backups/kb.sqlite")))
    restore = sub.add_parser("restore")
    restore.add_argument("path")
    restore.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = PrototypeStore()
    if args.command == "serve":
        code, result = _serve(args.mode, args.host, args.port)
    elif args.command == "export":
        code, result = _export(store, args.path)
    elif args.command == "backup":
        code, result = _backup(store, args.path)
    else:
        code, result = _restore(args.path, dry_run=args.dry_run)
    print(summary(args.command, result.to_payload()))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
