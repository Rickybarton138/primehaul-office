"""
Job Cost Calculator & Charges Tariff routes for PrimeHaul Office Manager.
Day-rate pricing model: crew/day + vans/day + packers/day + materials + distance + access.
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
    distance_miles: float = Form(0),
    num_vans: int = Form(1),
    packing_required: bool = Form(False),
    crew_override: int = Form(0),
    packer_override: int = Form(0),
    # Materials
    small_box: int = Form(0),
    medium_box: int = Form(0),
    large_box: int = Form(0),
    wardrobe_box: int = Form(0),
    packing_paper: int = Form(0),
    tape_roll: int = Form(0),
    king_mattress_bag: int = Form(0),
    single_mattress_bag: int = Form(0),
    # Access
    pickup_floors: int = Form(0),
    pickup_has_lift: bool = Form(False),
    pickup_parking: str = Form("driveway"),
    pickup_parking_distance: int = Form(0),
    pickup_narrow: bool = Form(False),
    pickup_outdoor_steps: int = Form(0),
    pickup_outdoor_path: bool = Form(False),
    dropoff_floors: int = Form(0),
    dropoff_has_lift: bool = Form(False),
    dropoff_parking: str = Form("driveway"),
    dropoff_parking_distance: int = Form(0),
    dropoff_narrow: bool = Form(False),
    dropoff_outdoor_steps: int = Form(0),
    dropoff_outdoor_path: bool = Form(False),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    tariff = get_company_tariff(current_user.company, db)

    result = calculate_job_cost(
        total_cbm=total_cbm,
        distance_miles=distance_miles,
        num_vans=num_vans,
        packing_required=packing_required,
        materials={
            "small_box": small_box, "medium_box": medium_box,
            "large_box": large_box, "wardrobe_box": wardrobe_box,
            "packing_paper": packing_paper, "tape_roll": tape_roll,
            "king_mattress_bag": king_mattress_bag, "single_mattress_bag": single_mattress_bag,
        },
        pickup_access={
            "floors": pickup_floors, "has_lift": pickup_has_lift,
            "parking_type": pickup_parking, "parking_distance_m": pickup_parking_distance,
            "narrow_access": pickup_narrow, "outdoor_steps": pickup_outdoor_steps,
            "outdoor_path": pickup_outdoor_path,
        },
        dropoff_access={
            "floors": dropoff_floors, "has_lift": dropoff_has_lift,
            "parking_type": dropoff_parking, "parking_distance_m": dropoff_parking_distance,
            "narrow_access": dropoff_narrow, "outdoor_steps": dropoff_outdoor_steps,
            "outdoor_path": dropoff_outdoor_path,
        },
        crew_override=crew_override,
        packer_override=packer_override,
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
    man_day_rate: float = Form(300),
    van_day_rate: float = Form(100),
    cbm_per_man_per_day: float = Form(15),
    min_crew: int = Form(2),
    packer_day_rate: float = Form(300),
    max_boxes_per_packer: int = Form(60),
    overnight_reserve_boxes: int = Form(12),
    local_miles_included: int = Form(15),
    distance_tier_1_rate: float = Form(1.50),
    distance_tier_2_rate: float = Form(2.00),
    distance_tier_3_rate: float = Form(2.50),
    distance_tier_4_rate: float = Form(3.00),
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
    small_box: float = Form(3),
    medium_box: float = Form(4),
    large_box: float = Form(5),
    wardrobe_box: float = Form(16),
    packing_paper: float = Form(12.50),
    tape_roll: float = Form(2.50),
    king_mattress_bag: float = Form(8),
    single_mattress_bag: float = Form(5),
    vat_rate: float = Form(0.20),
):
    company = db.query(Company).filter(Company.id == current_user.company_id).first()

    company.pricing_tariff = {
        "man_day_rate": man_day_rate, "van_day_rate": van_day_rate,
        "cbm_per_man_per_day": cbm_per_man_per_day, "min_crew": min_crew,
        "packer_day_rate": packer_day_rate, "max_boxes_per_packer": max_boxes_per_packer,
        "overnight_reserve_boxes": overnight_reserve_boxes,
        "local_miles_included": local_miles_included,
        "distance_tier_1_rate": distance_tier_1_rate, "distance_tier_2_rate": distance_tier_2_rate,
        "distance_tier_3_rate": distance_tier_3_rate, "distance_tier_4_rate": distance_tier_4_rate,
        "price_per_floor": price_per_floor, "no_lift_surcharge": no_lift_surcharge,
        "parking_driveway": 0, "parking_street": parking_street,
        "parking_permit": parking_permit, "parking_limited": parking_limited,
        "parking_distance_per_50m": parking_distance_per_50m,
        "narrow_access_fee": narrow_access_fee, "time_restriction_fee": time_restriction_fee,
        "booking_required_fee": booking_required_fee,
        "outdoor_steps_per_5": outdoor_steps_per_5, "outdoor_path_fee": outdoor_path_fee,
        "small_box": small_box, "medium_box": medium_box,
        "large_box": large_box, "wardrobe_box": wardrobe_box,
        "packing_paper": packing_paper, "tape_roll": tape_roll,
        "king_mattress_bag": king_mattress_bag, "single_mattress_bag": single_mattress_bag,
        "vat_rate": vat_rate,
    }
    db.commit()

    return RedirectResponse(url="/tariff", status_code=302)
