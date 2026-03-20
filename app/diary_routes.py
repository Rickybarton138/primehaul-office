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
async def diary_create_event(
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    form = await request.form()
    title = form.get("title", "")
    event_type = form.get("event_type", "job")
    start_date = form.get("start_date", "")
    start_time = form.get("start_time", "09:00")
    end_date = form.get("end_date", "") or start_date
    end_time = form.get("end_time", "17:00")
    vehicle_id = form.get("vehicle_id", "")
    notes = form.get("notes", "")

    # Checkboxes send multiple values with same name
    staff_id_list = form.getlist("staff_ids")

    start_dt = datetime.fromisoformat(f"{start_date}T{start_time}")
    end_dt = datetime.fromisoformat(f"{end_date}T{end_time}")

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


@router.get("/api/events/{event_id}")
def diary_get_event(
    event_id: str,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    """Get single event as JSON for the edit modal."""
    event = db.query(DiaryEvent).filter(
        DiaryEvent.id == event_id,
        DiaryEvent.company_id == current_user.company_id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Resolve staff names
    staff_names = []
    if event.staff_member_ids:
        staff_records = db.query(StaffMember).filter(StaffMember.id.in_(event.staff_member_ids)).all()
        staff_names = [s.full_name for s in staff_records]

    # Resolve vehicle registration
    vehicle_reg = ""
    if event.vehicle_id:
        v = db.query(Vehicle).filter(Vehicle.id == event.vehicle_id).first()
        vehicle_reg = v.registration if v else ""

    return {
        "id": event.id,
        "title": event.title,
        "event_type": event.event_type,
        "start_date": event.start_time.strftime("%Y-%m-%d"),
        "start_time": event.start_time.strftime("%H:%M"),
        "end_date": event.end_time.strftime("%Y-%m-%d"),
        "end_time": event.end_time.strftime("%H:%M"),
        "vehicle_id": event.vehicle_id or "",
        "vehicle_reg": vehicle_reg,
        "staff_member_ids": event.staff_member_ids or [],
        "staff_names": staff_names,
        "notes": event.notes or "",
    }


@router.post("/api/events/{event_id}/edit")
async def diary_edit_event(
    event_id: str,
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    event = db.query(DiaryEvent).filter(
        DiaryEvent.id == event_id,
        DiaryEvent.company_id == current_user.company_id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    form = await request.form()
    title = form.get("title", "")
    event_type = form.get("event_type", "job")
    start_date = form.get("start_date", "")
    start_time = form.get("start_time", "09:00")
    end_date = form.get("end_date", "") or start_date
    end_time = form.get("end_time", "17:00")
    vehicle_id = form.get("vehicle_id", "")
    notes = form.get("notes", "")
    staff_id_list = form.getlist("staff_ids")

    event.title = title.strip()
    event.event_type = event_type
    event.start_time = datetime.fromisoformat(f"{start_date}T{start_time}")
    event.end_time = datetime.fromisoformat(f"{end_date}T{end_time}")
    event.vehicle_id = vehicle_id if vehicle_id else None
    event.staff_member_ids = staff_id_list
    event.notes = notes.strip() if notes else None
    event.color = EVENT_COLORS.get(event_type, "#6b7280")
    event.updated_at = datetime.utcnow()
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
