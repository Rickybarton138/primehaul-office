# PrimeHaul Office Manager — Build Plan

## Sprint 1: Foundation (Current)
- [x] Scaffold project structure
- [x] CLAUDE.md + tasks
- [x] Core modules: config, database, auth, dependencies, models, error_tracking
- [x] Main FastAPI app with health check
- [x] Company + User models (with franchise fields)
- [x] Login/signup flow (Jinja2)
- [x] Admin dashboard shell
- [x] Alembic setup + initial migration
- [x] requirements.txt + railway.json + startup.py
- [x] GitHub repo created (Rickybarton138/primehaul-office)
- [ ] Tests: health, auth

## Sprint 2: Staff, Vehicles, Diary
- [ ] staff_members model + CRUD
- [ ] vehicles model + CRUD
- [ ] diary_events model + calendar API
- [ ] Admin pages: staff list, vehicle fleet, calendar view
- [ ] Alembic migration

## Sprint 3: Jobs, Crew, Materials
- [ ] job_assignments + crew_assignments models
- [ ] materials_inventory + materials_usage models
- [ ] mileage_logs model
- [ ] Job scheduling endpoints
- [ ] Materials stock management
- [ ] Job status workflow: new → quoted → booked → scheduled → in_progress → completed

## Sprint 4: Lead Ingestion + Reviews
- [ ] external_lead_sources + external_leads models
- [ ] review_requests model
- [ ] POST /api/v1/ingest/lead webhook
- [ ] Adapters: PrimeHaul Leads, CompareMyMove, AnyVan, manual
- [ ] Lead → Job conversion
- [ ] Review automation (post-completion triggers)

## Sprint 5: Frontend Polish
- [ ] Calendar/diary (fullcalendar.js)
- [ ] Lead pipeline (kanban)
- [ ] Materials stock page
- [ ] Route planning (Mapbox)
- [ ] Review dashboard
- [ ] Daily briefing page
- [ ] Email comms dashboard
- [ ] Social autopilot
