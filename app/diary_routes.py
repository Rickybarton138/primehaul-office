"""
Diary & calendar routes for PrimeHaul Office Manager.
Calendar view, event CRUD, JSON API for fullcalendar.js.
"""

from datetime import datetime, date, timedelta
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, DiaryEvent, JobAssignment, StaffMember, Vehicle

router = APIRouter(prefix="/diary", tags=["diary"])
templates = Jinja2Templates(directory="app/templates")

EVENT_COLORS = {
    "job": "#2ee59d",
    "survey_visit": "#3b82f6",
    "maintenance": "#f59e0b",
    "meeting": "#8b5cf6",
    "blocked": "#ef4444",
}


@router.get("", response_class=HTMLResponse)
def diary_page(
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    staff = (
        db.query(StaffMember)
        .filter(StaffMember.company_id == current_user.company_id, StaffMember.is_active == True)
        .order_by(StaffMember.full_name)
        .all()
    )
    vehicles = (
        db.query(Vehicle)
        .filter(Vehicle.company_id == current_user.company_id, Vehicle.is_active == True)
        .order_by(Vehicle.registration)
        .all()
    )

    return templates.TemplateResponse("diary/calendar.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "staff": staff,
        "vehicles": vehicles,
    })


@router.get("/api/events")
def diary_events_api(
    request: Request,
    start: str = "",
    end: str = "",
    staff_id: str = "",
    vehicle_id: str = "",
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    """JSON API for FullCalendar — returns events in the given date range."""
    query = db.query(DiaryEvent).filter(DiaryEvent.company_id == current_user.company_id)

    if start:
        query = query.filter(DiaryEvent.end_time >= datetime.fromisoformat(start))
    if end:
        query = query.filter(DiaryEvent.start_time <= datetime.fromisoformat(end))
    if staff_id:
        query = query.filter(DiaryEvent.staff_member_ids.contains([staff_id]))
    if vehicle_id:
        query = query.filter(DiaryEvent.vehicle_id == vehicle_id)

    events = query.order_by(DiaryEvent.start_time).all()

    return [
        {
            "id": e.id,
            "title": e.title,
            "start": e.start_time.isoformat(),
            "end": e.end_time.isoformat(),
            "allDay": e.all_day,
            "color": e.color or EVENT_COLORS.get(e.event_type, "#6b7280"),
            "extendedProps": {
                "event_type": e.event_type,
                "job_assignment_id": e.job_assignment_id,
                "vehicle_id": e.vehicle_id,
                "staff_member_ids": e.staff_member_ids or [],
                "notes": e.notes,
            },
        }
        for e in events
    ]


@router.post("/api/events")
def diary_create_event(
    request: Request,
    title: str = Form(...),
    event_type: str = Form("job"),
    start_date: str = Form(...),
    start_time: str = Form("09:00"),
    end_date: str = Form(""),
    end_time: str = Form("17:00"),
    all_day: bool = Form(False),
    vehicle_id: str = Form(""),
    staff_ids: str = Form(""),
    notes: str = Form(""),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    end_date = end_date or start_date
    start_dt = datetime.fromisoformat(f"{start_date}T{start_time}")
    end_dt = datetime.fromisoformat(f"{end_date}T{end_time}")

    staff_id_list = [s.strip() for s in staff_ids.split(",") if s.strip()] if staff_ids else []

    event = DiaryEvent(
        company_id=current_user.company_id,
        title=title.strip(),
        event_type=event_type,
        start_time=start_dt,
        end_time=end_dt,
        all_day=all_day,
        vehicle_id=vehicle_id if vehicle_id else None,
        staff_member_ids=staff_id_list,
        notes=notes.strip() if notes else None,
        color=EVENT_COLORS.get(event_type, "#6b7280"),
    )
    db.add(event)
    db.commit()

    return RedirectResponse(url="/diary", status_code=302)


@router.post("/api/events/{event_id}/delete")
def diary_delete_event(
    event_id: str,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    event = db.query(DiaryEvent).filter(
        DiaryEvent.id == event_id,
        DiaryEvent.company_id == current_user.company_id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    db.delete(event)
    db.commit()
    return RedirectResponse(url="/diary", status_code=302)


@router.get("/today", response_class=HTMLResponse)
def diary_today(
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    """Daily briefing — today's events, jobs, staff, vehicles."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = today_start + timedelta(days=1)

    events = (
        db.query(DiaryEvent)
        .filter(
            DiaryEvent.company_id == current_user.company_id,
            DiaryEvent.start_time < today_end,
            DiaryEvent.end_time > today_start,
        )
        .order_by(DiaryEvent.start_time)
        .all()
    )

    jobs_today = (
        db.query(JobAssignment)
        .filter(
            JobAssignment.company_id == current_user.company_id,
            JobAssignment.scheduled_date == date.today(),
        )
        .order_by(JobAssignment.scheduled_start_time)
        .all()
    )

    return templates.TemplateResponse("diary/today.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "events": events,
        "jobs_today": jobs_today,
        "today": date.today(),
    })
