"""
Staff management routes for PrimeHaul Office Manager.
CRUD for staff members — drivers, porters, surveyors, office staff.
"""

from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, StaffMember
from app.auth import hash_password

router = APIRouter(prefix="/staff", tags=["staff"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def staff_list(
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    staff = (
        db.query(StaffMember)
        .filter(StaffMember.company_id == current_user.company_id)
        .order_by(StaffMember.is_active.desc(), StaffMember.full_name)
        .all()
    )
    return templates.TemplateResponse("staff/list.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "staff": staff,
    })


@router.get("/add", response_class=HTMLResponse)
def staff_add_form(
    request: Request,
    current_user: User = Depends(require_role("admin")),
):
    return templates.TemplateResponse("staff/form.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "staff_member": None,
        "editing": False,
    })


@router.post("/add")
def staff_add_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    role: str = Form("porter"),
    hourly_rate: float = Form(12.0),
    employment_type: str = Form("full_time"),
    license_type: str = Form(""),
    license_expiry: str = Form(""),
    emergency_contact_name: str = Form(""),
    emergency_contact_phone: str = Form(""),
    create_login: bool = Form(False),
    login_password: str = Form(""),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    staff = StaffMember(
        company_id=current_user.company_id,
        full_name=full_name.strip(),
        email=email.strip().lower() if email else None,
        phone=phone.strip() if phone else None,
        role=role,
        hourly_rate_pence=int(hourly_rate * 100),
        employment_type=employment_type,
        license_type=license_type if license_type else None,
        license_expiry=date.fromisoformat(license_expiry) if license_expiry else None,
        emergency_contact_name=emergency_contact_name.strip() if emergency_contact_name else None,
        emergency_contact_phone=emergency_contact_phone.strip() if emergency_contact_phone else None,
    )
    db.add(staff)
    db.flush()

    # Optionally create a login account for this staff member
    if create_login and email and login_password:
        user = User(
            company_id=current_user.company_id,
            email=email.strip().lower(),
            password_hash=hash_password(login_password),
            full_name=full_name.strip(),
            phone=phone.strip() if phone else None,
            role=role,
        )
        db.add(user)
        db.flush()
        staff.user_id = user.id

    db.commit()
    return RedirectResponse(url="/staff", status_code=302)


@router.get("/{staff_id}", response_class=HTMLResponse)
def staff_detail(
    staff_id: str,
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    staff = db.query(StaffMember).filter(
        StaffMember.id == staff_id,
        StaffMember.company_id == current_user.company_id,
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    return templates.TemplateResponse("staff/detail.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "staff_member": staff,
    })


@router.get("/{staff_id}/edit", response_class=HTMLResponse)
def staff_edit_form(
    staff_id: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    staff = db.query(StaffMember).filter(
        StaffMember.id == staff_id,
        StaffMember.company_id == current_user.company_id,
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    return templates.TemplateResponse("staff/form.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "staff_member": staff,
        "editing": True,
    })


@router.post("/{staff_id}/edit")
def staff_edit_submit(
    staff_id: str,
    full_name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    role: str = Form("porter"),
    hourly_rate: float = Form(12.0),
    employment_type: str = Form("full_time"),
    license_type: str = Form(""),
    license_expiry: str = Form(""),
    emergency_contact_name: str = Form(""),
    emergency_contact_phone: str = Form(""),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    staff = db.query(StaffMember).filter(
        StaffMember.id == staff_id,
        StaffMember.company_id == current_user.company_id,
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    staff.full_name = full_name.strip()
    staff.email = email.strip().lower() if email else None
    staff.phone = phone.strip() if phone else None
    staff.role = role
    staff.hourly_rate_pence = int(hourly_rate * 100)
    staff.employment_type = employment_type
    staff.license_type = license_type if license_type else None
    staff.license_expiry = date.fromisoformat(license_expiry) if license_expiry else None
    staff.emergency_contact_name = emergency_contact_name.strip() if emergency_contact_name else None
    staff.emergency_contact_phone = emergency_contact_phone.strip() if emergency_contact_phone else None
    staff.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/staff/{staff_id}", status_code=302)


@router.post("/{staff_id}/toggle")
def staff_toggle_active(
    staff_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    staff = db.query(StaffMember).filter(
        StaffMember.id == staff_id,
        StaffMember.company_id == current_user.company_id,
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    staff.is_active = not staff.is_active
    staff.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/staff", status_code=302)
