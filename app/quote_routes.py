"""
Job Cost Calculator & Charges Tariff routes for PrimeHaul Office Manager.
Interactive quoting tool + editable tariff settings.
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, Company
from app.pricing import DEFAULT_TARIFF, get_company_tariff, calculate_job_cost

router = APIRouter(tags=["quoting"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/quote-calculator", response_class=HTMLResponse)
def quote_calculator_page(
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    tariff = get_company_tariff(current_user.company, db)

    return templates.TemplateResponse("quoting/calculator.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "tariff": tariff,
    })


@router.post("/api/quote-calculate")
def quote_calculate_api(
    request: Request,
    total_cbm: float = Form(0),
    total_weight_kg: float = Form(0),
    bulky_items: int = Form(0),
    fragile_items: int = Form(0),
    distance_miles: float = Form(0),
    # Pickup access
    pickup_floors: int = Form(0),
    pickup_has_lift: bool = Form(False),
    pickup_parking: str = Form("driveway"),
    pickup_parking_distance: int = Form(0),
    pickup_narrow: bool = Form(False),
    pickup_outdoor_steps: int = Form(0),
    pickup_outdoor_path: bool = Form(False),
    # Dropoff access
    dropoff_floors: int = Form(0),
    dropoff_has_lift: bool = Form(False),
    dropoff_parking: str = Form("driveway"),
    dropoff_parking_distance: int = Form(0),
    dropoff_narrow: bool = Form(False),
    dropoff_outdoor_steps: int = Form(0),
    dropoff_outdoor_path: bool = Form(False),
    # Packing
    small_boxes: int = Form(0),
    medium_boxes: int = Form(0),
    large_boxes: int = Form(0),
    wardrobe_boxes: int = Form(0),
    mattress_covers: int = Form(0),
    packing_service_hours: float = Form(0),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    tariff = get_company_tariff(current_user.company, db)

    pickup_access = {
        "floors": pickup_floors,
        "has_lift": pickup_has_lift,
        "parking_type": pickup_parking,
        "parking_distance_m": pickup_parking_distance,
        "narrow_access": pickup_narrow,
        "outdoor_steps": pickup_outdoor_steps,
        "outdoor_path": pickup_outdoor_path,
    }

    dropoff_access = {
        "floors": dropoff_floors,
        "has_lift": dropoff_has_lift,
        "parking_type": dropoff_parking,
        "parking_distance_m": dropoff_parking_distance,
        "narrow_access": dropoff_narrow,
        "outdoor_steps": dropoff_outdoor_steps,
        "outdoor_path": dropoff_outdoor_path,
    }

    packing_boxes = {
        "small_box": small_boxes,
        "medium_box": medium_boxes,
        "large_box": large_boxes,
        "wardrobe_box": wardrobe_boxes,
        "mattress_cover": mattress_covers,
    }

    result = calculate_job_cost(
        total_cbm=total_cbm,
        total_weight_kg=total_weight_kg,
        bulky_items=bulky_items,
        fragile_items=fragile_items,
        distance_miles=distance_miles,
        pickup_access=pickup_access,
        dropoff_access=dropoff_access,
        packing_boxes=packing_boxes,
        packing_service_hours=packing_service_hours,
        tariff=tariff,
    )

    return JSONResponse(result)


@router.get("/tariff", response_class=HTMLResponse)
def tariff_page(
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    tariff = get_company_tariff(current_user.company, db)

    return templates.TemplateResponse("quoting/tariff.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "tariff": tariff,
    })


@router.post("/tariff")
def tariff_update(
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
    # All tariff fields as form inputs
    base_fee: float = Form(250),
    price_per_cbm: float = Form(35),
    bulky_item_fee: float = Form(25),
    fragile_item_fee: float = Form(15),
    weight_threshold_kg: int = Form(1000),
    price_per_kg_over: float = Form(0.50),
    free_miles: int = Form(10),
    price_per_mile: float = Form(1.50),
    price_per_floor: float = Form(15),
    no_lift_surcharge: float = Form(50),
    parking_street: float = Form(25),
    parking_permit: float = Form(40),
    parking_limited: float = Form(60),
    parking_distance_per_50m: float = Form(10),
    narrow_access_fee: float = Form(35),
    time_restriction_fee: float = Form(25),
    booking_required_fee: float = Form(20),
    outdoor_steps_per_5: float = Form(15),
    outdoor_path_fee: float = Form(20),
    labour_rate_per_hour: float = Form(25),
    min_crew: int = Form(2),
    cbm_per_hour: float = Form(5),
    min_labour_hours: float = Form(2),
    small_box: float = Form(3),
    medium_box: float = Form(4),
    large_box: float = Form(5),
    wardrobe_box: float = Form(12),
    mattress_cover: float = Form(8),
    packing_labour_per_hour: float = Form(40),
    vat_rate: float = Form(0.20),
    low_multiplier: float = Form(0.90),
    high_multiplier: float = Form(1.15),
):
    company = db.query(Company).filter(Company.id == current_user.company_id).first()

    company.pricing_tariff = {
        "base_fee": base_fee, "price_per_cbm": price_per_cbm,
        "bulky_item_fee": bulky_item_fee, "fragile_item_fee": fragile_item_fee,
        "weight_threshold_kg": weight_threshold_kg, "price_per_kg_over": price_per_kg_over,
        "free_miles": free_miles, "price_per_mile": price_per_mile,
        "price_per_floor": price_per_floor, "no_lift_surcharge": no_lift_surcharge,
        "parking_driveway": 0, "parking_street": parking_street,
        "parking_permit": parking_permit, "parking_limited": parking_limited,
        "parking_distance_per_50m": parking_distance_per_50m,
        "narrow_access_fee": narrow_access_fee, "time_restriction_fee": time_restriction_fee,
        "booking_required_fee": booking_required_fee,
        "outdoor_steps_per_5": outdoor_steps_per_5, "outdoor_path_fee": outdoor_path_fee,
        "labour_rate_per_hour": labour_rate_per_hour, "min_crew": min_crew,
        "cbm_per_hour": cbm_per_hour, "min_labour_hours": min_labour_hours,
        "small_box": small_box, "medium_box": medium_box,
        "large_box": large_box, "wardrobe_box": wardrobe_box,
        "mattress_cover": mattress_cover, "packing_labour_per_hour": packing_labour_per_hour,
        "vat_rate": vat_rate, "low_multiplier": low_multiplier, "high_multiplier": high_multiplier,
    }
    db.commit()

    return RedirectResponse(url="/tariff", status_code=302)
