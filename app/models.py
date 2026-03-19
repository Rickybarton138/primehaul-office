"""
SQLAlchemy models for PrimeHaul Office Manager.
All tables are multi-tenant by company_id.
Prices in pence (integers). UUIDs for PKs. UTC datetimes.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date, Time,
    ForeignKey, Text, Numeric, JSON,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def new_uuid():
    return str(uuid.uuid4())


# ──────────────────────────────────────────────
# Core: Company + User
# ──────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50))
    address = Column(Text)
    postcode = Column(String(20))
    base_lat = Column(Numeric(10, 7))
    base_lng = Column(Numeric(10, 7))
    service_radius_miles = Column(Integer, default=50)
    logo_url = Column(Text)
    brand_color = Column(String(7), default="#2ee59d")

    # Subscription
    subscription_tier = Column(String(30), default="trial")  # trial, standard, premium, franchise
    stripe_customer_id = Column(String(255))
    trial_ends_at = Column(DateTime)
    max_users = Column(Integer, default=10)

    # Franchise fields
    is_franchise = Column(Boolean, default=False)
    franchise_region = Column(String(100))
    features_enabled = Column(JSON, default=list)
    os_company_slug = Column(String(100))  # links to PrimeHaul OS company
    leads_auto_import = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="company")
    staff_members = relationship("StaffMember", back_populates="company")
    vehicles = relationship("Vehicle", back_populates="company")
    job_assignments = relationship("JobAssignment", back_populates="company")
    materials = relationship("MaterialsInventory", back_populates="company")
    diary_events = relationship("DiaryEvent", back_populates="company")
    external_lead_sources = relationship("ExternalLeadSource", back_populates="company")
    external_leads = relationship("ExternalLead", back_populates="company")
    review_requests = relationship("ReviewRequest", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50))
    role = Column(String(30), default="office")  # owner, admin, office, surveyor, driver, porter
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="users")


# ──────────────────────────────────────────────
# Staff & Vehicles
# ──────────────────────────────────────────────

class StaffMember(Base):
    __tablename__ = "staff_members"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # links to app login if they have one
    full_name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    role = Column(String(50), default="porter")  # driver, porter, surveyor, office
    hourly_rate_pence = Column(Integer, default=1200)  # £12/hr default
    employment_type = Column(String(20), default="full_time")  # full_time, part_time, casual
    license_type = Column(String(20))  # cat_b, cat_c, cat_c1, none
    license_expiry = Column(Date)
    emergency_contact_name = Column(String(255))
    emergency_contact_phone = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="staff_members")
    crew_assignments = relationship("CrewAssignment", back_populates="staff_member")
    mileage_logs = relationship("MileageLog", back_populates="staff_member")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    registration = Column(String(20), nullable=False)
    make = Column(String(100))
    model = Column(String(100))
    vehicle_type = Column(String(50), default="luton_3.5t")  # luton_3.5t, luton_7.5t, transit, containerised
    capacity_cbm = Column(Numeric(10, 2))
    max_weight_kg = Column(Numeric(10, 2))
    mot_expiry = Column(Date)
    insurance_expiry = Column(Date)
    tax_expiry = Column(Date)
    current_mileage = Column(Integer, default=0)
    status = Column(String(20), default="available")  # available, in_use, maintenance, off_road
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="vehicles")
    job_assignments = relationship("JobAssignment", back_populates="vehicle")
    mileage_logs = relationship("MileageLog", back_populates="vehicle")


# ──────────────────────────────────────────────
# Job Scheduling & Crew Assignment
# ──────────────────────────────────────────────

class JobAssignment(Base):
    __tablename__ = "job_assignments"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)

    # Customer details
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255))
    customer_phone = Column(String(50))
    pickup = Column(JSON)  # {address, postcode, lat, lng, floor, lift, parking, notes}
    dropoff = Column(JSON)  # {address, postcode, lat, lng, floor, lift, parking, notes}
    distance_miles = Column(Numeric(10, 2))

    # Job details
    total_cbm = Column(Numeric(10, 2))
    total_items = Column(Integer, default=0)
    property_type = Column(String(50))
    special_requirements = Column(Text)

    # Scheduling
    scheduled_date = Column(Date)
    scheduled_start_time = Column(Time)
    estimated_duration_hours = Column(Numeric(4, 1))
    vehicle_id = Column(String(36), ForeignKey("vehicles.id"), nullable=True)
    route_order = Column(Integer, default=0)  # position in day's route

    # Pricing (all in pence)
    quoted_price_pence = Column(Integer)
    final_price_pence = Column(Integer)
    deposit_pence = Column(Integer)
    deposit_paid = Column(Boolean, default=False)

    # Status
    status = Column(String(30), default="new")
    # new → contacted → quoted → booked → scheduled → in_progress → completed → cancelled
    actual_start_time = Column(DateTime)
    actual_end_time = Column(DateTime)

    # Source tracking
    source = Column(String(50))  # primehaul_leads, comparemymove, anyvan, manual, os_survey
    external_lead_id = Column(String(36), ForeignKey("external_leads.id"), nullable=True)

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="job_assignments")
    vehicle = relationship("Vehicle", back_populates="job_assignments")
    crew_assignments = relationship("CrewAssignment", back_populates="job_assignment")
    materials_usage = relationship("MaterialsUsage", back_populates="job_assignment")
    review_request = relationship("ReviewRequest", back_populates="job_assignment", uselist=False)


class CrewAssignment(Base):
    __tablename__ = "crew_assignments"

    id = Column(String(36), primary_key=True, default=new_uuid)
    job_assignment_id = Column(String(36), ForeignKey("job_assignments.id"), nullable=False)
    staff_member_id = Column(String(36), ForeignKey("staff_members.id"), nullable=False)
    role_on_job = Column(String(30), default="porter")  # lead_driver, driver, porter
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job_assignment = relationship("JobAssignment", back_populates="crew_assignments")
    staff_member = relationship("StaffMember", back_populates="crew_assignments")


# ──────────────────────────────────────────────
# Materials Inventory & Usage
# ──────────────────────────────────────────────

class MaterialsInventory(Base):
    __tablename__ = "materials_inventory"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    item_name = Column(String(200), nullable=False)
    category = Column(String(50), default="packing")  # packing, equipment, consumable, vehicle_accessory
    unit = Column(String(20), default="each")  # each, roll, box, litre
    quantity_in_stock = Column(Integer, default=0)
    reorder_threshold = Column(Integer, default=10)
    reorder_quantity = Column(Integer, default=50)
    unit_cost_pence = Column(Integer, default=0)
    supplier_name = Column(String(200))
    supplier_url = Column(Text)
    last_restock_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="materials")
    usage_records = relationship("MaterialsUsage", back_populates="material")


class MaterialsUsage(Base):
    __tablename__ = "materials_usage"

    id = Column(String(36), primary_key=True, default=new_uuid)
    material_id = Column(String(36), ForeignKey("materials_inventory.id"), nullable=False)
    job_assignment_id = Column(String(36), ForeignKey("job_assignments.id"), nullable=True)
    quantity_used = Column(Integer, nullable=False)
    used_by_staff_id = Column(String(36), ForeignKey("staff_members.id"), nullable=True)
    used_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

    material = relationship("MaterialsInventory", back_populates="usage_records")
    job_assignment = relationship("JobAssignment", back_populates="materials_usage")


# ──────────────────────────────────────────────
# Lead Ingestion
# ──────────────────────────────────────────────

class ExternalLeadSource(Base):
    __tablename__ = "external_lead_sources"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    source_name = Column(String(100), nullable=False)  # primehaul_leads, comparemymove, anyvan, manual
    api_key = Column(String(500))
    webhook_url = Column(Text)
    is_active = Column(Boolean, default=True)
    leads_received = Column(Integer, default=0)
    last_lead_at = Column(DateTime)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="external_lead_sources")
    leads = relationship("ExternalLead", back_populates="source")


class ExternalLead(Base):
    __tablename__ = "external_leads"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    source_id = Column(String(36), ForeignKey("external_lead_sources.id"), nullable=True)
    external_ref = Column(String(200))  # reference from external platform

    customer_name = Column(String(255))
    customer_email = Column(String(255))
    customer_phone = Column(String(50))
    pickup = Column(JSON)
    dropoff = Column(JSON)
    move_date = Column(Date)
    property_type = Column(String(100))
    estimated_cbm = Column(Numeric(10, 2))
    notes = Column(Text)
    raw_data = Column(JSON)  # complete original payload

    status = Column(String(30), default="new")  # new, contacted, quoted, booked, rejected
    converted_to_job_id = Column(String(36), ForeignKey("job_assignments.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="external_leads")
    source = relationship("ExternalLeadSource", back_populates="leads")


# ──────────────────────────────────────────────
# Diary & Calendar
# ──────────────────────────────────────────────

class DiaryEvent(Base):
    __tablename__ = "diary_events"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    title = Column(String(255), nullable=False)
    event_type = Column(String(30), default="job")  # job, survey_visit, maintenance, meeting, blocked
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    all_day = Column(Boolean, default=False)
    job_assignment_id = Column(String(36), ForeignKey("job_assignments.id"), nullable=True)
    vehicle_id = Column(String(36), ForeignKey("vehicles.id"), nullable=True)
    staff_member_ids = Column(JSON, default=list)  # list of staff_member UUIDs
    notes = Column(Text)
    color = Column(String(7))  # hex for calendar display
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="diary_events")


# ──────────────────────────────────────────────
# Mileage & Vehicle Tracking
# ──────────────────────────────────────────────

class MileageLog(Base):
    __tablename__ = "mileage_logs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    vehicle_id = Column(String(36), ForeignKey("vehicles.id"), nullable=False)
    staff_member_id = Column(String(36), ForeignKey("staff_members.id"), nullable=False)
    job_assignment_id = Column(String(36), ForeignKey("job_assignments.id"), nullable=True)
    date = Column(Date, nullable=False)
    start_mileage = Column(Integer, nullable=False)
    end_mileage = Column(Integer, nullable=False)
    fuel_litres = Column(Numeric(6, 2))
    fuel_cost_pence = Column(Integer)
    purpose = Column(String(100), default="job")  # job, depot_transfer, personal
    created_at = Column(DateTime, default=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="mileage_logs")
    staff_member = relationship("StaffMember", back_populates="mileage_logs")


# ──────────────────────────────────────────────
# Reviews
# ──────────────────────────────────────────────

class ReviewRequest(Base):
    __tablename__ = "review_requests"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    job_assignment_id = Column(String(36), ForeignKey("job_assignments.id"), nullable=False)
    customer_email = Column(String(255), nullable=False)
    customer_name = Column(String(255))
    platform = Column(String(30), default="google")  # google, trustpilot, facebook
    review_url = Column(Text)
    sent_at = Column(DateTime)
    clicked_at = Column(DateTime)
    reviewed_at = Column(DateTime)
    status = Column(String(20), default="pending")  # pending, sent, clicked, reviewed, expired
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="review_requests")
    job_assignment = relationship("JobAssignment", back_populates="review_request")


# ──────────────────────────────────────────────
# Operational Logs
# ──────────────────────────────────────────────

class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(500))
    email_type = Column(String(50))  # quote_followup, booking_confirm, pre_move, post_move_review, manual
    status = Column(String(20), default="sent")  # sent, failed, skipped
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    level = Column(String(20), default="ERROR")
    source = Column(String(255))
    message = Column(Text)
    traceback = Column(Text)
    request_method = Column(String(10))
    request_path = Column(String(500))
    request_ip = Column(String(50))
    status_code = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
