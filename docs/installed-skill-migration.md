# Installed skill migration

Last updated: 2026-10-04

Canonical ownership changed during P1. The central Skills Manager library, installed IDs, presets and agent deployments were deliberately preserved as existing version snapshots.

After P2 validates self-contained exports, reassociate each existing entry with its new exported source using Skills Manager, then check/update and deploy through the manager. Do not install the same name again and create a suffixed duplicate. Do not edit manager metadata or copy source folders directly into a host.

The private workspace migration record contains the exact installed entry IDs and owner mapping. Source migration is complete; installed-version refresh is pending P2.
