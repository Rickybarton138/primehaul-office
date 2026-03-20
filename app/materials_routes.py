"""
Materials inventory & stock control routes for PrimeHaul Office Manager.
Track blankets, boxes, tape, fuel, equipment. Reorder alerts.
"""

from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, MaterialsInventory, MaterialsUsage, MileageLog, Vehicle, StaffMember

router = APIRouter(prefix="/materials", tags=["materials"])
templates = Jinja2Templates(directory="app/templates")

# Default materials for a removal company
DEFAULT_MATERIALS = [
    ("Moving Blankets", "equipment", "each", 50, 10, 20, 800),
    ("Small Boxes", "packing", "each", 100, 20, 50, 150),
    ("Medium Boxes", "packing", "each", 80, 20, 50, 250),
    ("Large Boxes", "packing", "each", 60, 15, 30, 350),
    ("Wardrobe Boxes", "packing", "each", 20, 5, 10, 800),
    ("Packing Tape Rolls", "consumable", "roll", 30, 10, 20, 200),
    ("Bubble Wrap", "packing", "roll", 10, 3, 5, 1500),
    ("Packing Paper (kg)", "consumable", "each", 20, 5, 10, 500),
    ("Mattress Covers", "packing", "each", 10, 3, 5, 600),
    ("Sofa Covers", "packing", "each", 10, 3, 5, 800),
    ("Furniture Dollies", "equipment", "each", 4, 2, 2, 5000),
    ("Ramps", "equipment", "each", 2, 1, 1, 15000),
    ("Ratchet Straps", "equipment", "each", 20, 5, 10, 1000),
    ("Diesel (litres)", "consumable", "litre", 200, 50, 100, 155),
]


@router.get("", response_class=HTMLResponse)
def materials_list(
    request: Request,
    category: str = "",
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    query = db.query(MaterialsInventory).filter(
        MaterialsInventory.company_id == current_user.company_id,
        MaterialsInventory.is_active == True,
    )
    if category:
        query = query.filter(MaterialsInventory.category == category)

    materials = query.order_by(MaterialsInventory.category, MaterialsInventory.item_name).all()

    # Flag low stock items
    low_stock = [m for m in materials if m.quantity_in_stock <= m.reorder_threshold]

    return templates.TemplateResponse("materials/list.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "materials": materials,
        "low_stock": low_stock,
        "active_category": category,
        "categories": ["packing", "equipment", "consumable", "vehicle_accessory"],
    })


@router.post("/seed-defaults")
def seed_default_materials(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Seed the default materials inventory for a new company."""
    existing = db.query(MaterialsInventory).filter(
        MaterialsInventory.company_id == current_user.company_id
    ).count()
    if existing > 0:
        return RedirectResponse(url="/materials", status_code=302)

    for name, category, unit, qty, threshold, reorder_qty, cost in DEFAULT_MATERIALS:
        mat = MaterialsInventory(
            company_id=current_user.company_id,
            item_name=name,
            category=category,
            unit=unit,
            quantity_in_stock=qty,
            reorder_threshold=threshold,
            reorder_quantity=reorder_qty,
            unit_cost_pence=cost,
        )
        db.add(mat)

    db.commit()
    return RedirectResponse(url="/materials", status_code=302)


@router.get("/add", response_class=HTMLResponse)
def materials_add_form(
    request: Request,
    current_user: User = Depends(require_role("admin")),
):
    return templates.TemplateResponse("materials/form.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "material": None,
        "editing": False,
    })


@router.post("/add")
def materials_add_submit(
    item_name: str = Form(...),
    category: str = Form("packing"),
    unit: str = Form("each"),
    quantity_in_stock: int = Form(0),
    reorder_threshold: int = Form(10),
    reorder_quantity: int = Form(50),
    unit_cost: float = Form(0),
    supplier_name: str = Form(""),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    mat = MaterialsInventory(
        company_id=current_user.company_id,
        item_name=item_name.strip(),
        category=category,
        unit=unit,
        quantity_in_stock=quantity_in_stock,
        reorder_threshold=reorder_threshold,
        reorder_quantity=reorder_quantity,
        unit_cost_pence=int(unit_cost * 100),
        supplier_name=supplier_name.strip() if supplier_name else None,
    )
    db.add(mat)
    db.commit()
    return RedirectResponse(url="/materials", status_code=302)


@router.post("/{material_id}/restock")
def materials_restock(
    material_id: str,
    quantity: int = Form(...),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    mat = db.query(MaterialsInventory).filter(
        MaterialsInventory.id == material_id,
        MaterialsInventory.company_id == current_user.company_id,
    ).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    mat.quantity_in_stock += quantity
    mat.last_restock_at = datetime.utcnow()
    mat.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/materials", status_code=302)


@router.post("/{material_id}/use")
def materials_use(
    material_id: str,
    quantity_used: int = Form(...),
    job_assignment_id: str = Form(""),
    notes: str = Form(""),
    current_user: User = Depends(require_role("office")),
    db: Session = Depends(get_db),
):
    mat = db.query(MaterialsInventory).filter(
        MaterialsInventory.id == material_id,
        MaterialsInventory.company_id == current_user.company_id,
    ).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    usage = MaterialsUsage(
        material_id=material_id,
        job_assignment_id=job_assignment_id if job_assignment_id else None,
        quantity_used=quantity_used,
        notes=notes.strip() if notes else None,
    )
    db.add(usage)
    mat.quantity_in_stock = max(0, mat.quantity_in_stock - quantity_used)
    mat.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/materials", status_code=302)


@router.get("/{material_id}/edit", response_class=HTMLResponse)
def materials_edit_form(
    material_id: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    mat = db.query(MaterialsInventory).filter(
        MaterialsInventory.id == material_id,
        MaterialsInventory.company_id == current_user.company_id,
    ).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    return templates.TemplateResponse("materials/form.html", {
        "request": request,
        "user": current_user,
        "company": current_user.company,
        "material": mat,
        "editing": True,
    })


@router.post("/{material_id}/edit")
def materials_edit_submit(
    material_id: str,
    item_name: str = Form(...),
    category: str = Form("packing"),
    unit: str = Form("each"),
    reorder_threshold: int = Form(10),
    reorder_quantity: int = Form(50),
    unit_cost: float = Form(0),
    supplier_name: str = Form(""),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    mat = db.query(MaterialsInventory).filter(
        MaterialsInventory.id == material_id,
        MaterialsInventory.company_id == current_user.company_id,
    ).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    mat.item_name = item_name.strip()
    mat.category = category
    mat.unit = unit
    mat.reorder_threshold = reorder_threshold
    mat.reorder_quantity = reorder_quantity
    mat.unit_cost_pence = int(unit_cost * 100)
    mat.supplier_name = supplier_name.strip() if supplier_name else None
    mat.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/materials", status_code=302)
