"""
PrimeHaul Office Manager — PDF Quote Generator.

Uses fpdf2 (pure Python, no system dependencies) to generate
branded A4 PDF quotes.
"""

from datetime import datetime, timedelta
from fpdf import FPDF


class QuotePDF(FPDF):
    def __init__(self, company, brand_color_hex="#2ee59d"):
        super().__init__()
        self.company = company
        # Parse hex color
        h = brand_color_hex.lstrip("#")
        self.brand_r = int(h[0:2], 16)
        self.brand_g = int(h[2:4], 16)
        self.brand_b = int(h[4:6], 16)

    def header(self):
        # Company name
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(self.brand_r, self.brand_g, self.brand_b)
        self.cell(0, 10, self.company.company_name, new_x="LMARGIN", new_y="NEXT")

        # Company details
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        details = []
        if self.company.email:
            details.append(self.company.email)
        if self.company.phone:
            details.append(self.company.phone)
        if details:
            self.cell(0, 4, " | ".join(details), new_x="LMARGIN", new_y="NEXT")

        # Green line
        self.set_draw_color(self.brand_r, self.brand_g, self.brand_b)
        self.set_line_width(0.8)
        self.line(10, self.get_y() + 3, 200, self.get_y() + 3)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(160, 160, 160)
        self.cell(0, 10, f"{self.company.company_name} | {self.company.email or ''} | {self.company.phone or ''}", align="C")


def generate_quote_pdf(quote, company) -> bytes:
    """Generate a branded PDF quote. Returns PDF bytes."""
    brand_color = company.brand_color or "#2ee59d"
    pdf = QuotePDF(company, brand_color)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── TITLE ──
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(30, 30, 50)
    pdf.cell(0, 10, "Removal Quote", new_x="LMARGIN", new_y="NEXT")

    # Ref / Date / Valid
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    valid_until = quote.valid_until.strftime("%d %B %Y") if quote.valid_until else ""
    created = quote.created_at.strftime("%d %B %Y") if quote.created_at else ""
    pdf.cell(0, 5, f"Ref: {quote.quote_ref}  |  Date: {created}  |  Valid until: {valid_until}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ── CUSTOMER BOX ──
    _section_header(pdf, "Customer")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 50)
    pdf.cell(0, 6, quote.customer_name or "", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    if quote.customer_email:
        pdf.cell(0, 5, quote.customer_email, new_x="LMARGIN", new_y="NEXT")
    if quote.customer_phone:
        pdf.cell(0, 5, quote.customer_phone, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ── LOCATIONS ──
    _section_header(pdf, "Move Details")
    y = pdf.get_y()

    # Collection (left)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(95, 4, "COLLECTION", new_x="RIGHT")
    pdf.cell(95, 4, "DELIVERY", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 50)
    pickup = f"{quote.pickup_address or ''}"
    dropoff = f"{quote.dropoff_address or ''}"
    pdf.cell(95, 5, pickup, new_x="RIGHT")
    pdf.cell(95, 5, dropoff, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 10)
    h = company.brand_color or "#2ee59d"
    hr, hg, hb = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    pdf.set_text_color(hr, hg, hb)
    pdf.cell(95, 5, quote.pickup_postcode or "", new_x="RIGHT")
    pdf.cell(95, 5, quote.dropoff_postcode or "", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    details = []
    if quote.total_cbm:
        details.append(f"{quote.total_cbm} CBM")
    if quote.num_vans:
        details.append(f"{quote.num_vans} vehicle(s)")
    if quote.packing_required:
        details.append("Full packing service")
    else:
        details.append("Load & unload only")
    if quote.move_date:
        details.append(f"Move date: {quote.move_date.strftime('%d %B %Y')}")
    pdf.cell(0, 5, " | ".join(details), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ── LINE ITEMS TABLE ──
    _section_header(pdf, "Quotation")

    # Table header
    pdf.set_fill_color(30, 30, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 8, "  Description", fill=True, new_x="RIGHT")
    pdf.cell(20, 8, "Qty", fill=True, align="C", new_x="RIGHT")
    pdf.cell(35, 8, "Unit Price", fill=True, align="R", new_x="RIGHT")
    pdf.cell(40, 8, "Total  ", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    # Table rows
    lines = quote.line_items or []
    pdf.set_font("Helvetica", "", 9)
    for idx, line in enumerate(lines):
        bg = idx % 2 == 0
        if bg:
            pdf.set_fill_color(245, 245, 248)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.set_text_color(30, 30, 50)
        desc = line.get("description", "")
        qty = str(line.get("qty", ""))
        unit_price = line.get("unit_price", 0)
        total = line.get("total", 0)

        pdf.cell(95, 7, f"  {desc}", fill=bg, new_x="RIGHT")
        pdf.cell(20, 7, qty, fill=bg, align="C", new_x="RIGHT")
        pdf.cell(35, 7, f"£{unit_price:.2f}" if unit_price else "", fill=bg, align="R", new_x="RIGHT")
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(40, 7, f"£{total:.2f}  ", fill=bg, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)

    pdf.ln(3)

    # ── TOTALS ──
    x_label = 130
    x_value = 170

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.set_x(x_label)
    pdf.cell(40, 6, "Subtotal", new_x="RIGHT")
    pdf.cell(30, 6, f"£{quote.subtotal_pence / 100:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x_label)
    pdf.cell(40, 6, "VAT (20%)", new_x="RIGHT")
    pdf.cell(30, 6, f"£{quote.vat_pence / 100:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    # Total line
    pdf.set_draw_color(hr, hg, hb)
    pdf.set_line_width(0.5)
    pdf.line(x_label, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(hr, hg, hb)
    pdf.set_x(x_label)
    pdf.cell(40, 8, "Total", new_x="RIGHT")
    pdf.cell(30, 8, f"£{quote.total_pence / 100:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)

    # ── TERMS ──
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 50)
    pdf.cell(0, 5, "Terms & Conditions", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 120, 120)
    terms = (
        "This quote is valid for 30 days from the date of issue. A deposit of 25% is required to confirm your booking. "
        "The balance is due on completion of the move. Cancellations within 48 hours of the move date may incur charges. "
        "All goods are covered by our Goods in Transit insurance during the move. "
        "Additional insurance for high-value items is available on request. "
        "Payment methods: Bank transfer, debit/credit card."
    )
    pdf.multi_cell(0, 4, terms)

    return pdf.output()


def _section_header(pdf, title):
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 50)
    pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.2)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
