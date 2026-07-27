# Architecture Decision Records

Records of architecturally significant decisions: what was decided, the context
that forced the decision, and what was given up.

An ADR is worth writing when a decision is expensive to reverse, when the
reasoning is not evident from the code, or when a plausible-looking alternative
was rejected for a non-obvious reason. Routine choices do not need one.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-utc-timestamp-invariant.md) | UTC timestamp invariant | Accepted |

## Conventions

- Filename: `NNNN-short-kebab-title.md`, numbered sequentially from `0001`.
- Status is one of `Proposed`, `Accepted`, `Superseded by NNNN`, or `Deprecated`.
- Do not edit an accepted ADR to reflect a change of mind. Write a new one and
  mark the old one superseded — the point is the record of what was believed at
  the time, not a current-state description.
- Reference the issue and PR that produced the decision.
- Record rejected alternatives and why. That is usually the most useful part
  later, when someone proposes one of them again.

Reference documentation describing how something currently works belongs in
`docs/`, not here. `docs/UTC_TIMESTAMPS.md` and
`docs/adr/0001-utc-timestamp-invariant.md` are the worked example of the split:
the first tells you how to use the invariant, the second tells you why it exists.
