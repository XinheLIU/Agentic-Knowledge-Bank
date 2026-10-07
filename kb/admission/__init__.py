"""Deterministic personal admission (ticket 09).

Public surface: :func:`kb.admission.policy.admit` — a pure, per-item,
prompt-free admission function — plus the typed detector specs and the
verbatim hollow-word lists. Reason-code membership stays owned by the shared
``kb/model.py`` registry (O2); this package owns semantics only.
"""

from kb.admission.hollow_words import HOLLOW_WORDS, HOLLOW_WORDS_EN, HOLLOW_WORDS_ZH
from kb.admission.policy import (
    POLICY_ID,
    POLICY_VERSION,
    AdmissionDecision,
    AdmissionPolicy,
    DedupState,
    admit,
    classify_topics,
    source_class_of,
)

__all__ = [
    "POLICY_ID",
    "POLICY_VERSION",
    "AdmissionDecision",
    "AdmissionPolicy",
    "DedupState",
    "HOLLOW_WORDS",
    "HOLLOW_WORDS_EN",
    "HOLLOW_WORDS_ZH",
    "admit",
    "classify_topics",
    "source_class_of",
]
