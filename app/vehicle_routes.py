"""
Vehicle fleet management routes for PrimeHaul Office Manager.
CRUD for vehicles — lutons, transits, containerised.
"""

from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, Vehicle

router = APIRouter(prefix="/vehicles", tags=["vehicles"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def vehicle_list(
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    vehicles = (
        db.query(Vehicle)
        .filter(Vehicle.company_id == current_user.company_id)
        .order_by(Vehicle.is_active.desc(), Vehicle.registration)
        .all()
    )

    # Flag vehicles with expiring docs (within 30 days)
    today = date.today()
    for v in vehicles:
        v.mot_warning = v.mot_expiry and (v.mot_expiry - today).days <= 30
        v.insurance_warning = v.insurance_expiry and (v.insurance_expiry - today).days <= 30
        v.tax_warning = v.tax_expiry and (v.tax_expiry - today).days <= 30

    return templates.TemplateResponse("vehicles/list.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "vehicles": vehicles,
    })


@router.get("/add", response_class=HTMLResponse)
def vehicle_add_form(
    request: Request,
    current_user: User = Depends(require_role("admin")),
):
    return templates.TemplateResponse("vehicles/form.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "vehicle": None,
        "editing": False,
    })


@router.post("/add")
def vehicle_add_submit(
    request: Request,
    registration: str = Form(...),
    make: str = Form(""),
    model: str = Form(""),
    vehicle_type: str = Form("luton_3.5t"),
    capacity_cbm: float = Form(0),
    max_weight_kg: float = Form(0),
    mot_expiry: str = Form(""),
    insurance_expiry: str = Form(""),
    tax_expiry: str = Form(""),
    current_mileage: int = Form(0),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    vehicle = Vehicle(
        company_id=current_user.company_id,
        registration=registration.strip().upper(),
        make=make.strip() if make else None,
        model=model.strip() if model else None,
        vehicle_type=vehicle_type,
        capacity_cbm=capacity_cbm if capacity_cbm else None,
        max_weight_kg=max_weight_kg if max_weight_kg else None,
        mot_expiry=date.fromisoformat(mot_expiry) if mot_expiry else None,
        insurance_expiry=date.fromisoformat(insurance_expiry) if insurance_expiry else None,
        tax_expiry=date.fromisoformat(tax_expiry) if tax_expiry else None,
        current_mileage=current_mileage,
    )
    db.add(vehicle)
    db.commit()
    return RedirectResponse(url="/vehicles", status_code=302)


@router.get("/{vehicle_id}", response_class=HTMLResponse)
def vehicle_detail(
    vehicle_id: str,
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == current_user.company_id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return templates.TemplateResponse("vehicles/detail.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "vehicle": vehicle,
    })


@router.get("/{vehicle_id}/edit", response_class=HTMLResponse)
def vehicle_edit_form(
    vehicle_id: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == current_user.company_id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return templates.TemplateResponse("vehicles/form.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "vehicle": vehicle,
        "editing": True,
    })


@router.post("/{vehicle_id}/edit")
def vehicle_edit_submit(
    vehicle_id: str,
    registration: str = Form(...),
    make: str = Form(""),
    model: str = Form(""),
    vehicle_type: str = Form("luton_3.5t"),
    capacity_cbm: float = Form(0),
    max_weight_kg: float = Form(0),
    mot_expiry: str = Form(""),
    insurance_expiry: str = Form(""),
    tax_expiry: str = Form(""),
    current_mileage: int = Form(0),
    status: str = Form("available"),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == current_user.company_id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle.registration = registration.strip().upper()
    vehicle.make = make.strip() if make else None
    vehicle.model = model.strip() if model else None
    vehicle.vehicle_type = vehicle_type
    vehicle.capacity_cbm = capacity_cbm if capacity_cbm else None
    vehicle.max_weight_kg = max_weight_kg if max_weight_kg else None
    vehicle.mot_expiry = date.fromisoformat(mot_expiry) if mot_expiry else None
    vehicle.insurance_expiry = date.fromisoformat(insurance_expiry) if insurance_expiry else None
    vehicle.tax_expiry = date.fromisoformat(tax_expiry) if tax_expiry else None
    vehicle.current_mileage = current_mileage
    vehicle.status = status
    vehicle.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/vehicles/{vehicle_id}", status_code=302)


@router.post("/{vehicle_id}/toggle")
def vehicle_toggle_active(
    vehicle_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == current_user.company_id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle.is_active = not vehicle.is_active
    vehicle.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/vehicles", status_code=302)
