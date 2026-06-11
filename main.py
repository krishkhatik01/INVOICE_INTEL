import os
from dotenv import load_dotenv
from agent import InvoiceIntelAgent


def main():
    load_dotenv()

    if not os.environ.get("GROQ_API_KEY"):
        print("CRITICAL: GROQ_API_KEY not found in .env file.")
        return

    target_directory = "./sample_documents"
    os.makedirs(target_directory, exist_ok=True)

    agent = InvoiceIntelAgent()

    def progress(idx, total, filename):
        print(f"[{idx}/{total}] Processing {filename}...")

    final_report = agent.run_analysis(target_directory, progress_callback=progress)

    output_file = "invoice_report.json"
    with open(output_file, "w") as f:
        f.write(final_report)

    print(f"\nInvoiceIntel analysis complete! Results saved to {output_file}")


if __name__ == "__main__":
    main()
