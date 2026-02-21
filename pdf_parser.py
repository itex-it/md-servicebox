import pdfplumber
import os

def extract_maintenance_services(pdf_path: str) -> list:
    """
    Extracts maintenance services from the given ServiceBox Wartungsplan PDF.
    Returns a list of dictionaries:
    {'type': '...', 'description': '...', 'interval_standard': '...', 'interval_severe': '...'}
    """
    if not os.path.exists(pdf_path):
        return []

    services = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return []
                
            first_page = pdf.pages[0]
            tables = first_page.extract_tables()
            
            # The PDF contains multiple tables. We are looking for tables that look like:
            # Row 0: ['Systematische Arbeiten', None, None] (or similar section header)
            # Row N: ['Description', 'Standard', 'Severe']
            
            current_type = "Unknown"
            
            for table in tables:
                for row in table:
                    # Clean up the row
                    row = [str(r).strip() if r is not None else "" for r in row]
                    
                    if not any(row):
                        continue
                        
                    # If it's a section header (like ['Systematische Arbeiten', '', ''])
                    if row[0] and len(row) >= 3 and not row[1] and not row[2]:
                        current_type = row[0]
                        continue
                        
                    # If it's a data row and has valid content in columns 1 and 2
                    if len(row) >= 3 and row[0] and (row[1] or row[2]):
                        # Avoid matching headers like "WARTUNG", "Normale Nutzungsbedingungen"
                        if "Normale Nutzungsbedingungen" in row[1] or "WARTUNG" in row[0]:
                            continue
                            
                        # Avoid the descriptive text tables (e.g. "Die Wartungsintervalle...")
                        if len(row[0]) > 100:
                            continue
                            
                        services.append({
                            'type': current_type,
                            'description': row[0].replace('\n', ' '),
                            'interval_standard': row[1].replace('\n', ' '),
                            'interval_severe': row[2].replace('\n', ' ') if len(row) > 2 else ""
                        })
                        
    except Exception as e:
        print(f"Error parsing PDF {pdf_path}: {str(e)}")
        
    return services
