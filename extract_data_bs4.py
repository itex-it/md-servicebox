from bs4 import BeautifulSoup
import re

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def run():
    filename = 'dashboard_dump_frame_2_frameHub.html'
    print(f"Loading {filename}...")
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {}
    
    # 1. Warranty Info
    # Structure: <td class="textbold">Garantiebeginndatum :</td> <td>05/07/2011</td>
    try:
        # Find label 'Garantiebeginndatum'
        start_label = soup.find('td', string=re.compile(r'Garantiebeginndatum', re.IGNORECASE))
        if start_label:
            # Value is usually the next sibling td
            start_value = start_label.find_next_sibling('td')
            if start_value:
                data['warranty_start'] = clean_text(start_value.get_text())
        
        # Find label 'Garantieende' (careful not to match 'Garantieende Korrosion' first if regex is loose)
        # We can find all and check text
        labels = soup.find_all('td', string=re.compile(r'Garantieende', re.IGNORECASE))
        for label in labels:
            txt = clean_text(label.get_text())
            if 'Korrosion' in txt:
                # This is Corrosion
                corr_value = label.find_next_sibling('td')
                if corr_value:
                    data['warranty_end_corrosion'] = clean_text(corr_value.get_text())
            elif 'Garantieende' in txt:
                # This is standard end (likely)
                # But 'Garantieende Korrosion' also contains 'Garantieende'
                # So we check exact match or exclusion
                end_value = label.find_next_sibling('td')
                if end_value:
                     val = clean_text(end_value.get_text())
                     # Only set if not set or overwrite if it looks like a date and not 'Korrosion' logic
                     # Here, we assume the order or exact text. 
                     # Let's rely on exclusion.
                     if 'Korrosion' not in txt:
                         data['warranty_end'] = val

    except Exception as e:
        print(f"Error extracting warranty: {e}")

    # 2. LCDV
    # Table headers: G, M, LP...
    try:
        # Finding the table by looking for a header 'G' and 'M'
        # We find a 'th' with text 'G', then check parent 'tr'
        th_g = soup.find('th', string=re.compile(r'^\s*G\s*$', re.IGNORECASE)) # Precise match for G
        
        if th_g:
            row_header = th_g.find_parent('tr')
            if row_header:
                headers = [clean_text(th.get_text()) for th in row_header.find_all('th')]
                
                # Value row is next sibling tr
                row_value = row_header.find_next_sibling('tr')
                if row_value:
                    values = [clean_text(td.get_text()) for td in row_value.find_all('td')]
                    
                    if len(headers) == len(values) and len(headers) > 0:
                        data['lcdv'] = dict(zip(headers, values))
                    else:
                        data['lcdv_error'] = f"Mismatch: {len(headers)} headers vs {len(values)} values"
    
    except Exception as e:
        print(f"Error extracting LCDV: {e}")

    # 3. Recalls
    try:
        # Tab text: Überprüfungsaktion (0)
        # Using regex for partial match
        tab = soup.find('a', string=re.compile(r'Überprüfungsaktion', re.IGNORECASE))
        if tab:
            data['recall_tab_text'] = clean_text(tab.get_text())
        
        # Message
        msg = soup.find('p', class_='message', string=re.compile(r'Überprüfungsaktion', re.IGNORECASE))
        if msg:
            data['recall_message'] = clean_text(msg.get_text())
            
    except Exception as e:
        print(f"Error extracting recalls: {e}")
        
    print("-" * 20)
    print("EXTRACTED DATA:")
    print(data)
    print("-" * 20)

if __name__ == "__main__":
    run()
