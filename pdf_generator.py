"""
PDF generation utilities for converting JSON invoice reports to PDF format.
"""

import io
from datetime import datetime
from typing import Dict, Any
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, 
    KeepTogether, PageTemplate, Frame, Image
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def generate_pdf_from_json(report_data: Dict[str, Any]) -> bytes:
    """
    Convert invoice report JSON to a professional PDF.
    
    Args:
        report_data: Dictionary containing invoice report with 'summary' and 'invoices' keys
        
    Returns:
        PDF content as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold',
        borderColor=colors.HexColor('#e0e0e0'),
        borderWidth=0,
        borderPadding=6
    )
    
    # Title
    story.append(Paragraph("📋 Invoice Intelligence Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    story.append(Spacer(1, 0.3 * inch))
    
    # Summary Section
    summary = report_data.get("summary", {})
    if summary:
        story.append(Paragraph("Executive Summary", heading_style))
        
        summary_data = [
            ["Metric", "Value"],
            ["Total Invoices", str(summary.get("total_invoices", 0))],
            ["High Priority", str(summary.get("high_priority", 0))],
            ["Flagged for Review", str(summary.get("flagged_for_review", 0))],
            ["Total Amount Extracted", f"${summary.get('total_amount_extracted', 0):,.2f}"],
        ]
        
        status_breakdown = summary.get("status_breakdown", {})
        for status, count in status_breakdown.items():
            summary_data.append([f"{status}", str(count)])
        
        summary_table = Table(summary_data, colWidths=[2.5 * inch, 2.5 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.2 * inch))
        
        # Files Processed
        files_processed = summary.get("files_processed", [])
        if files_processed:
            story.append(Paragraph("Files Processed", heading_style))
            files_data = [["File Name", "Invoices Found"]]
            for file_info in files_processed:
                files_data.append([
                    file_info.get("file", ""),
                    str(file_info.get("invoices_found", 0))
                ])
            
            files_table = Table(files_data, colWidths=[3.5 * inch, 1.5 * inch])
            files_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(files_table)
            story.append(Spacer(1, 0.3 * inch))
    
    # Detailed Invoices Section
    invoices = report_data.get("invoices", [])
    if invoices:
        story.append(PageBreak())
        story.append(Paragraph("Detailed Invoice Analysis", heading_style))
        
        for idx, invoice in enumerate(invoices, 1):
            # Invoice header with status color
            status = invoice.get("status", "Unknown")
            status_color = {
                "Overdue": colors.HexColor('#d32f2f'),
                "Unpaid": colors.HexColor('#f57c00'),
                "Paid": colors.HexColor('#388e3c'),
                "Partial": colors.HexColor('#fbc02d'),
            }.get(status, colors.grey)
            
            # Invoice details table
            invoice_details = [
                ["Invoice ID", invoice.get("invoice_id", "N/A"), "Vendor", invoice.get("vendor_name", "N/A")],
                ["Amount", f"{invoice.get('currency', 'USD')} {invoice.get('amount', 0):,.2f}", "Status", status],
                ["Invoice Date", invoice.get("invoice_date", "N/A"), "Due Date", invoice.get("due_date", "N/A")],
                ["Priority", invoice.get("priority", "N/A"), "Confidence", f"{invoice.get('confidence_score', 0)}%"],
            ]
            
            invoice_table = Table(invoice_details, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
            invoice_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (1, 0), (1, -1), status_color),
                ('TEXTCOLOR', (1, 0), (1, -1), colors.white),
            ]))
            
            story.append(invoice_table)
            story.append(Spacer(1, 0.1 * inch))
            
            # Anomalies
            anomalies = invoice.get("anomalies", [])
            if anomalies:
                anomaly_text = "<b>⚠️ Anomalies:</b> " + "; ".join(anomalies)
                story.append(Paragraph(anomaly_text, styles['Normal']))
                story.append(Spacer(1, 0.05 * inch))
            
            # Action Items
            action_items = invoice.get("action_items", [])
            if action_items:
                action_text = "<b>✓ Action Items:</b><br/>"
                for item in action_items:
                    action_text += f"• {item}<br/>"
                story.append(Paragraph(action_text, styles['Normal']))
                story.append(Spacer(1, 0.05 * inch))
            
            # Uncertainty note
            uncertainty_note = invoice.get("uncertainty_note", "")
            if uncertainty_note:
                note_style = ParagraphStyle(
                    'Note',
                    parent=styles['Normal'],
                    fontSize=8,
                    textColor=colors.HexColor('#666666'),
                    leftIndent=12,
                    borderColor=colors.HexColor('#ffebee'),
                    borderWidth=1,
                    borderPadding=6,
                    backColor=colors.HexColor('#fff5f5'),
                )
                story.append(Paragraph(f"<i>📝 Note: {uncertainty_note}</i>", note_style))
            
            story.append(Spacer(1, 0.2 * inch))
            
            # Page break after every 3 invoices
            if idx % 3 == 0 and idx < len(invoices):
                story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
