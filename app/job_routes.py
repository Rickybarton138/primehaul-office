"""
Job management routes for PrimeHaul Office Manager.
Job assignments, crew allocation, scheduling, status workflow.
"""

from datetime import datetime, date, time
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import (
    User, JobAssignment, CrewAssignment, StaffMember, Vehicle, DiaryEvent
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
templates = Jinja2Templates(directory="app/templates")

JOB_STATUSES = ["new", "contacted", "quoted", "booked", "scheduled", "in_progress", "completed", "cancelled"]


@router.get("", response_class=HTMLResponse)
def job_list(
    request: Request,
    status: str = "",
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    query = db.query(JobAssignment).filter(JobAssignment.company_id == current_user.company_id)
    if status:
        query = query.filter(JobAssignment.status == status)
    jobs = query.order_by(JobAssignment.created_at.desc()).limit(100).all()

    status_counts = dict(
        db.query(JobAssignment.status, func.count())
        .filter(JobAssignment.company_id == current_user.company_id)
        .group_by(JobAssignment.status)
        .all()
    )

    return templates.TemplateResponse("jobs/list.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "jobs": jobs,
        "statuses": JOB_STATUSES,
        "status_counts": status_counts,
        "active_status": status,
    })


@router.get("/add", response_class=HTMLResponse)
def job_add_form(
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    vehicles = db.query(Vehicle).filter(
        Vehicle.company_id == current_user.company_id, Vehicle.is_active == True
    ).order_by(Vehicle.registration).all()
    staff = db.query(StaffMember).filter(
        StaffMember.company_id == current_user.company_id, StaffMember.is_active == True
    ).order_by(StaffMember.full_name).all()

    return templates.TemplateResponse("jobs/form.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "job": None,
        "vehicles": vehicles,
        "staff": staff,
        "editing": False,
    })


@router.post("/add")
def job_add_submit(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(""),
    customer_phone: str = Form(""),
    pickup_address: str = Form(""),
    pickup_postcode: str = Form(""),
    dropoff_address: str = Form(""),
    dropoff_postcode: str = Form(""),
    property_type: str = Form(""),
    total_cbm: float = Form(0),
    total_items: int = Form(0),
    special_requirements: str = Form(""),
    scheduled_date: str = Form(""),
    scheduled_start_time: str = Form(""),
    estimated_duration_hours: float = Form(0),
    vehicle_id: str = Form(""),
    quoted_price: float = Form(0),
    notes: str = Form(""),
    source: str = Form("manual"),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    job = JobAssignment(
        company_id=current_user.company_id,
        customer_name=customer_name.strip(),
        customer_email=customer_email.strip().lower() if customer_email else None,
        customer_phone=customer_phone.strip() if customer_phone else None,
        pickup={"address": pickup_address.strip(), "postcode": pickup_postcode.strip()} if pickup_address else None,
        dropoff={"address": dropoff_address.strip(), "postcode": dropoff_postcode.strip()} if dropoff_address else None,
        property_type=property_type if property_type else None,
        total_cbm=total_cbm if total_cbm else None,
        total_items=total_items if total_items else 0,
        special_requirements=special_requirements.strip() if special_requirements else None,
        scheduled_date=date.fromisoformat(scheduled_date) if scheduled_date else None,
        scheduled_start_time=time.fromisoformat(scheduled_start_time) if scheduled_start_time else None,
        estimated_duration_hours=estimated_duration_hours if estimated_duration_hours else None,
        vehicle_id=vehicle_id if vehicle_id else None,
        quoted_price_pence=int(quoted_price * 100) if quoted_price else None,
        notes=notes.strip() if notes else None,
        source=source,
        status="new",
    )
    db.add(job)
    db.commit()

    return RedirectResponse(url=f"/jobs/{job.id}", status_code=302)


@router.get("/{job_id}", response_class=HTMLResponse)
def job_detail(
    job_id: str,
    request: Request,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    job = db.query(JobAssignment).filter(
        JobAssignment.id == job_id,
        JobAssignment.company_id == current_user.company_id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    crew = (
        db.query(CrewAssignment)
        .options(joinedload(CrewAssignment.staff_member))
        .filter(CrewAssignment.job_assignment_id == job_id)
        .all()
    )

    available_staff = db.query(StaffMember).filter(
        StaffMember.company_id == current_user.company_id, StaffMember.is_active == True
    ).order_by(StaffMember.full_name).all()

    vehicles = db.query(Vehicle).filter(
        Vehicle.company_id == current_user.company_id, Vehicle.is_active == True
    ).order_by(Vehicle.registration).all()

    return templates.TemplateResponse("jobs/detail.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "job": job,
        "crew": crew,
        "available_staff": available_staff,
        "vehicles": vehicles,
        "statuses": JOB_STATUSES,
    })


@router.post("/{job_id}/status")
def job_update_status(
    job_id: str,
    new_status: str = Form(...),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    job = db.query(JobAssignment).filter(
        JobAssignment.id == job_id,
        JobAssignment.company_id == current_user.company_id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = new_status
    if new_status == "in_progress" and not job.actual_start_time:
        job.actual_start_time = datetime.utcnow()
    elif new_status == "completed" and not job.actual_end_time:
        job.actual_end_time = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)


@router.post("/{job_id}/assign-vehicle")
def job_assign_vehicle(
    job_id: str,
    vehicle_id: str = Form(...),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    job = db.query(JobAssignment).filter(
        JobAssignment.id == job_id,
        JobAssignment.company_id == current_user.company_id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.vehicle_id = vehicle_id if vehicle_id else None
    job.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)


@router.post("/{job_id}/assign-crew")
def job_assign_crew(
    job_id: str,
    staff_member_id: str = Form(...),
    role_on_job: str = Form("porter"),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    job = db.query(JobAssignment).filter(
        JobAssignment.id == job_id,
        JobAssignment.company_id == current_user.company_id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = db.query(CrewAssignment).filter(
        CrewAssignment.job_assignment_id == job_id,
        CrewAssignment.staff_member_id == staff_member_id,
    ).first()
    if existing:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    assignment = CrewAssignment(
        job_assignment_id=job_id,
        staff_member_id=staff_member_id,
        role_on_job=role_on_job,
    )
    db.add(assignment)
    db.commit()

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)


@router.post("/{job_id}/remove-crew/{crew_id}")
def job_remove_crew(
    job_id: str,
    crew_id: str,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    assignment = db.query(CrewAssignment).filter(
        CrewAssignment.id == crew_id,
        CrewAssignment.job_assignment_id == job_id,
    ).first()
    if assignment:
        db.delete(assignment)
        db.commit()

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)


@router.post("/{job_id}/schedule-diary")
def job_create_diary_event(
    job_id: str,
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    """Auto-create a diary event from a scheduled job."""
    job = db.query(JobAssignment).filter(
        JobAssignment.id == job_id,
        JobAssignment.company_id == current_user.company_id,
    ).first()
    if not job or not job.scheduled_date:
        raise HTTPException(status_code=400, detail="Job must have a scheduled date")

    start_time = datetime.combine(
        job.scheduled_date,
        job.scheduled_start_time or time(9, 0),
    )
    duration_hours = float(job.estimated_duration_hours or 4)
    from datetime import timedelta
    end_time = start_time + timedelta(hours=duration_hours)

    crew = db.query(CrewAssignment).filter(CrewAssignment.job_assignment_id == job_id).all()
    staff_ids = [str(c.staff_member_id) for c in crew]

    event = DiaryEvent(
        company_id=current_user.company_id,
        title=f"{job.customer_name}",
        event_type="job",
        start_time=start_time,
        end_time=end_time,
        job_assignment_id=job.id,
        vehicle_id=job.vehicle_id,
        staff_member_ids=staff_ids,
        color="#2ee59d",
    )
    db.add(event)
    db.commit()

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)
