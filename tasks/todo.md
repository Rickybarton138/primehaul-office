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

## Sprint 2: Staff, Vehicles, Diary ✅
- [x] staff_routes.py: list, add, edit, detail, toggle, optional login creation
- [x] vehicle_routes.py: list, add, edit, detail, toggle, MOT/insurance/tax warnings
- [x] diary_routes.py: calendar page, events JSON API, create/delete, daily briefing
- [x] FullCalendar 6.1 integration (dark theme, month/week/day/list views)
- [x] base_app.html shared nav template + dashboard refactored
- [x] 11 new templates (3 staff, 3 vehicles, 2 diary, 1 base_app, dashboard rewrite)
- [ ] Alembic migration (run on deploy)

## Sprint 3: Jobs, Crew, Materials ✅
- [x] job_routes.py: list (with status filter pills + counts), add form, detail, status update, vehicle assign, crew assign/remove, auto-create diary event
- [x] materials_routes.py: list (with low stock alerts + category filter), add, edit, restock, use/consume, seed 14 default removal materials
- [x] Job status workflow: new → contacted → quoted → booked → scheduled → in_progress → completed → cancelled
- [x] Crew assignment: add staff to jobs with role (porter/driver/lead_driver), remove
- [x] Vehicle assignment per job
- [x] "Add to Diary" button auto-creates calendar event from scheduled job
- [x] Materials: default seed (blankets, boxes, tape, bubble wrap, dollies, ramps, straps, diesel)
- [x] 8 new templates: jobs list, form, detail + materials list, form
- [x] Routers wired into main.py

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
