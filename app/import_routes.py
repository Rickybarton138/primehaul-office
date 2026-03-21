"""
MoveMan survey import routes for PrimeHaul Office Manager.
Paste survey text → parse → auto-generate quote draft.
"""

import json
from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, Quote
from app.moveman_parser import parse_moveman_survey, survey_to_quote_lines
from app.pricing import get_company_tariff

router = APIRouter(prefix="/import", tags=["import"])
templates = Jinja2Templates(directory="app/templates")


def _next_quote_ref(company_id: str, db: Session) -> str:
    from datetime import datetime
    year = datetime.utcnow().year
    count = db.query(Quote).filter(
        Quote.company_id == company_id,
        Quote.quote_ref.like(f"Q-{year}-%"),
    ).count()
    return f"Q-{year}-{count + 1:04d}"


@router.get("/moveman", response_class=HTMLResponse)
def moveman_import_page(
    request: Request,
    current_user: User = Depends(require_role("office")),
):
    return templates.TemplateResponse("import/moveman.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "survey": None,
        "lines": None,
    })


@router.post("/moveman/parse", response_class=HTMLResponse)
def moveman_parse(
    request: Request,
    survey_text: str = Form(...),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    survey = parse_moveman_survey(survey_text)
    tariff = get_company_tariff(current_user.company, db)
    lines = survey_to_quote_lines(survey, tariff)

    subtotal = sum(l["total"] for l in lines)
    vat = subtotal * tariff.get("vat_rate", 0.20)
    total = subtotal + vat

    return templates.TemplateResponse("import/moveman.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "survey": survey,
        "lines": lines,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "lines_json": json.dumps(lines),
        "survey_text": survey_text,
    })


@router.post("/moveman/create-quote")
def moveman_create_quote(
    request: Request,
    survey_text: str = Form(...),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    survey = parse_moveman_survey(survey_text)
    tariff = get_company_tariff(current_user.company, db)
    lines = survey_to_quote_lines(survey, tariff)

    subtotal = sum(l["total"] for l in lines)
    vat = subtotal * tariff.get("vat_rate", 0.20)
    total = subtotal + vat

    quote = Quote(
        company_id=current_user.company_id,
        quote_ref=_next_quote_ref(current_user.company_id, db),
        customer_name=survey.client_name,
        customer_email=survey.email,
        customer_phone=survey.mobile or survey.telephone,
        pickup_address=survey.address_from,
        pickup_postcode=survey.postcode_from,
        dropoff_address=survey.address_to,
        dropoff_postcode=survey.postcode_to,
        total_cbm=survey.total_volume_m3,
        num_vans=max(1, len([l for l in lines if "Vehicle" in l.get("description", "")])),
        packing_required=survey.packing_required,
        line_items=lines,
        subtotal_pence=int(round(subtotal * 100)),
        vat_pence=int(round(vat * 100)),
        total_pence=int(round(total * 100)),
        status="draft",
        created_by_user_id=current_user.id,
        valid_until=date.today() + timedelta(days=30),
        notes=f"Imported from MoveMan survey ({survey.survey_date}). {survey.notes}",
    )
    db.add(quote)
    db.commit()

    return RedirectResponse(url=f"/quotes/{quote.id}", status_code=302)
