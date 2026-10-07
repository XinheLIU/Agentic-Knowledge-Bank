"""Canonical vocabulary: enums, registries, and normalization algorithms.

Single owner per the resolved asset model (ticket 02, ``asset-audit-model.md``
§3.2/§4): this pure, I/O-free module is the ONLY place that declares reason-code
literals, outcome/state/status vocabularies, the ``story_fp`` algorithm, and URL
normalization. ``kb/store/schema.py`` generates its DDL CHECK lists from the
constants here (never copied); admission and consumer modules import codes from
this registry and never declare their own (closes O2; makes G7-class drift
impossible).

Policy-code *semantics* live in ``docs/product/ai-kb/admission-policy.md`` §2;
this module owns membership and namespaces only.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = [
    "ASSET_STATES",
    "OUTCOMES",
    "RUN_STATUSES",
    "ITEM_CONTENT_LANGUAGES",
    "ITEM_SOURCE_TYPES",
    "ReasonCode",
    "ReasonNamespaces",
    "REASON_CODE_REGISTRY",
    "normalize_url",
    "story_fingerprint",
    "mint_radical_id",
]

# ---------------------------------------------------------------------------
# Enumerations (DDL CHECK lists are generated from these)
# ---------------------------------------------------------------------------

#: ``items.state`` — assets carry only accepted/superseded (asset model §2).
ASSET_STATES: Final[tuple[str, ...]] = ("accepted", "superseded")

#: ``admissions.outcome`` — candidate decision ledger outcomes (asset model §6).
OUTCOMES: Final[tuple[str, ...]] = ("accepted", "rejected", "failed", "supersede")

#: ``runs.status`` — durable run status derived by the ingest surface.
RUN_STATUSES: Final[tuple[str, ...]] = ("success", "partial_failure", "failure")

#: ``items.source_type`` — copied verbatim from the radar; open enum, no CHECK.
ITEM_SOURCE_TYPES: Final[tuple[str, ...]] = (
    "repository",
    "paper",
    "blog",
    "discussion",
    "benchmark",
    "tutorial",
    "product",
    "news",
    "documentation",
    "unknown",
)

#: ``items.metadata_json`` language-keyed payload keys (open; documented hint).
ITEM_CONTENT_LANGUAGES: Final[tuple[str, ...]] = ("en", "zh")


# ---------------------------------------------------------------------------
# Reason-code registry (asset model §3.2)
# ---------------------------------------------------------------------------


class ReasonNamespaces:
    """Ordered reason-code namespaces; each code declared exactly once."""

    POLICY_DECISION = (
        "ACCEPTED",
        "TOPIC_P0_BOOST",
        "RESCUED_BY_TOPIC",
        "REJECTED_LOW_SCORE",
        "LOW_SOURCE_TYPE",
    )
    POLICY_NEGATIVE_PATTERNS = (
        "NEG_HYPE_NO_MECHANISM",
        "NEG_HIRING_CONFERENCE",
        "NEG_SHALLOW_LAUNCH",
        "NEG_GENERIC_ENTERPRISE",
    )
    DEDUP = ("DUPLICATE_ID", "DUPLICATE_URL")
    INTEGRITY = (
        "MISSING_SCORE",
        "MISSING_SUMMARY",
        "MALFORMED_ENRICHMENT",
        "MALFORMED_METADATA",
        "MISSING_PUBLISHED_AT",
    )
    POLICY_WARNING = ("LOW_CONFIDENCE_MATCH",)
    TRANSPORT_MAPPING = ("MAP_FAILED", "TRUNCATED_STAGE", "ENVELOPE_INVALID", "STAGE_TIMEOUT")
    RUN_LEVEL = ("ENRICHMENT_UNAVAILABLE",)


class ReasonCode:
    """Namespace accessors and membership predicates over the registry."""

    namespaces: Final[dict[str, tuple[str, ...]]] = {
        "policy_decision": ReasonNamespaces.POLICY_DECISION,
        "policy_negative_patterns": ReasonNamespaces.POLICY_NEGATIVE_PATTERNS,
        "dedup": ReasonNamespaces.DEDUP,
        "integrity": ReasonNamespaces.INTEGRITY,
        "policy_warning": ReasonNamespaces.POLICY_WARNING,
        "transport_mapping": ReasonNamespaces.TRANSPORT_MAPPING,
        "run_level": ReasonNamespaces.RUN_LEVEL,
    }

    @classmethod
    def all_codes(cls) -> tuple[str, ...]:
        ordered: list[str] = []
        for codes in cls.namespaces.values():
            for code in codes:
                if code not in ordered:
                    ordered.append(code)
        return tuple(ordered)

    @classmethod
    def is_registered(cls, code: str) -> bool:
        return code in cls.all_codes()

    @classmethod
    def namespace_of(cls, code: str) -> str | None:
        for namespace, codes in cls.namespaces.items():
            if code in codes:
                return namespace
        return None


#: The registry itself, in canonical namespace order.
REASON_CODE_REGISTRY: Final[tuple[str, ...]] = ReasonCode.all_codes()


# ---------------------------------------------------------------------------
# Normalization algorithms (single owners; used by policy and edges)
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_URL_STRIP_RE = re.compile(r"^https?://", re.IGNORECASE)
_TRAILING_SLASH_RE = re.compile(r"/+$")


def normalize_url(url: str) -> str:
    """Normalize a URL for dedup comparison (admission policy §2.4).

    Strips the ``http(s)://`` scheme, trailing slashes, and lowercases the
    host. Single owner: the admission policy calls this; it never
    re-implements the algorithm.
    """
    value = _URL_STRIP_RE.sub("", url.strip())
    value = _TRAILING_SLASH_RE.sub("", value)
    lowered = value.lower()
    # Lowercasing the whole string also lowercases the path; the policy
    # specifies host lowercasing only, so restore the original case after
    # the first '/' (the host boundary), if present.
    slash = value.find("/")
    if slash == -1:
        return lowered
    return value[:slash].lower() + value[slash:]


def story_fingerprint(title: str, url: str) -> str:
    """Compute ``story_fp = normalize(title) + "|" + domain(url)``.

    Title normalization: lowercase, punctuation stripped, whitespace
    collapsed. Domain: host of the URL (scheme stripped), lowercased, no
    path. Single owner of the algorithm (asset model §1.2).
    """
    normalized_title = _WS_RE.sub(" ", _PUNCT_RE.sub("", title.strip().lower())).strip()
    host = normalize_url(url).split("/", 1)[0]
    return f"{normalized_title}|{host}"


def mint_radical_id(radar: str, opaque_id: str) -> str:
    """Mint ``<radar>:<opaque id>`` exactly once (ADR 0001).

    The opaque id is stored verbatim — colons are legal and an input that
    already contains a namespace-looking prefix is NOT treated as
    pre-namespaced. Minting happens only in the radar mapper
    (``kb/horizon/mapper.py``); the store and every consumer use the
    resulting string verbatim.
    """
    if not radar or not opaque_id:
        raise ValueError("radar and opaque id must be non-empty")
    return f"{radar}:{opaque_id}"
