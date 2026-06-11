# InvoiceIntel Agent

InvoiceIntel is an AI-powered invoice analysis tool. Upload invoices, vendor
emails, statements, or spreadsheets in **any format**, and the agent will:

- Extract every invoice it can find (vendor, amount, dates, status)
- Detect anomalies (duplicates, missing PO references, overdue payments,
  suspiciously round numbers, outlier amounts)
- Generate concrete, prioritized action items for your finance team
- Score its own confidence and flag uncertain extractions for human review
- Render everything in a full analytics dashboard (charts + searchable table)

It uses [Groq](https://console.groq.com/) for fast LLM inference (text +
vision models), so document understanding works even on scanned PDFs and
photographed receipts.

## Supported file types

| Type | Extensions |
|---|---|
| PDFs (text or scanned) | `.pdf` |
| Spreadsheets | `.csv`, `.xlsx`, `.xls` |
| Documents | `.docx`, `.txt`, `.md`, `.markdown` |
| Email | `.eml` |
| Images | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp` |
| Structured data | `.json` |

Scanned PDFs with no extractable text are automatically rendered as images
and routed to the vision model.

## Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and add your Groq API key:

   ```bash
   cp .env.example .env
   # then edit .env and set GROQ_API_KEY=...
   ```

   Get a free API key at https://console.groq.com/keys

## Running the web app

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000 in your browser. From there you can:

1. Drag and drop (or click to select) any combination of supported files
2. Click **Analyze documents** — the backend processes each file and runs
   it through the AI agent
3. Watch the live progress bar as each document is analyzed
4. Get a full dashboard: summary metrics, status/priority charts, top
   vendors by spend, and a searchable/filterable invoice list with
   anomalies, action items, and confidence scores
5. Click **Download report** to save the raw JSON results

Click **Load demo data** on the upload screen to preview the dashboard with
sample data without uploading anything or using API credits.

## Running as a CLI batch job (no web UI)

Drop files into `sample_documents/` and run:

```bash
python main.py
```

This writes the same report format to `invoice_report.json`.

## Project structure

```
agent.py        - Core AI agent: routes documents to text/vision models,
                  validates output against the schema, retries on errors
processor.py    - Local document parsing (PDF, DOCX, CSV, XLSX, EML, images, JSON)
models.py       - Pydantic schema for extracted invoice data
server.py       - FastAPI backend: file upload, async job processing, status polling
main.py         - CLI entrypoint for batch/local runs
static/index.html - Dashboard frontend
demo_report.json  - Sample data for the "Load demo data" button
```

## Deployment notes

- `server.py` keeps job state in memory, which is fine for a single
  instance / demo deployments. For multi-instance production deployments,
  swap the in-memory `JOBS` dict for Redis or a database.
- Each analysis job runs in a background thread; uploaded files are stored
  in a temporary directory and deleted once the job finishes.
- Set `GROQ_API_KEY` as an environment variable in your hosting platform
  (don't commit `.env`).
- For production, run behind a process manager (e.g. `gunicorn -k
  uvicorn.workers.UvicornWorker`) and a reverse proxy (e.g. Nginx).
