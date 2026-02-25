import pdfplumber
import json
import glob
import os

pdf_files = glob.glob(os.path.join('downloads', '*VR1UJZKWZPW124195*.pdf'))
if not pdf_files:
    print("No PDF found for VIN VR1UJZKWZPW124195")
else:
    pdf_path = pdf_files[0]
    print(f"Parsing {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            print("No pages!")
        else:
            first_page = pdf.pages[0]
            tables = first_page.extract_tables()
            
            for i, table in enumerate(tables):
                print(f"--- Table {i} ---")
                for j, row in enumerate(table):
                    row_clean = [str(r).strip() if r is not None else "" for r in row]
                    print(f"Row {j}: {row_clean}")

