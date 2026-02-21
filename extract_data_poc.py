from playwright.sync_api import sync_playwright
import os

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Load the local dump file
        file_path = f"file:///{os.getcwd()}/dashboard_dump_frame_2_frameHub.html".replace("\\", "/")
        print(f"Loading {file_path}")
        page.goto(file_path)
        
        data = {}
        
        # 1. Warranty Info
        try:
            # Warranty End
            # HTML: <td class="textbold"><font color="red">Garantieende :</font></td>
            # XPath: //td[contains(., 'Garantieende')]/following-sibling::td
            warranty_end_el = page.locator("//td[contains(., 'Garantieende') and not(contains(., 'Korrosion'))]/following-sibling::td").first
            if warranty_end_el.count() > 0:
                 data['warranty_end'] = warranty_end_el.inner_text().strip()
            
            # Warranty Start
            warranty_start_el = page.locator("//td[contains(., 'Garantiebeginndatum')]/following-sibling::td").first
            if warranty_start_el.count() > 0:
                 data['warranty_start'] = warranty_start_el.inner_text().strip()

            # Warranty End Corrosion
            warranty_corr_el = page.locator("//td[contains(., 'Garantieende Korrosion')]/following-sibling::td").first
            if warranty_corr_el.count() > 0:
                 data['warranty_end_corrosion'] = warranty_corr_el.inner_text().strip()

        except Exception as e:
            print(f"Error extracting warranty: {e}")

        # 2. LCDV
        try:
            # LCDV is in a table class="data center"
            # It has headers G, M, LP, SI etc.
            
            # XPath to find the header row: //table[contains(@class, 'data')]//tr[th[contains(., 'G')] and th[contains(., 'M')]]
            header_row = page.locator("//table[contains(@class, 'data')]//tr[th[contains(., 'G')] and th[contains(., 'M')]]").first
            
            if header_row.count() > 0:
                headers = header_row.locator("th").all_inner_texts()
                # Value row is the next sibling tr
                value_row = header_row.locator("xpath=following-sibling::tr").first
                values = value_row.locator("td").all_inner_texts()
                
                if len(headers) == len(values):
                    lcdv_data = dict(zip(headers, values))
                    data['lcdv'] = lcdv_data
                else:
                    data['lcdv_error'] = f"Mismatch: {len(headers)} headers, {len(values)} values"
            else:
                 data['lcdv_error'] = "Header row not found"
            
        except Exception as e:
            print(f"Error extracting LCDV: {e}")

        # 3. Recalls (Überprüfungsaktion)
        try:
            # Tab text: Überprüfungsaktion (0)
            tab = page.locator("//a[contains(., 'Überprüfungsaktion')]").first
            if tab.count() > 0:
                 data['recall_tab_text'] = tab.inner_text().strip()

            # Message: <p class="message">Mit dieser VIN sind keine Überprüfungsaktionen verbunden</p>
            msg = page.locator("//p[contains(@class, 'message') and contains(., 'Überprüfungsaktion')]").first
            if msg.count() > 0:
                data['recall_message'] = msg.inner_text().strip()

        except Exception as e:
            print(f"Error extracting recalls: {e}")



        print("Extracted Data:")
        print(data)
        
        browser.close()

if __name__ == "__main__":
    run()
