from pydantic import BaseModel, Field
from typing import List, Optional


class InvoiceRecord(BaseModel):
    invoice_id: str = Field(description="Invoice number or ID. Use 'UNKNOWN' if not found.")
    vendor_name: str = Field(description="Name of the vendor or supplier issuing the invoice.")
    amount: float = Field(description="Total invoice amount as a number. Use 0.0 if not parseable.")
    currency: str = Field(description="Currency code (e.g., INR, USD, EUR). Default to 'INR' if not stated.")
    invoice_date: str = Field(description="Date of invoice. Use 'Unknown' if not found.")
    due_date: str = Field(description="Payment due date. Use 'Unknown' if not found.")
    status: str = Field(description="Payment status: Paid, Unpaid, Overdue, Partial, or Unknown.")
    anomalies: List[str] = Field(description="List of detected anomalies (e.g., 'Missing PO reference', 'Duplicate amount', 'Round number — possible estimate').")
    action_items: List[str] = Field(description="Concrete actionable tasks (e.g., 'Chase vendor for updated invoice', 'Escalate to finance manager — overdue 30+ days').")
    priority: str = Field(description="Priority level: High, Medium, or Low.")
    confidence_score: int = Field(description="Extraction confidence: 95-100 explicit, 70-90 inferred, <70 uncertain.")
    flagged_for_review: bool = Field(description="True if confidence_score < 70 or anomalies detected.")
    uncertainty_note: Optional[str] = Field(
        default=None,
        description="Required if flagged_for_review is True. Explain what was inferred and what evidence is missing."
    )
    source_document: str = Field(description="Filename of the source document this invoice was extracted from.")


class ExtractionResult(BaseModel):
    internal_reasoning: str = Field(
        description="Chain-of-thought: step-by-step logic explaining how invoices were identified, anomalies detected, and action items generated."
    )
    invoices: List[InvoiceRecord]
