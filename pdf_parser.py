import pdfplumber
import os
import re

def parse_interval_string(text: str) -> dict:
    text = text.lower().strip()
    result = {
        "interval_type": "unknown",
        "km": None,
        "years": None
    }
    
    if not text:
        return result
        
    if "dann alle" in text:
        result["interval_type"] = "first_then"
    elif "alle " in text or text.startswith("alle"):
        result["interval_type"] = "recurring"
    else:
        result["interval_type"] = "once"
        
    km_match = re.search(r'(\d+)\s*km', text)
    if km_match:
        result["km"] = int(km_match.group(1))
        
    year_match = re.search(r'(\d+)\s*jahr', text)
    if year_match:
        result["years"] = int(year_match.group(1))
        
    return result


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
                        
                    # If it's a section header (like ['Systematische Arbeiten', ''] or ['Systematische Arbeiten', '', ''])
                    if row[0] and len(row) >= 2 and not row[1] and (len(row) < 3 or not row[2]):
                        current_type = row[0]
                        continue
                        
                    # If it's a data row and has valid content
                    if len(row) >= 2 and row[0] and row[1]:
                        # Avoid matching headers like "WARTUNG", "Normale Nutzungsbedingungen"
                        if "Normale Nutzungsbedingungen" in row[1] or "WARTUNG" in row[0]:
                            continue
                            
                        # Avoid the descriptive text tables (e.g. "Die Wartungsintervalle...")
                        if len(row[0]) > 100:
                            continue
                            
                        interval_standard = row[1].replace('\n', ' ')
                        interval_severe = row[2].replace('\n', ' ') if len(row) > 2 and row[2] else ""
                        
                        parsed = parse_interval_string(interval_standard)
                        parsed_severe = parse_interval_string(interval_severe) if interval_severe else {}
                        
                        svc = {
                            'type': current_type,
                            'description': row[0].replace('\n', ' '),
                            'interval_standard': interval_standard,
                            'interval_severe': interval_severe,
                            'interval_type': parsed.get('interval_type', 'unknown'),
                            'km': parsed.get('km'),
                            'years': parsed.get('years')
                        }
                        
                        if interval_severe:
                            svc['severe_km'] = parsed_severe.get('km')
                            svc['severe_years'] = parsed_severe.get('years')
                            
                        services.append(svc)
                        
    except Exception as e:
        print(f"Error parsing PDF {pdf_path}: {str(e)}")
        
    return services
