"""
PrimeHaul Office Manager — Job Cost Calculator & Charges Tariff.

Unified pricing engine for quoting removal jobs manually.
Based on proven formulas from PrimeHaul OS + Survey, with labour + VAT.
All rates are editable per-company via the tariff settings page.
"""

# ──────────────────────────────────────────────
# Default tariff (UK averages — company can override)
# ──────────────────────────────────────────────

DEFAULT_TARIFF = {
    # Base
    "base_fee": 250.00,
    "price_per_cbm": 35.00,

    # Item surcharges
    "bulky_item_fee": 25.00,
    "fragile_item_fee": 15.00,

    # Weight
    "weight_threshold_kg": 1000,
    "price_per_kg_over": 0.50,

    # Distance
    "free_miles": 10,
    "price_per_mile": 1.50,

    # Access - Floors
    "price_per_floor": 15.00,
    "no_lift_surcharge": 50.00,

    # Access - Parking
    "parking_driveway": 0.00,
    "parking_street": 25.00,
    "parking_permit": 40.00,
    "parking_limited": 60.00,
    "parking_distance_per_50m": 10.00,

    # Access - Building
    "narrow_access_fee": 35.00,
    "time_restriction_fee": 25.00,
    "booking_required_fee": 20.00,

    # Access - Outdoor
    "outdoor_steps_per_5": 15.00,
    "outdoor_path_fee": 20.00,

    # Labour
    "labour_rate_per_hour": 25.00,  # per person
    "min_crew": 2,
    "cbm_per_hour": 5.0,  # loading speed
    "min_labour_hours": 2.0,

    # Packing materials
    "small_box": 3.00,
    "medium_box": 4.00,
    "large_box": 5.00,
    "wardrobe_box": 12.00,
    "mattress_cover": 8.00,
    "packing_labour_per_hour": 40.00,

    # VAT
    "vat_rate": 0.20,

    # Estimate range
    "low_multiplier": 0.90,
    "high_multiplier": 1.15,
}


def get_company_tariff(company, db) -> dict:
    """Get the company's tariff, falling back to defaults."""
    from app.models import Company
    tariff = DEFAULT_TARIFF.copy()

    # If company has custom tariff stored in JSON
    if hasattr(company, "pricing_tariff") and company.pricing_tariff:
        tariff.update(company.pricing_tariff)

    return tariff


def calculate_access_cost(access_data: dict, tariff: dict) -> float:
    """Calculate access difficulty surcharges."""
    if not access_data:
        return 0.0

    cost = 0.0
    floors = int(access_data.get("floors", 0) or 0)
    cost += floors * tariff["price_per_floor"]

    if floors > 0 and not access_data.get("has_lift", False):
        cost += tariff["no_lift_surcharge"]

    parking = access_data.get("parking_type", "driveway")
    parking_key = f"parking_{parking}"
    cost += tariff.get(parking_key, 0)

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


def calculate_labour_cost(total_cbm: float, distance_miles: float, tariff: dict) -> tuple[float, dict]:
    """Calculate labour cost based on volume, distance, and crew."""
    loading_hours = max(tariff["min_labour_hours"], total_cbm / tariff["cbm_per_hour"])
    travel_hours = (distance_miles / 30) if distance_miles else 0
    unloading_hours = loading_hours * 0.8
    total_hours = loading_hours + travel_hours + unloading_hours
    crew_size = tariff["min_crew"] if total_cbm < 30 else 3

    cost = total_hours * tariff["labour_rate_per_hour"] * crew_size

    return cost, {
        "loading_hours": round(loading_hours, 1),
        "travel_hours": round(travel_hours, 1),
        "unloading_hours": round(unloading_hours, 1),
        "total_hours": round(total_hours, 1),
        "crew_size": crew_size,
        "rate_per_hour": tariff["labour_rate_per_hour"],
    }


def calculate_job_cost(
    total_cbm: float = 0,
    total_weight_kg: float = 0,
    bulky_items: int = 0,
    fragile_items: int = 0,
    distance_miles: float = 0,
    pickup_access: dict = None,
    dropoff_access: dict = None,
    packing_boxes: dict = None,
    packing_service_hours: float = 0,
    tariff: dict = None,
) -> dict:
    """
    Calculate full job cost with breakdown.

    Returns dict with estimate_low, estimate_high, and detailed breakdown.
    All amounts in GBP (not pence).
    """
    if tariff is None:
        tariff = DEFAULT_TARIFF.copy()

    # Base fee
    base = tariff["base_fee"]

    # Volume
    cbm_cost = total_cbm * tariff["price_per_cbm"]

    # Item surcharges
    bulky_cost = bulky_items * tariff["bulky_item_fee"]
    fragile_cost = fragile_items * tariff["fragile_item_fee"]

    # Weight overage
    weight_cost = 0.0
    if total_weight_kg > tariff["weight_threshold_kg"]:
        weight_cost = (total_weight_kg - tariff["weight_threshold_kg"]) * tariff["price_per_kg_over"]

    # Distance
    distance_cost = 0.0
    if distance_miles > tariff["free_miles"]:
        distance_cost = (distance_miles - tariff["free_miles"]) * tariff["price_per_mile"]

    # Access surcharges
    pickup_access_cost = calculate_access_cost(pickup_access or {}, tariff)
    dropoff_access_cost = calculate_access_cost(dropoff_access or {}, tariff)
    access_cost = pickup_access_cost + dropoff_access_cost

    # Labour
    labour_cost, labour_detail = calculate_labour_cost(total_cbm, distance_miles, tariff)

    # Packing materials
    packing_material_cost = 0.0
    packing_detail = {}
    if packing_boxes:
        for box_type, qty in packing_boxes.items():
            if qty and box_type in tariff:
                packing_material_cost += qty * tariff[box_type]
                packing_detail[box_type] = {"qty": qty, "unit_cost": tariff[box_type], "total": qty * tariff[box_type]}

    # Packing service labour
    packing_labour_cost = packing_service_hours * tariff["packing_labour_per_hour"]

    # Subtotal (before VAT)
    subtotal = (
        base + cbm_cost + bulky_cost + fragile_cost + weight_cost
        + distance_cost + access_cost + labour_cost
        + packing_material_cost + packing_labour_cost
    )

    # VAT
    vat = subtotal * tariff["vat_rate"]
    total = subtotal + vat

    # Estimate range
    estimate_low = max(150, round(total * tariff["low_multiplier"], 2))
    estimate_high = round(total * tariff["high_multiplier"], 2)

    return {
        "estimate_low": estimate_low,
        "estimate_high": estimate_high,
        "estimate_low_pence": int(estimate_low * 100),
        "estimate_high_pence": int(estimate_high * 100),
        "breakdown": {
            "base_fee": base,
            "cbm_cost": round(cbm_cost, 2),
            "bulky_surcharge": round(bulky_cost, 2),
            "fragile_surcharge": round(fragile_cost, 2),
            "weight_surcharge": round(weight_cost, 2),
            "distance_cost": round(distance_cost, 2),
            "pickup_access_cost": round(pickup_access_cost, 2),
            "dropoff_access_cost": round(dropoff_access_cost, 2),
            "access_cost_total": round(access_cost, 2),
            "labour_cost": round(labour_cost, 2),
            "labour_detail": labour_detail,
            "packing_material_cost": round(packing_material_cost, 2),
            "packing_detail": packing_detail,
            "packing_labour_cost": round(packing_labour_cost, 2),
            "subtotal": round(subtotal, 2),
            "vat": round(vat, 2),
            "vat_rate": tariff["vat_rate"],
            "total": round(total, 2),
        },
    }
