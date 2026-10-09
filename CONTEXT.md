# Context

> Last updated: 2026-10-08

Canonical terminology for Agentic-Knowledge-Bank. A glossary and nothing else — no implementation, no procedure.

The former admission vocabulary (focus topics, learning tracks, reading priority, scoring, quality grades, the Horizon cutover terms) **moves to Information Assistant** with the admission pipeline — recover its text from git (`git show HEAD:CONTEXT.md`) before the move, since this file no longer holds it. Do not reintroduce it here.

## The knowledge model

| Term | Meaning |
|---|---|
| **Knowledge instance** | One topic's knowledge base. The durable product of this repository: an agreed structure, filled with depth, over a body of material. |
| **Archive** | The external folder of accumulated raw material — what you collected, not what you wrote. Read-only, and never a *stage*. |
| **Material** | One file in the archive, or one section of one file. The atom the archive is inventoried at. |
| **Provenance** | Where a claim came from, recorded per claim. The property the whole product is organised around. |

## The stages

`archive → materials → notes → wiki` is a pipeline, not a filing system. Each stage transforms what it receives and no stage is skipped.

| Term | Meaning |
|---|---|
| **Inventory** | Stage 0. One row per material: what it is, how much of it is worth attention, and how it is identified. |
| **Note** | Stage 1. A topic's material merged, deduplicated, clustered and cleaned with its provenance intact. |
| **Wiki** | Stage 2. The presentation layer: concepts explained to depth, in narrative order. |
| **Evidence** | What a note is. It reports what the material says. Nothing is added, improved, or judged. |
| **Presentation** | What a wiki page is. It explains a concept to a reader. The difference from evidence is the reason both layers exist. |

## Structure

| Term | Meaning |
|---|---|
| **Domain** | The subject one knowledge instance covers. |
| **Thread** | A named line the narrative follows — a sequence of concepts that belongs together. |
| **Core concept** | A concept substantial enough to carry a thread and stand on its own. |
| **Hierarchy** | Domain → thread → core concept. A concept's position in it is declared, not implied. |
| **Parent** | The concept a page hangs under. Sub-variants live inside their parent, not beside it. |
| **Fold** | To place a concept inside the page that owns it rather than giving it a page. The default when a concept's status is unclear. |
| **Admission** | The decision that a concept deserves its own page. It requires carrying a thread and standing at depth. |

## Depth

| Term | Meaning |
|---|---|
| **Level** | One of the four things a concept page must answer: what it is, how it relates, how it computes, where it extends. |
| **Coverage** | How well a level is answered — fully, in part, by a pointer, or not at all. |
| **Gap** | A level with no material and no verified source behind it, named explicitly. A gap is an honest answer; invented content is not. |

## Sources

| Term | Meaning |
|---|---|
| **Primary source** | The work itself — a paper, official documentation, a canonical repository. It can carry a claim, including a priority claim. |
| **Secondary source** | An exposition of a work — a textbook, lecture notes, a course. It can explain; it cannot be the authority for what came first. |
| **Verified source** | A primary or secondary source actually fetched, with its identity and version recorded. Only a verified source may be cited. |
| **Material id** | A stable identifier for one row of the inventory. What a note-derived claim points at. |
| **Source id** | A stable identifier for one verified source. What a supplemented claim points at. |
| **Trust** | How much a source's word is worth. Owned across topics by Information Assistant — a different question from where this instance's claims came from, which is why the two are recorded apart. |

## Narrative and agreement

| Term | Meaning |
|---|---|
| **Narrative** | The agreed architecture of an instance: its hierarchy, its threads, and which concepts are core. |
| **Granularity** | How coarse or fine the page set is. Too fine scatters one idea across thin pages; too coarse buries a concept inside another. |
| **Gate** | A point where the agent stops and the agreement is made before anything is written. Every run has them. |
| **Run** | One end-to-end pass over an instance — inventory, notes, wiki. |
| **Instance schema** | An instance's own conventions, written on first run: its language, its tags, its depth template, its update policy. |
