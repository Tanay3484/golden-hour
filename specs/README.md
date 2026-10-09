# Specs — AI-PDLC workflow

Every feature goes through four gated phases. An AI agent may draft any phase, but a **human approves each
gate** before the next phase starts. Approval is recorded by setting `Status: Approved` in the file header.

| Phase | File | Answers | Gate |
|-------|------|---------|------|
| 1. Requirements | `requirements.md` | *What* and *why*: user stories, acceptance criteria (EARS), non-goals | Human approves scope |
| 2. Design | `design.md` | *How*: architecture, data flow, interfaces, prompts, risks | Human approves approach |
| 3. Tasks | `tasks.md` | Ordered, small, independently verifiable tasks traced to requirements | Human approves plan |
| 4. Implement & Verify | code + tests | Each task: implement → test → tick checkbox → commit | Tests green, AC demoed |

## Rules

- **Traceability.** Every task cites requirement IDs (e.g. `R2.1`); every acceptance criterion is covered by a
  test or a documented manual check.
- **Specs are the source of truth.** If implementation reveals a spec is wrong, update the spec first (and
  note it in the Changelog), then the code.
- **Small steps.** One task ≈ one commit ≈ one reviewable diff.
- **Open questions block their gate.** A phase can't be approved while it has unresolved open questions.
- **Task ownership.** Every task in `tasks.md` has an owner: `@human` or `@ai`. The AI never implements
  `@human` tasks. It may write the failing tests / interface stubs for them only if the owner asks, and it
  reviews them when asked. Pairing tasks are marked `@human+ai`.

## Acceptance-criteria format (EARS)

- Ubiquitous: `The system SHALL <response>.`
- Event: `WHEN <trigger>, the system SHALL <response>.`
- State: `WHILE <state>, the system SHALL <response>.`
- Unwanted: `IF <condition>, THEN the system SHALL <response>.`

## Index

| ID | Feature | Phase | Status |
|----|---------|-------|--------|
| 001 | [Golden Hour MVP](001-golden-hour-mvp/) | Implement | Approved 2026-10-08 — in progress |
| 002 | [Nearby places for your hobbies](002-nearby-places/) | Implement | Approved 2026-10-09 — in progress |
