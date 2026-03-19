# Lessons Learned

## Architecture Decisions (2026-03-19)
- Office Manager is a **separate app** from OS, not a module — keeps codebases clean, independent pricing
- Road Staff PWA has no backend — talks to Office Manager API directly
- Products communicate via authenticated REST webhooks, no event bus needed yet
- Patterns copied from OS (auth, config, database, startup) then adapted
