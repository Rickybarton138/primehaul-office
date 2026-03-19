# PrimeHaul Office Manager

> Full back-office automation platform for removal companies.
> Owner: Ricky (rickybarton138@btinternet.com)
> Tech Stack: FastAPI + PostgreSQL + SQLAlchemy + Jinja2 + Tailwind CSS

## What This Is

PrimeHaul Office Manager is a standalone B2B SaaS app for removal companies to manage their entire back-office:
- Lead ingestion (from PrimeHaul Leads, CompareMyMove, AnyVan, manual)
- Email comms (automated sequences: quote follow-up, booking confirm, pre-move, post-move review)
- Booking & diary scheduling (calendar view, job scheduling)
- Vehicle & staff allocation (assign vehicles + crew to jobs)
- Route planning (optimize daily routes)
- Materials inventory & stock control (blankets, boxes, tape, fuel, equipment)
- Review collection (Google, Trustpilot, Facebook automation)
- SEO & social stack automation

## Pricing

- **£149/mo** (up to 10 users, extra users £9.99/mo each)
- Part of PrimeHaul franchise bundle at £349/mo

## Part of the PrimeHaul Ecosystem

| Product | Repo | Relationship |
|---------|------|-------------|
| PrimeHaul OS | ~/primehaul | Sends completed survey data via API |
| PrimeHaul Leads | ~/primehaul-leads | Auto-imports leads via webhook |
| PrimeHaul Survey | ~/primehaul-survey | Surveyors use for in-person quotes |
| **Office Manager** | **~/primehaul-office** | **This app — the operational hub** |
| PrimeHaul Road Staff | ~/primehaul-crew | Crew PWA reads from this app's API |

## Agent Behaviour Rules

1. **Plan Mode Default** — Enter plan mode for 3+ step tasks; stop and re-plan on failure
2. **Subagent Strategy** — Offload research/exploration to subagents; one task per subagent
3. **Self-Improvement Loop** — After any user correction, update `tasks/lessons.md`; review lessons each session
4. **Verification Before Done** — Prove it works before marking complete; run tests, check logs
5. **Demand Elegance (Balanced)** — Challenge hacky solutions on non-trivial changes; skip for simple fixes
6. **Autonomous Bug Fixing** — Just fix bugs using logs/errors/tests; zero context switching from user

## Task Management

- `tasks/todo.md` — Plans and progress
- `tasks/lessons.md` — Captured lessons

## Core Principles

- **Simplicity First** — Minimise code impact
- **No Laziness** — Find root causes, senior-level standards
- **All prices in pence** (integers), UUIDs for PKs, UTC datetimes
- **Multi-tenant by company_id** on all tables
- **Cookie-based JWT auth** (24h expiry)
