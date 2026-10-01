---
name: brainstorming
description: Use when starting a new project or large feature, or when a change needs unresolved design decisions. Skip read-only tasks and straightforward changes with settled requirements.
---

# Design before implementation

The main session owns design. Preserve the user's purpose, constraints and acceptance conditions. Read the relevant existing flow before choosing an approach; do not repeat questions already answered in the request.

**Kickoff.** When starting a new project, or a large feature (more than three files, or a design the codebase does not have yet) with no spec or plan yet, do not infer the goal. Ask until the deliverable, success criteria, constraints, non-goals and target user or environment are clear (skip what the request already answers), summarize them back, and get the user's approval before design or planning. This is the one intake gate; its approval covers the plan that follows. Batch the questions; after two rounds, or when the user says to proceed, record the open assumptions in the summary and continue. A dispatched worker skips this gate.

Choose only the depth the task needs:

- **Bounded change:** requirements and implementation boundary are clear. State the approach briefly when useful, then implement within the existing authorization. No mandatory spec file, plan file or separate approval turn.
- **Feasibility spike:** identify the concrete question and cheapest adequate probe. Read-only checks can proceed. Keep throwaway experiments isolated and label their limits; retaining prototype code requires production verification.
- **Architectural change:** new subsystem, cross-component interface, migration or meaningful unresolved tradeoff. Read [architecture decisions](references/architecture.md), record the design and acceptance conditions, and use `orchestra:writing-plans` when a multi-step implementation plan helps execution.

After kickoff, ask only for missing information or a consequential decision that cannot reasonably be inferred. Existing authorization persists. Honor an explicit request to stop for design or plan approval; otherwise do not turn routine document creation into a new permission gate. Host rules govern destructive or external actions. Record newly discovered scope or risk and reassess only the affected decision.

Stay within the request. Preserve security, privacy, data integrity, accessibility, compatibility and hardware calibration. Avoid unrelated refactoring and speculative features. Use a visual only when it clarifies a real decision, with the available host tools; do not start a separate visual-companion server by default. When the user asks for the browser companion, follow the [visual companion guide](visual-companion.md).

Before implementation, confirm every acceptance condition has a verification path. For behavior changes use meaningful regression/TDD checks; use `orchestra:verification-before-completion` for reusable evidence. No separate planner or reviewer agents.
