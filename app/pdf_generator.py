"""
PrimeHaul Office Manager — PDF Quote Generator.

Generates branded PDF quotes using WeasyPrint (HTML→PDF).
Falls back to basic HTML if WeasyPrint is not installed.
"""

from datetime import datetime, timedelta

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


def generate_quote_pdf(quote, company) -> bytes:
    """Generate a branded PDF quote document. Returns PDF bytes."""
    lines = quote.line_items or []
    brand_color = company.brand_color or "#2ee59d"

    # Build line items HTML
    lines_html = ""
    for line in lines:
        lines_html += f"""
        <tr>
            <td style="padding:8px 12px; border-bottom:1px solid #e5e7eb;">{line.get('description','')}</td>
            <td style="padding:8px 12px; border-bottom:1px solid #e5e7eb; text-align:center;">{line.get('qty','')}</td>
            <td style="padding:8px 12px; border-bottom:1px solid #e5e7eb; text-align:right;">£{line.get('unit_price',0):.2f}</td>
            <td style="padding:8px 12px; border-bottom:1px solid #e5e7eb; text-align:right; font-weight:600;">£{line.get('total',0):.2f}</td>
        </tr>"""

    valid_until = quote.valid_until.strftime('%d %B %Y') if quote.valid_until else (datetime.utcnow() + timedelta(days=30)).strftime('%d %B %Y')
    created = quote.created_at.strftime('%d %B %Y') if quote.created_at else datetime.utcnow().strftime('%d %B %Y')

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4; margin: 20mm; }}
            body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a1a2e; font-size: 11pt; line-height: 1.5; }}
            .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 3px solid {brand_color}; }}
            .company-name {{ font-size: 22pt; font-weight: 700; color: {brand_color}; }}
            .company-details {{ font-size: 9pt; color: #6b7280; text-align: right; line-height: 1.6; }}
            .quote-title {{ font-size: 16pt; font-weight: 700; color: #1a1a2e; margin: 20px 0 5px; }}
            .quote-ref {{ font-size: 10pt; color: #6b7280; }}
            .customer-box {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; margin: 20px 0; }}
            .customer-box h3 {{ margin: 0 0 8px; font-size: 10pt; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }}
            .customer-box p {{ margin: 2px 0; }}
            .details-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
            .detail-box {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }}
            .detail-box h3 {{ margin: 0 0 5px; font-size: 10pt; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            thead th {{ background: #1a1a2e; color: white; padding: 10px 12px; font-size: 10pt; text-align: left; }}
            thead th:nth-child(2) {{ text-align: center; }}
            thead th:nth-child(3), thead th:nth-child(4) {{ text-align: right; }}
            .totals {{ margin-top: 10px; float: right; width: 250px; }}
            .totals-row {{ display: flex; justify-content: space-between; padding: 5px 0; font-size: 11pt; }}
            .totals-row.total {{ border-top: 2px solid {brand_color}; padding-top: 8px; margin-top: 5px; font-size: 14pt; font-weight: 700; color: {brand_color}; }}
            .terms {{ clear: both; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 9pt; color: #6b7280; }}
            .terms h3 {{ color: #1a1a2e; font-size: 10pt; margin-bottom: 8px; }}
            .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #e5e7eb; text-align: center; font-size: 8pt; color: #9ca3af; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <div class="company-name">{company.company_name}</div>
            </div>
            <div class="company-details">
                {company.email or ''}<br>
                {company.phone or ''}<br>
                {company.address or ''}
            </div>
        </div>

        <div class="quote-title">Removal Quote</div>
        <div class="quote-ref">Ref: {quote.quote_ref} &nbsp;|&nbsp; Date: {created} &nbsp;|&nbsp; Valid until: {valid_until}</div>

        <div class="customer-box">
            <h3>Customer</h3>
            <p><strong>{quote.customer_name}</strong></p>
            <p>{quote.customer_email or ''}</p>
            <p>{quote.customer_phone or ''}</p>
        </div>

        <div class="details-grid">
            <div class="detail-box">
                <h3>Collection</h3>
                <p>{quote.pickup_address or ''}</p>
                <p>{quote.pickup_postcode or ''}</p>
            </div>
            <div class="detail-box">
                <h3>Delivery</h3>
                <p>{quote.dropoff_address or ''}</p>
                <p>{quote.dropoff_postcode or ''}</p>
            </div>
        </div>

        {f'<div class="details-grid"><div class="detail-box"><h3>Move Details</h3><p>Volume: {quote.total_cbm or 0} CBM</p><p>Distance: {quote.distance_miles or 0} miles</p><p>Vehicles: {quote.num_vans or 1}</p></div><div class="detail-box"><h3>Service</h3><p>{"Full packing service included" if quote.packing_required else "Customer packing (load & unload only)"}</p><p>Move date: {quote.move_date.strftime("%d %B %Y") if quote.move_date else "To be confirmed"}</p></div></div>'}

        <table>
            <thead>
                <tr>
                    <th>Description</th>
                    <th>Qty</th>
                    <th>Unit Price</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody>
                {lines_html}
            </tbody>
        </table>

        <div class="totals">
            <div class="totals-row"><span>Subtotal</span><span>£{quote.subtotal_pence / 100:.2f}</span></div>
            <div class="totals-row"><span>VAT (20%)</span><span>£{quote.vat_pence / 100:.2f}</span></div>
            <div class="totals-row total"><span>Total</span><span>£{quote.total_pence / 100:.2f}</span></div>
        </div>

        <div class="terms">
            <h3>Terms & Conditions</h3>
            <p>This quote is valid for 30 days from the date of issue. A deposit of 25% is required to confirm your booking.
            The balance is due on completion of the move. Cancellations within 48 hours of the move date may incur charges.
            All goods are covered by our Goods in Transit insurance during the move.
            Additional insurance for high-value items is available on request.</p>
            <p style="margin-top:8px;">Payment methods: Bank transfer, debit/credit card.</p>
        </div>

        <div class="footer">
            {company.company_name} &nbsp;|&nbsp; {company.email or ''} &nbsp;|&nbsp; {company.phone or ''}
        </div>
    </body>
    </html>
    """

    if WEASYPRINT_AVAILABLE:
        return HTML(string=html_content).write_pdf()
    else:
        return html_content.encode("utf-8")
