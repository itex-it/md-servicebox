import pdfplumber
import json
import sys

pdf_path = r"c:\##-Antigravity\servicebox\downloads\VF3EBRHD8BZ038648_Wartungsplan.pdf"

print(f"Analyzing {pdf_path}...")
try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        # We only care about the first page
        first_page = pdf.pages[0]
        
        print("\n--- EXTRACTED TEXT (FIRST 1000 CHARS) ---")
        text = first_page.extract_text()
        print(text[:1000] if text else "No text found.")
        
        print("\n--- EXTRACTED TABLES ---")
        tables = first_page.extract_tables()
        for i, table in enumerate(tables):
            print(f"\nTable {i+1}:")
            for row in table[:10]: # Print first 10 rows of each table
                print(row)
                
except Exception as e:
    print(f"Error parsing PDF: {e}")
