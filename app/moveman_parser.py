"""
PrimeHaul Office Manager — MoveMan Survey Parser.

Parses MoveMan survey text (copy-pasted or from email) and extracts
structured data for auto-populating quotes.

MoveMan format: tab-separated, room-by-room inventory with headers,
item rows, room totals, and survey totals.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MoveManItem:
    room: str
    name: str
    qty: int
    volume_ft3: float
    volume_m3: float
    weight_lbs: float
    weight_kg: float
    value: float
    condition: str
    service: str  # "Full Pack", "Packed by mover", "Not Packed", ""


@dataclass
class MoveManSurvey:
    # Header
    survey_date: str = ""
    surveyor: str = ""
    client_name: str = ""
    address_from: str = ""
    postcode_from: str = ""
    address_to: str = ""
    postcode_to: str = ""
    telephone: str = ""
    mobile: str = ""
    email: str = ""

    # Totals
    total_volume_ft3: float = 0
    total_volume_m3: float = 0
    total_weight_lbs: float = 0
    total_weight_kg: float = 0
    total_value: float = 0
    total_items: int = 0

    # Rooms & items
    rooms: dict = field(default_factory=dict)  # room_name -> list[MoveManItem]
    items: list = field(default_factory=list)

    # Notes
    notes: str = ""

    # Derived
    packing_required: bool = False
    carton_counts: dict = field(default_factory=dict)


def parse_moveman_survey(text: str) -> MoveManSurvey:
    """Parse MoveMan survey text into structured data."""
    survey = MoveManSurvey()
    lines = text.strip().split("\n")

    current_room = ""
    in_item_table = False
    carton_counts = {
        "pack_1": 0, "pack_2": 0, "pack_3": 0,
        "carton_clothes": 0, "carton_books": 0,
        "carton_odds": 0, "carton_gc": 0,
        "wardrobe_cartons": 0,
    }

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # ── HEADER FIELDS ──
        if line.startswith("Survey date"):
            survey.survey_date = _extract_tab_value(line)
        elif line.startswith("Surveyor"):
            survey.surveyor = _extract_tab_value(line)
        elif line.startswith("Client name"):
            survey.client_name = _extract_tab_value(line)
        elif line.startswith("Mobile"):
            survey.mobile = _extract_first_tab_value(line)
        elif line.startswith("Telephone"):
            survey.telephone = _extract_first_tab_value(line)
        elif line.startswith("Email"):
            survey.email = _extract_first_tab_value(line)

        # ── ADDRESSES ──
        # Address lines come in pairs (from | to) after "Address from    Address to"
        elif line.startswith("Address from"):
            # Next few lines are address pairs
            addr_from_lines = []
            addr_to_lines = []
            for j in range(i + 1, min(i + 5, len(lines))):
                addr_line = lines[j].strip()
                if not addr_line or addr_line.startswith("Telephone") or addr_line.startswith("Mobile"):
                    break
                parts = addr_line.split("\t")
                if len(parts) >= 2:
                    addr_from_lines.append(parts[0].strip())
                    addr_to_lines.append(parts[1].strip())
                elif len(parts) == 1:
                    addr_from_lines.append(parts[0].strip())

            survey.address_from = ", ".join(f for f in addr_from_lines if f)
            survey.address_to = ", ".join(t for t in addr_to_lines if t)

            # Extract postcodes (last line of address is usually postcode)
            for a in addr_from_lines:
                pc = _extract_postcode(a)
                if pc:
                    survey.postcode_from = pc
            for a in addr_to_lines:
                pc = _extract_postcode(a)
                if pc:
                    survey.postcode_to = pc

        # ── ROOM HEADERS ──
        # A room header is a line that doesn't match known patterns and is followed by "Volume    Weight"
        elif i + 1 < len(lines) and "Volume" in lines[i + 1] and "Weight" in lines[i + 1]:
            current_room = line.strip()
            if current_room not in survey.rooms:
                survey.rooms[current_room] = []
            in_item_table = False

        # ── ITEM TABLE HEADER ──
        elif line.startswith("Item") and "No" in line and "ft" in line:
            in_item_table = True
            continue

        # ── ROOM TOTALS ──
        elif "items in" in line.lower():
            in_item_table = False
            continue

        # ── SURVEY TOTALS ──
        elif line.startswith("Survey totals"):
            parts = line.split("\t")
            nums = [_parse_float(p) for p in parts[1:]]
            if len(nums) >= 4:
                survey.total_volume_ft3 = nums[0]
                survey.total_volume_m3 = nums[1]
                survey.total_weight_lbs = nums[2]
                survey.total_weight_kg = nums[3]
            if len(nums) >= 5:
                survey.total_value = nums[4]

        # ── NOTES ──
        elif line == "Notes":
            # Everything after "Notes" until end is notes
            remaining = "\n".join(lines[i + 1:]).strip()
            survey.notes = remaining
            break

        # ── ITEM ROWS ──
        elif in_item_table and current_room:
            item = _parse_item_row(line, current_room)
            if item:
                survey.items.append(item)
                survey.rooms[current_room].append(item)
                survey.total_items += item.qty

                # Track carton types
                name_lower = item.name.lower()
                if "pack 1" in name_lower:
                    carton_counts["pack_1"] += item.qty
                elif "pack 2" in name_lower:
                    carton_counts["pack_2"] += item.qty
                elif "pack 3" in name_lower:
                    carton_counts["pack_3"] += item.qty
                elif "carton clothes" in name_lower:
                    carton_counts["carton_clothes"] += item.qty
                elif "carton books" in name_lower or "carton book" in name_lower:
                    carton_counts["carton_books"] += item.qty
                elif "carton odds" in name_lower:
                    carton_counts["carton_odds"] += item.qty
                elif "carton g & c" in name_lower or "carton g&c" in name_lower:
                    carton_counts["carton_gc"] += item.qty
                elif "wardrobe carton" in name_lower:
                    carton_counts["wardrobe_cartons"] += item.qty

                # Check if packing service needed
                if item.service and "pack" in item.service.lower() and "not packed" not in item.service.lower():
                    survey.packing_required = True

    survey.carton_counts = carton_counts
    return survey


def _extract_tab_value(line: str) -> str:
    parts = line.split("\t")
    return parts[1].strip() if len(parts) > 1 else ""


def _extract_first_tab_value(line: str) -> str:
    parts = line.split("\t")
    return parts[1].strip() if len(parts) > 1 else ""


def _extract_postcode(text: str) -> Optional[str]:
    match = re.search(r"[A-Z]{1,2}\s?\d{1,2}\s?\d[A-Z]{2}", text.upper().replace(".", ""))
    return match.group(0) if match else None


def _parse_float(s: str) -> float:
    try:
        return float(s.strip().replace(",", "").replace("£", ""))
    except (ValueError, AttributeError):
        return 0.0


def _parse_item_row(line: str, room: str) -> Optional[MoveManItem]:
    """Parse a tab-separated item row."""
    parts = line.split("\t")
    if len(parts) < 6:
        return None

    name = parts[0].strip()
    if not name or name.lower() in ("item", ""):
        return None

    try:
        qty = int(_parse_float(parts[1]))
        vol_ft3 = _parse_float(parts[2])
        vol_m3 = _parse_float(parts[3])
        wt_lbs = _parse_float(parts[4])
        wt_kg = _parse_float(parts[5])
        value = _parse_float(parts[6]) if len(parts) > 6 else 0
        condition = parts[7].strip() if len(parts) > 7 else ""
        mode = parts[8].strip() if len(parts) > 8 else ""
        service = parts[9].strip() if len(parts) > 9 else ""
    except (ValueError, IndexError):
        return None

    if qty == 0:
        return None

    return MoveManItem(
        room=room,
        name=name,
        qty=qty,
        volume_ft3=vol_ft3,
        volume_m3=vol_m3,
        weight_lbs=wt_lbs,
        weight_kg=wt_kg,
        value=value,
        condition=condition,
        service=service,
    )


def survey_to_quote_lines(survey: MoveManSurvey, tariff: dict) -> list[dict]:
    """Convert a parsed MoveMan survey into quote line items using company tariff."""
    lines = []
    cbm = survey.total_volume_m3

    # ── CREW ──
    cbm_per_man = tariff.get("cbm_per_man_per_day", 15)
    min_crew = tariff.get("min_crew", 2)
    import math
    crew = max(min_crew, math.ceil(cbm / cbm_per_man)) if cbm > 0 else min_crew
    man_rate = tariff.get("man_day_rate", 300)
    lines.append({
        "description": f"Move day crew ({crew} men)",
        "qty": crew,
        "unit_price": man_rate,
        "total": crew * man_rate,
    })

    # ── VEHICLES ──
    # Estimate vans from CBM (one 3.5t Luton ≈ 15-18 CBM capacity)
    vans = max(1, math.ceil(cbm / 17))
    van_rate = tariff.get("van_day_rate", 100)
    lines.append({
        "description": f"Vehicles ({vans} x Luton)",
        "qty": vans,
        "unit_price": van_rate,
        "total": vans * van_rate,
    })

    # ── PRE-PACK ──
    if survey.packing_required:
        cc = survey.carton_counts
        total_boxes = cc.get("pack_1", 0) + cc.get("pack_2", 0) + cc.get("pack_3", 0) + \
                      cc.get("carton_books", 0) + cc.get("carton_odds", 0) + cc.get("carton_gc", 0)
        max_per_packer = tariff.get("max_boxes_per_packer", 60)
        overnight = tariff.get("overnight_reserve_boxes", 12)
        packable = max(0, total_boxes - overnight)
        packers = max(1, math.ceil(packable / max_per_packer)) if packable > 0 else 1
        packer_rate = tariff.get("packer_day_rate", 300)
        lines.append({
            "description": f"Pre-pack day ({packers} packer{'s' if packers > 1 else ''})",
            "qty": packers,
            "unit_price": packer_rate,
            "total": packers * packer_rate,
        })

    # ── MATERIALS ──
    cc = survey.carton_counts

    # Small boxes (Pack 1 + Pack 2)
    small_qty = cc.get("pack_1", 0) + cc.get("pack_2", 0)
    if small_qty > 0:
        price = tariff.get("small_box", 3.0)
        lines.append({"description": "Small boxes", "qty": small_qty, "unit_price": price, "total": small_qty * price})

    # Large boxes (Pack 3 + Carton Books + Carton Odds + Carton G&C)
    large_qty = cc.get("pack_3", 0) + cc.get("carton_books", 0) + cc.get("carton_odds", 0) + cc.get("carton_gc", 0)
    if large_qty > 0:
        price = tariff.get("large_box", 5.0)
        lines.append({"description": "Large boxes", "qty": large_qty, "unit_price": price, "total": large_qty * price})

    # Wardrobe cartons
    wardrobe_qty = cc.get("wardrobe_cartons", 0)
    if wardrobe_qty > 0:
        price = tariff.get("wardrobe_box", 16.0)
        lines.append({"description": "Wardrobe cartons", "qty": wardrobe_qty, "unit_price": price, "total": wardrobe_qty * price})

    # Clothes cartons (customer-packed, no charge — but list for info)
    clothes_qty = cc.get("carton_clothes", 0)
    if clothes_qty > 0:
        lines.append({"description": f"Clothes cartons (customer-packed)", "qty": clothes_qty, "unit_price": 0, "total": 0})

    # Estimate packing paper + tape from total boxes
    total_boxes_packed = small_qty + large_qty
    if total_boxes_packed > 0:
        paper_packs = max(1, math.ceil(total_boxes_packed / 15))
        paper_price = tariff.get("packing_paper", 12.50)
        lines.append({"description": "Packing paper", "qty": paper_packs, "unit_price": paper_price, "total": paper_packs * paper_price})

        tape_rolls = max(1, math.ceil(total_boxes_packed / 20))
        tape_price = tariff.get("tape_roll", 2.50)
        lines.append({"description": "Tape rolls", "qty": tape_rolls, "unit_price": tape_price, "total": tape_rolls * tape_price})

    return lines
