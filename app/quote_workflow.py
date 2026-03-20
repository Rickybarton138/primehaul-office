"""
Quote workflow routes for PrimeHaul Office Manager.

Flow: Calculator → Save Draft → Review/Amend → Approve → Email PDF → Track
"""

import io
import smtplib
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, Quote, EmailLog
from app.config import settings
from app.pdf_generator import generate_quote_pdf

router = APIRouter(prefix="/quotes", tags=["quotes"])
templates = Jinja2Templates(directory="app/templates")


def _next_quote_ref(company_id: str, db: Session) -> str:
    """Generate next sequential quote reference: Q-2026-0042"""
    year = datetime.utcnow().year
    count = db.query(Quote).filter(
        Quote.company_id == company_id,
        Quote.quote_ref.like(f"Q-{year}-%"),
    ).count()
    return f"Q-{year}-{count + 1:04d}"


@router.post("/save-draft")
def save_quote_draft(
    request: Request,
    # Customer
    customer_name: str = Form(...),
    customer_email: str = Form(""),
    customer_phone: str = Form(""),
    # Locations
    pickup_address: str = Form(""),
    pickup_postcode: str = Form(""),
    dropoff_address: str = Form(""),
    dropoff_postcode: str = Form(""),
    # Job
    total_cbm: float = Form(0),
    distance_miles: float = Form(0),
    num_vans: int = Form(1),
    packing_required: bool = Form(False),
    move_date: str = Form(""),
    # Line items (JSON string)
    line_items_json: str = Form("[]"),
    subtotal_pence: int = Form(0),
    vat_pence: int = Form(0),
    total_pence: int = Form(0),
    notes: str = Form(""),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    import json
    try:
        line_items = json.loads(line_items_json)
    except (json.JSONDecodeError, TypeError):
        line_items = []

    quote = Quote(
        company_id=current_user.company_id,
        quote_ref=_next_quote_ref(current_user.company_id, db),
        customer_name=customer_name.strip(),
        customer_email=customer_email.strip().lower() if customer_email else None,
        customer_phone=customer_phone.strip() if customer_phone else None,
        pickup_address=pickup_address.strip() if pickup_address else None,
        pickup_postcode=pickup_postcode.strip().upper() if pickup_postcode else None,
        dropoff_address=dropoff_address.strip() if dropoff_address else None,
        dropoff_postcode=dropoff_postcode.strip().upper() if dropoff_postcode else None,
        total_cbm=total_cbm if total_cbm else None,
        distance_miles=distance_miles if distance_miles else None,
        num_vans=num_vans,
        packing_required=packing_required,
        move_date=date.fromisoformat(move_date) if move_date else None,
        line_items=line_items,
        subtotal_pence=subtotal_pence,
        vat_pence=vat_pence,
        total_pence=total_pence,
        status="draft",
        created_by_user_id=current_user.id,
        valid_until=date.today() + timedelta(days=30),
        notes=notes.strip() if notes else None,
    )
    db.add(quote)
    db.commit()

    return RedirectResponse(url=f"/quotes/{quote.id}", status_code=302)


@router.get("", response_class=HTMLResponse)
def quote_list(
    request: Request,
    status: str = "",
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    query = db.query(Quote).filter(Quote.company_id == current_user.company_id)
    if status:
        query = query.filter(Quote.status == status)
    quotes = query.order_by(Quote.created_at.desc()).limit(100).all()

    return templates.TemplateResponse("quotes/list.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "quotes": quotes,
        "active_status": status,
    })


@router.get("/{quote_id}", response_class=HTMLResponse)
def quote_review(
    quote_id: str,
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    quote = db.query(Quote).filter(
        Quote.id == quote_id,
        Quote.company_id == current_user.company_id,
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    return templates.TemplateResponse("quotes/review.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "quote": quote,
    })


@router.post("/{quote_id}/update-line")
def quote_update_line(
    quote_id: str,
    line_index: int = Form(...),
    description: str = Form(...),
    qty: str = Form(""),
    unit_price: float = Form(0),
    total: float = Form(0),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    quote = db.query(Quote).filter(
        Quote.id == quote_id,
        Quote.company_id == current_user.company_id,
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    lines = list(quote.line_items or [])
    if 0 <= line_index < len(lines):
        lines[line_index] = {
            "description": description.strip(),
            "qty": qty,
            "unit_price": unit_price,
            "total": total,
        }
        quote.line_items = lines
        _recalculate_totals(quote)
        quote.updated_at = datetime.utcnow()
        db.commit()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=302)


@router.post("/{quote_id}/add-line")
def quote_add_line(
    quote_id: str,
    description: str = Form(...),
    qty: str = Form(""),
    unit_price: float = Form(0),
    total: float = Form(0),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    quote = db.query(Quote).filter(
        Quote.id == quote_id,
        Quote.company_id == current_user.company_id,
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    lines = list(quote.line_items or [])
    lines.append({
        "description": description.strip(),
        "qty": qty,
        "unit_price": unit_price,
        "total": total,
    })
    quote.line_items = lines
    _recalculate_totals(quote)
    quote.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=302)


@router.post("/{quote_id}/remove-line")
def quote_remove_line(
    quote_id: str,
    line_index: int = Form(...),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    quote = db.query(Quote).filter(
        Quote.id == quote_id,
        Quote.company_id == current_user.company_id,
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    lines = list(quote.line_items or [])
    if 0 <= line_index < len(lines):
        lines.pop(line_index)
        quote.line_items = lines
        _recalculate_totals(quote)
        quote.updated_at = datetime.utcnow()
        db.commit()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=302)


def _recalculate_totals(quote):
    """Recalculate subtotal, VAT, total from line items."""
    lines = quote.line_items or []
    subtotal = sum(line.get("total", 0) for line in lines)
    vat = subtotal * 0.20
    quote.subtotal_pence = int(round(subtotal * 100))
    quote.vat_pence = int(round(vat * 100))
    quote.total_pence = int(round((subtotal + vat) * 100))


@router.post("/{quote_id}/approve")
def quote_approve(
    quote_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    quote = db.query(Quote).filter(
        Quote.id == quote_id,
        Quote.company_id == current_user.company_id,
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    quote.status = "approved"
    quote.approved_by_user_id = current_user.id
    quote.approved_at = datetime.utcnow()
    quote.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=302)


@router.get("/{quote_id}/pdf")
def quote_download_pdf(
    quote_id: str,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    quote = db.query(Quote).filter(
        Quote.id == quote_id,
        Quote.company_id == current_user.company_id,
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    pdf_bytes = generate_quote_pdf(quote, current_user.company)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="quote-{quote.quote_ref}.pdf"'},
    )


@router.post("/{quote_id}/send")
def quote_send_email(
    quote_id: str,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Send the approved quote PDF to the customer via email."""
    quote = db.query(Quote).filter(
        Quote.id == quote_id,
        Quote.company_id == current_user.company_id,
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.status not in ("approved", "sent"):
        raise HTTPException(status_code=400, detail="Quote must be approved before sending")
    if not quote.customer_email:
        raise HTTPException(status_code=400, detail="Customer email is required")

    # Generate PDF
    pdf_bytes = generate_quote_pdf(quote, current_user.company)

    # Build email
    msg = MIMEMultipart()
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = quote.customer_email
    msg["Subject"] = f"Your Removal Quote - {quote.quote_ref} | {current_user.company.company_name}"

    body = f"""Dear {quote.customer_name},

Thank you for your enquiry. Please find attached your removal quote ({quote.quote_ref}).

Quote total: £{quote.total_pence / 100:.2f} (inc. VAT)
Valid until: {quote.valid_until.strftime('%d %B %Y') if quote.valid_until else 'N/A'}

If you would like to proceed, simply reply to this email or call us on {current_user.company.phone or 'the number below'}.

Kind regards,
{current_user.company.company_name}
{current_user.company.phone or ''}
{current_user.company.email or ''}
"""
    msg.attach(MIMEText(body, "plain"))

    # Attach PDF
    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=f"quote-{quote.quote_ref}.pdf")
    msg.attach(pdf_attachment)

    # Send
    email_status = "sent"
    error_message = None
    try:
        if settings.SMTP_USERNAME:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            email_status = "skipped"
            error_message = "SMTP not configured"
    except Exception as e:
        email_status = "failed"
        error_message = str(e)[:500]

    # Log
    log = EmailLog(
        company_id=current_user.company_id,
        to_email=quote.customer_email,
        subject=msg["Subject"],
        email_type="quote",
        status=email_status,
        error_message=error_message,
    )
    db.add(log)

    if email_status == "sent":
        quote.status = "sent"
        quote.sent_at = datetime.utcnow()
    quote.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=302)
