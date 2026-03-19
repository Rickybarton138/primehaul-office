"""
PrimeHaul Office Manager — Main FastAPI Application
Full back-office automation for removal companies.
"""

import logging
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.error_tracking import ErrorTrackingMiddleware
from app.auth import hash_password, verify_password, create_access_token, validate_password_strength
from app.models import Company, User
from app.dependencies import get_current_user, get_optional_current_user, require_role

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# App Setup
# ──────────────────────────────────────────────

app = FastAPI(
    title="PrimeHaul Office Manager",
    description="Full back-office automation for removal companies",
    version="0.1.0",
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})

# Error tracking middleware
app.add_middleware(ErrorTrackingMiddleware)

# Static files & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for Railway."""
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "service": "primehaul-office", "timestamp": datetime.utcnow().isoformat()}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "service": "primehaul-office"},
        )


# ──────────────────────────────────────────────
# Public Pages
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing_page(request: Request, current_user=Depends(get_optional_current_user)):
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("landing.html", {"request": request})


# ──────────────────────────────────────────────
# Auth: Login / Signup / Logout
# ──────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@app.post("/login")
@limiter.limit("10/minute")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.lower().strip(), User.is_active == True).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=401,
        )

    token = create_access_token(user_id=str(user.id), company_id=str(user.company_id), role=user.role)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=86400,  # 24 hours
    )
    return response


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("auth/signup.html", {"request": request})


@app.post("/signup")
@limiter.limit("5/minute")
def signup_submit(
    request: Request,
    company_name: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower().strip()

    # Check if email already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse(
            "auth/signup.html",
            {"request": request, "error": "An account with this email already exists"},
            status_code=400,
        )

    # Validate password
    is_valid, error_msg = validate_password_strength(password)
    if not is_valid:
        return templates.TemplateResponse(
            "auth/signup.html",
            {"request": request, "error": error_msg},
            status_code=400,
        )

    # Create company
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    existing_slug = db.query(Company).filter(Company.slug == slug).first()
    if existing_slug:
        import uuid
        slug = f"{slug}-{str(uuid.uuid4())[:8]}"

    company = Company(
        company_name=company_name.strip(),
        slug=slug,
        email=email,
        phone=phone.strip(),
        subscription_tier="trial",
    )
    db.add(company)
    db.flush()

    # Create owner user
    user = User(
        company_id=company.id,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        phone=phone.strip(),
        role="owner",
    )
    db.add(user)
    db.commit()

    # Auto-login
    token = create_access_token(user_id=str(user.id), company_id=str(company.id), role=user.role)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=86400,
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ──────────────────────────────────────────────
# Dashboard (authenticated)
# ──────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import JobAssignment, StaffMember, Vehicle, ExternalLead

    company_id = current_user.company_id

    # KPIs
    total_jobs = db.query(JobAssignment).filter(JobAssignment.company_id == company_id).count()
    active_jobs = db.query(JobAssignment).filter(
        JobAssignment.company_id == company_id,
        JobAssignment.status.in_(["new", "contacted", "quoted", "booked", "scheduled", "in_progress"]),
    ).count()
    staff_count = db.query(StaffMember).filter(StaffMember.company_id == company_id, StaffMember.is_active == True).count()
    vehicle_count = db.query(Vehicle).filter(Vehicle.company_id == company_id, Vehicle.is_active == True).count()
    new_leads = db.query(ExternalLead).filter(
        ExternalLead.company_id == company_id, ExternalLead.status == "new"
    ).count()

    # Recent jobs
    recent_jobs = (
        db.query(JobAssignment)
        .filter(JobAssignment.company_id == company_id)
        .order_by(JobAssignment.created_at.desc())
        .limit(10)
        .all()
    )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "staff_count": staff_count,
        "vehicle_count": vehicle_count,
        "new_leads": new_leads,
        "recent_jobs": recent_jobs,
    })


# ──────────────────────────────────────────────
# Lead Ingestion API (for external sources)
# ──────────────────────────────────────────────

@app.post("/api/v1/ingest/lead")
async def ingest_lead(request: Request, db: Session = Depends(get_db)):
    """Webhook endpoint for external lead sources (PrimeHaul Leads, CompareMyMove, AnyVan)."""
    # Verify API key
    api_key = request.headers.get("X-API-Key", "")
    if not api_key or api_key != settings.LEAD_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    body = await request.json()

    # Find target company (by company_id or franchise region)
    company_id = body.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id required")

    company = db.query(Company).filter(Company.id == company_id, Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    from app.models import ExternalLead
    lead = ExternalLead(
        company_id=company.id,
        external_ref=body.get("external_ref"),
        customer_name=body.get("customer_name"),
        customer_email=body.get("customer_email"),
        customer_phone=body.get("customer_phone"),
        pickup=body.get("pickup"),
        dropoff=body.get("dropoff"),
        move_date=body.get("move_date"),
        property_type=body.get("property_type"),
        estimated_cbm=body.get("estimated_cbm"),
        notes=body.get("notes"),
        raw_data=body,
        status="new",
    )
    db.add(lead)
    db.commit()

    logger.info(f"Lead ingested for company {company.slug}: {lead.customer_name}")
    return {"status": "ok", "lead_id": lead.id}


# ──────────────────────────────────────────────
# Crew API (for Road Staff PWA)
# ──────────────────────────────────────────────

@app.get("/api/v1/crew/my-jobs")
def crew_my_jobs(
    current_user: User = Depends(require_role("driver")),
    db: Session = Depends(get_db),
):
    """Get today's and upcoming jobs for the authenticated crew member."""
    from app.models import CrewAssignment, JobAssignment, StaffMember

    # Find staff member linked to this user
    staff = db.query(StaffMember).filter(
        StaffMember.user_id == current_user.id,
        StaffMember.is_active == True,
    ).first()

    if not staff:
        return {"jobs": []}

    today = datetime.utcnow().date()
    assignments = (
        db.query(CrewAssignment)
        .join(JobAssignment)
        .filter(
            CrewAssignment.staff_member_id == staff.id,
            JobAssignment.scheduled_date >= today,
            JobAssignment.status.in_(["scheduled", "in_progress"]),
        )
        .order_by(JobAssignment.scheduled_date, JobAssignment.scheduled_start_time)
        .limit(20)
        .all()
    )

    jobs = []
    for a in assignments:
        j = a.job_assignment
        jobs.append({
            "id": j.id,
            "customer_name": j.customer_name,
            "customer_phone": j.customer_phone,
            "pickup": j.pickup,
            "dropoff": j.dropoff,
            "scheduled_date": str(j.scheduled_date) if j.scheduled_date else None,
            "scheduled_start_time": str(j.scheduled_start_time) if j.scheduled_start_time else None,
            "estimated_duration_hours": float(j.estimated_duration_hours) if j.estimated_duration_hours else None,
            "total_cbm": float(j.total_cbm) if j.total_cbm else None,
            "special_requirements": j.special_requirements,
            "status": j.status,
            "role_on_job": a.role_on_job,
        })

    return {"jobs": jobs}
