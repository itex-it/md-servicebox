import pdf_parser
import json
import glob
import os

pdfs = glob.glob(os.path.join('downloads', '*VR1UJZKWZPW124195*.pdf'))
if not pdfs:
    print("No PDFs found.")
else:
    for f in pdfs:
        try:
            print(f"Parsing {f}...")
            res = pdf_parser.extract_maintenance_services(f)
            print("Extracted Data:", json.dumps(res, indent=2))
        except Exception as e:
            print("Error:", e)
