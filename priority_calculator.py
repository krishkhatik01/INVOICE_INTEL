"""
Priority calculation logic for invoices based on multiple factors.
"""

def calculate_priority(invoice: dict) -> str:
    """
    Calculate priority level (High, Medium, Low) based on invoice characteristics.
    
    Args:
        invoice: Invoice dictionary with status, amount, anomalies, etc.
        
    Returns:
        Priority level: "High", "Medium", or "Low"
    """
    score = 0
    
    # Status scoring
    status = invoice.get("status", "").lower()
    if status == "overdue":
        score += 40
    elif status == "unpaid":
        score += 25
    elif status == "partial":
        score += 20
    elif status == "paid":
        score += 0
    
    # Flagged for review
    if invoice.get("flagged_for_review", False):
        score += 15
    
    # Anomalies scoring
    anomalies = invoice.get("anomalies", [])
    if anomalies:
        score += len(anomalies) * 8
        
        # Extra points for critical anomalies
        critical_keywords = ["overdue", "missing", "duplicate", "high", "unusual", "discrepancy", "dispute"]
        for anomaly in anomalies:
            for keyword in critical_keywords:
                if keyword.lower() in anomaly.lower():
                    score += 5
    
    # Confidence scoring (lower confidence = higher priority)
    confidence = invoice.get("confidence_score", 100)
    if confidence < 70:
        score += 15
    elif confidence < 85:
        score += 8
    
    # Amount scoring (higher amounts = higher priority)
    amount = invoice.get("amount", 0)
    if amount > 1000000:  # Over 1M
        score += 20
    elif amount > 500000:  # Over 500K
        score += 15
    elif amount > 100000:  # Over 100K
        score += 10
    elif amount > 50000:  # Over 50K
        score += 5
    
    # Determine priority level based on score
    if score >= 60:
        return "High"
    elif score >= 30:
        return "Medium"
    else:
        return "Low"


def recalculate_all_priorities(report: dict) -> dict:
    """
    Recalculate priorities for all invoices in a report.
    
    Args:
        report: Full report dictionary with 'invoices' list
        
    Returns:
        Updated report with recalculated priorities
    """
    if "invoices" not in report:
        return report
    
    invoices = report["invoices"]
    
    # Recalculate each invoice's priority
    for invoice in invoices:
        invoice["priority"] = calculate_priority(invoice)
    
    # Update summary counts
    if "summary" in report:
        high_count = sum(1 for inv in invoices if inv.get("priority") == "High")
        report["summary"]["high_priority"] = high_count
    
    return report
