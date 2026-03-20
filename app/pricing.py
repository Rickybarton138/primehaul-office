"""
PrimeHaul Office Manager — Job Cost Calculator & Charges Tariff.

Day-rate pricing model matching how UK BAR-standard removal companies actually quote:
- Crew: £X per man per day (calculated from CBM ÷ 15 CBM/man/day)
- Packing: £X per packer per day (calculated from total boxes ÷ 60 boxes/man/day)
- Vehicles: £X per van per day
- Materials: itemised at customer-facing tariff prices
- Distance surcharge: tiered per-mile over local threshold
- Access surcharges: floors, parking, narrow, steps etc.
- VAT: 20%

NO per-CBM volume charge — crew day rate covers loading/unloading.
"""

import math

# ──────────────────────────────────────────────
# Default tariff (editable per-company)
# ──────────────────────────────────────────────

DEFAULT_TARIFF = {
    # Crew & vehicles
    "man_day_rate": 300.00,          # £300 per man per day
    "van_day_rate": 100.00,          # £100 per van per day
    "cbm_per_man_per_day": 15.0,     # loading capacity: 15 CBM per man per day (local)
    "min_crew": 2,                   # minimum crew on move day

    # Packing
    "packer_day_rate": 300.00,       # £300 per packer per day (same as crew rate)
    "max_boxes_per_packer": 60,      # max boxes one packer can do in a day
    "overnight_reserve_boxes": 12,   # boxes customer needs overnight (bedding, clothes, wash kit, plates)

    # Distance surcharge (fuel/wear & tear)
    "local_miles_included": 15,      # no surcharge within this radius
    "distance_tier_1_max": 50,       # 15-50 miles
    "distance_tier_1_rate": 1.50,    # £/mile
    "distance_tier_2_max": 100,      # 50-100 miles
    "distance_tier_2_rate": 2.00,
    "distance_tier_3_max": 200,      # 100-200 miles
    "distance_tier_3_rate": 2.50,
    "distance_tier_4_rate": 3.00,    # 200+ miles

    # Access surcharges (per location)
    "price_per_floor": 15.00,
    "no_lift_surcharge": 50.00,
    "parking_driveway": 0.00,
    "parking_street": 25.00,
    "parking_permit": 40.00,
    "parking_limited": 60.00,
    "parking_distance_per_50m": 10.00,
    "narrow_access_fee": 35.00,
    "time_restriction_fee": 25.00,
    "booking_required_fee": 20.00,
    "outdoor_steps_per_5": 15.00,
    "outdoor_path_fee": 20.00,

    # Packing materials (customer-facing prices)
    "small_box": 3.00,
    "medium_box": 4.00,
    "large_box": 5.00,
    "wardrobe_box": 16.00,
    "packing_paper": 12.50,          # per pack
    "tape_roll": 2.50,               # per roll
    "king_mattress_bag": 8.00,
    "single_mattress_bag": 5.00,

    # VAT
    "vat_rate": 0.20,
}


def get_company_tariff(company, db) -> dict:
    """Get the company's tariff, falling back to defaults."""
    tariff = DEFAULT_TARIFF.copy()
    if hasattr(company, "pricing_tariff") and company.pricing_tariff:
        tariff.update(company.pricing_tariff)
    return tariff


def calculate_access_cost(access_data: dict, tariff: dict) -> float:
    """Calculate access difficulty surcharges for one location."""
    if not access_data:
        return 0.0

    cost = 0.0
    floors = int(access_data.get("floors", 0) or 0)
    cost += floors * tariff["price_per_floor"]

    if floors > 0 and not access_data.get("has_lift", False):
        cost += tariff["no_lift_surcharge"]

    parking = access_data.get("parking_type", "driveway")
    cost += tariff.get(f"parking_{parking}", 0)

    parking_distance = int(access_data.get("parking_distance_m", 0) or 0)
    if parking_distance > 0:
        cost += max(1, parking_distance // 50) * tariff["parking_distance_per_50m"]

    if access_data.get("narrow_access"):
        cost += tariff["narrow_access_fee"]
    if access_data.get("time_restriction"):
        cost += tariff["time_restriction_fee"]
    if access_data.get("booking_required"):
        cost += tariff["booking_required_fee"]

    outdoor_steps = int(access_data.get("outdoor_steps", 0) or 0)
    if outdoor_steps > 0:
        cost += (outdoor_steps // 5 + (1 if outdoor_steps % 5 else 0)) * tariff["outdoor_steps_per_5"]

    if access_data.get("outdoor_path"):
        cost += tariff["outdoor_path_fee"]

    return cost


def calculate_distance_surcharge(distance_miles: float, tariff: dict) -> tuple[float, dict]:
    """Calculate tiered distance/fuel surcharge for longer moves."""
    local = tariff["local_miles_included"]
    if distance_miles <= local:
        return 0.0, {"chargeable_miles": 0, "tier": "local", "surcharge": 0}

    remaining = distance_miles - local
    cost = 0.0
    tier_breakdown = []

    # Tier 1
    t1_max = tariff["distance_tier_1_max"] - local
    t1_miles = min(remaining, t1_max)
    if t1_miles > 0:
        t1_cost = t1_miles * tariff["distance_tier_1_rate"]
        cost += t1_cost
        tier_breakdown.append({"miles": round(t1_miles, 1), "rate": tariff["distance_tier_1_rate"], "cost": round(t1_cost, 2)})
        remaining -= t1_miles

    # Tier 2
    t2_max = tariff["distance_tier_2_max"] - tariff["distance_tier_1_max"]
    t2_miles = min(remaining, t2_max)
    if t2_miles > 0:
        t2_cost = t2_miles * tariff["distance_tier_2_rate"]
        cost += t2_cost
        tier_breakdown.append({"miles": round(t2_miles, 1), "rate": tariff["distance_tier_2_rate"], "cost": round(t2_cost, 2)})
        remaining -= t2_miles

    # Tier 3
    t3_max = tariff["distance_tier_3_max"] - tariff["distance_tier_2_max"]
    t3_miles = min(remaining, t3_max)
    if t3_miles > 0:
        t3_cost = t3_miles * tariff["distance_tier_3_rate"]
        cost += t3_cost
        tier_breakdown.append({"miles": round(t3_miles, 1), "rate": tariff["distance_tier_3_rate"], "cost": round(t3_cost, 2)})
        remaining -= t3_miles

    # Tier 4 (200+)
    if remaining > 0:
        t4_cost = remaining * tariff["distance_tier_4_rate"]
        cost += t4_cost
        tier_breakdown.append({"miles": round(remaining, 1), "rate": tariff["distance_tier_4_rate"], "cost": round(t4_cost, 2)})

    return cost, {
        "chargeable_miles": round(distance_miles - local, 1),
        "tiers": tier_breakdown,
        "surcharge": round(cost, 2),
    }


def calculate_job_cost(
    total_cbm: float = 0,
    distance_miles: float = 0,
    num_vans: int = 1,
    # Packing
    packing_required: bool = False,
    materials: dict = None,
    # Access
    pickup_access: dict = None,
    dropoff_access: dict = None,
    # Overrides
    crew_override: int = 0,
    packer_override: int = 0,
    tariff: dict = None,
) -> dict:
    """
    Calculate full job cost using day-rate model.

    Crew size auto-calculated from CBM ÷ 15 CBM/man/day.
    Packer count auto-calculated from total boxes ÷ 60 boxes/man/day.
    All amounts in GBP (not pence).
    """
    if tariff is None:
        tariff = DEFAULT_TARIFF.copy()
    if materials is None:
        materials = {}

    # ── MOVE DAY CREW ──
    cbm_per_man = tariff["cbm_per_man_per_day"]
    auto_crew = max(tariff["min_crew"], math.ceil(total_cbm / cbm_per_man)) if total_cbm > 0 else tariff["min_crew"]
    crew_count = crew_override if crew_override > 0 else auto_crew
    crew_cost = crew_count * tariff["man_day_rate"]

    # ── VEHICLES ──
    vehicle_count = max(1, num_vans)
    vehicle_cost = vehicle_count * tariff["van_day_rate"]

    # ── PRE-PACK DAY ──
    packer_count = 0
    packing_labour_cost = 0.0
    pack_detail = {}
    if packing_required:
        total_boxes = sum(
            materials.get(k, 0) for k in ["small_box", "medium_box", "large_box"]
        )
        # Subtract overnight reserve — these get done on move morning by crew
        packable_day_before = max(0, total_boxes - tariff["overnight_reserve_boxes"])
        auto_packers = max(1, math.ceil(packable_day_before / tariff["max_boxes_per_packer"])) if packable_day_before > 0 else 1
        packer_count = packer_override if packer_override > 0 else auto_packers
        packing_labour_cost = packer_count * tariff["packer_day_rate"]

        pack_detail = {
            "total_boxes": total_boxes,
            "overnight_reserve": tariff["overnight_reserve_boxes"],
            "packable_day_before": packable_day_before,
            "packers_needed": packer_count,
            "rate_per_packer": tariff["packer_day_rate"],
        }

    # ── MATERIALS ──
    materials_cost = 0.0
    materials_breakdown = {}
    material_keys = [
        "small_box", "medium_box", "large_box", "wardrobe_box",
        "packing_paper", "tape_roll", "king_mattress_bag", "single_mattress_bag",
    ]
    for key in material_keys:
        qty = materials.get(key, 0)
        if qty and key in tariff:
            line_cost = qty * tariff[key]
            materials_cost += line_cost
            materials_breakdown[key] = {
                "qty": qty,
                "unit_price": tariff[key],
                "total": round(line_cost, 2),
            }

    # ── DISTANCE SURCHARGE ──
    distance_cost, distance_detail = calculate_distance_surcharge(distance_miles, tariff)

    # ── ACCESS SURCHARGES ──
    pickup_access_cost = calculate_access_cost(pickup_access or {}, tariff)
    dropoff_access_cost = calculate_access_cost(dropoff_access or {}, tariff)
    access_cost = pickup_access_cost + dropoff_access_cost

    # ── TOTALS ──
    subtotal = crew_cost + vehicle_cost + packing_labour_cost + materials_cost + distance_cost + access_cost
    vat = subtotal * tariff["vat_rate"]
    total = subtotal + vat

    return {
        "total": round(total, 2),
        "total_pence": int(round(total * 100)),
        "subtotal": round(subtotal, 2),
        "vat": round(vat, 2),
        "breakdown": {
            # Move day
            "crew_count": crew_count,
            "crew_rate": tariff["man_day_rate"],
            "crew_cost": round(crew_cost, 2),
            "cbm": total_cbm,
            "cbm_per_man": cbm_per_man,

            # Vehicles
            "vehicle_count": vehicle_count,
            "vehicle_rate": tariff["van_day_rate"],
            "vehicle_cost": round(vehicle_cost, 2),

            # Packing
            "packing_required": packing_required,
            "packing_labour_cost": round(packing_labour_cost, 2),
            "packing_detail": pack_detail,

            # Materials
            "materials_cost": round(materials_cost, 2),
            "materials_breakdown": materials_breakdown,

            # Distance
            "distance_miles": distance_miles,
            "distance_cost": round(distance_cost, 2),
            "distance_detail": distance_detail,

            # Access
            "pickup_access_cost": round(pickup_access_cost, 2),
            "dropoff_access_cost": round(dropoff_access_cost, 2),
            "access_cost": round(access_cost, 2),

            # Totals
            "subtotal": round(subtotal, 2),
            "vat": round(vat, 2),
            "vat_rate": tariff["vat_rate"],
            "total": round(total, 2),
        },
    }
