import os
import json
import time
import base64
import mimetypes
import logging
from groq import Groq
from pydantic import ValidationError
from models import ExtractionResult
from processor import DocumentProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class InvoiceIntelAgent:
    def __init__(self):
        # Relies on GROQ_API_KEY in your .env file
        self.client = Groq()
        self.text_model = "llama-3.3-70b-versatile"
        # Llama 4 Scout supports both text and image input with JSON mode
        self.vision_model = "meta-llama/llama-4-scout-17b-16e-instruct"

        self.json_schema = """
        {
          "internal_reasoning": "Explain your logic here BEFORE listing invoices.",
          "invoices": [
            {
              "invoice_id": "INV-1001",
              "vendor_name": "Vendor Name",
              "amount": 45000.00,
              "currency": "INR",
              "invoice_date": "2024-05-01",
              "due_date": "2024-05-31",
              "status": "Unpaid | Paid | Overdue | Partial | Unknown",
              "anomalies": ["Missing PO reference", "Duplicate amount detected"],
              "action_items": ["Chase vendor for payment confirmation", "Escalate to finance manager — overdue 30+ days"],
              "priority": "High | Medium | Low",
              "confidence_score": 95,
              "flagged_for_review": false,
              "uncertainty_note": "Explain inference if confidence < 70 or anomaly found",
              "source_document": "filename.csv"
            }
          ]
        }
        """

        self.system_prompt = f"""
        You are an elite Finance Intelligence Agent specializing in invoice analysis.
        Your job is to extract every invoice from the provided document and generate actionable insights.

        CRITICAL RULES:
        1. ZERO HALLUCINATIONS: Do not invent invoices or amounts not present in the document.
        2. ANOMALY DETECTION — flag any of the following:
           - Missing PO (Purchase Order) reference
           - Duplicate invoice ID or duplicate amount from same vendor
           - Round numbers (e.g., exactly 50000) — possible estimates, not final amounts
           - Due date already passed (overdue)
           - Amount unusually high compared to other invoices in the document
           - Missing vendor name, date, or invoice ID
        3. ACTION ITEMS — generate concrete, specific tasks. Examples:
           - "Chase [Vendor] — invoice #X overdue by [N] days"
           - "Flag Invoice #X for duplicate check — same amount as #Y from same vendor"
           - "Request PO reference from [Vendor] before processing payment"
           - "Escalate INV-X to finance manager — amount exceeds threshold"
        4. CONFIDENCE SCORING:
           - 95-100: All fields explicitly stated in document
           - 70-90: Some fields inferred from context
           - Below 70: Key fields missing; highly uncertain
        5. FLAG FOR REVIEW: Set flagged_for_review to true if confidence < 70 OR any anomaly is detected.
        6. OUTPUT FORMAT: Strictly output valid JSON matching this exact schema:
        {self.json_schema}
        """

    def _encode_image(self, image_path: str):
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/png"
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8'), mime_type

    def analyze_document(self, file_path: str) -> dict:
        file_name = os.path.basename(file_path)

        try:
            content = DocumentProcessor.process_file(file_path)
        except Exception as e:
            logger.error(f"Unexpected error processing {file_name}: {e}")
            return {"invoices": []}

        if content.startswith("[ERROR PARSING DOCUMENT]") or content.startswith("Unsupported file type"):
            logger.error(f"Skipping {file_name}: {content}")
            return {"invoices": []}

        is_image = content.startswith("[IMAGE_DATA]:")
        messages = [{"role": "system", "content": self.system_prompt}]

        if is_image:
            image_path = content.split(":", 1)[1].strip()
            try:
                base64_image, mime_type = self._encode_image(image_path)
            except Exception as e:
                logger.error(f"Could not encode image for {file_name}: {e}")
                return {"invoices": []}

            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Extract all invoices and generate action items from this image. Source Document: {file_name}"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                ]
            })
            active_model = self.vision_model
            logger.info(f"Routing {file_name} to Vision Model.")
        else:
            # Cap content length to keep within model context limits
            max_chars = 60000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n...[truncated]"

            messages.append({
                "role": "user",
                "content": f"Source Document Name: {file_name}\n\nDocument Content:\n{content}"
            })
            active_model = self.text_model
            logger.info(f"Routing {file_name} to Text Model.")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )

                raw_json = response.choices[0].message.content

                try:
                    validated_data = ExtractionResult.model_validate_json(raw_json)
                    logger.info(f"Success on {file_name}. Found {len(validated_data.invoices)} invoices.")
                    return validated_data.model_dump()
                except ValidationError as ve:
                    logger.warning(f"Validation failed on {file_name}, attempt {attempt + 1}. Retrying... Error: {ve}")
                    continue

            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    sleep_time = (attempt + 1) * 5
                    logger.warning(f"Rate limited on {file_name}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"API Error on {file_name}: {str(e)}")
                    return {"invoices": []}

        return {"invoices": []}

    def run_analysis(self, directory_path: str, progress_callback=None) -> str:
        """Analyzes every supported file in a directory and returns a JSON report.

        progress_callback (optional): called as progress_callback(index, total, filename)
        before each file is processed, useful for streaming progress to a frontend.
        """
        all_invoices = []
        per_file_results = []

        if not os.path.exists(directory_path):
            return json.dumps({"error": "Directory not found"})

        files = sorted([f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))])
        total = len(files)

        for idx, filename in enumerate(files, start=1):
            if progress_callback:
                try:
                    progress_callback(idx, total, filename)
                except Exception:
                    pass

            file_path = os.path.join(directory_path, filename)
            time.sleep(2)  # Pacing to protect free tier

            result_dict = self.analyze_document(file_path)
            invoices = result_dict.get("invoices", [])
            all_invoices.extend(invoices)
            per_file_results.append({"file": filename, "invoices_found": len(invoices)})

        # Summary stats
        total_invoices = len(all_invoices)
        high_priority = sum(1 for i in all_invoices if i.get("priority") == "High")
        flagged = sum(1 for i in all_invoices if i.get("flagged_for_review"))
        total_amount = sum(i.get("amount", 0) for i in all_invoices)

        status_counts = {}
        for i in all_invoices:
            status = i.get("status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        report = {
            "summary": {
                "total_invoices": total_invoices,
                "high_priority": high_priority,
                "flagged_for_review": flagged,
                "total_amount_extracted": total_amount,
                "status_breakdown": status_counts,
                "files_processed": per_file_results,
            },
            "invoices": all_invoices
        }

        return json.dumps(report, indent=4)
