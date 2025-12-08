import fitz
import pdfplumber
from pathlib import Path
import os

# Relative path from project root
pdf_path = Path("agent/tool/local_search/update_box/A Survey of Reinforcement Learning for LLMs.pdf")
print(f"Current CWD: {os.getcwd()}")
print(f"Checking {pdf_path}: exists={pdf_path.exists()}")

print("Importing fitz...")
try:
    doc = fitz.open(pdf_path)
    print(f"Fitz opened PDF. Pages: {len(doc)}")
    doc.close()
except Exception as e:
    print(f"Fitz failed: {e}")

print("Importing pdfplumber...")
try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Pdfplumber opened PDF. Pages: {len(pdf.pages)}")
except Exception as e:
    print(f"Pdfplumber failed: {e}")
