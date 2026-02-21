import asyncio
import os
import re
import time
import base64
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup
from config_loader import config, logger

class ServiceBoxDownloader:
    def __init__(self, output_dir=None, headless=None):
        # Prefer arguments, fallback to config
        self.output_dir = output_dir if output_dir else config.get("output_dir", "downloads")
        # headless arg priority: arg > config > False
        if headless is not None:
            self.headless = headless
        else:
            self.headless = config.get("headless", False)
            
        self.timeout = config.get("timeout_seconds", 30000)
        self.short_timeout = config.get("short_timeout_seconds", 5000)
            
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _clean_text(self, text):
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()

    def extract_vehicle_data(self, html_content):
        """
        Extracts vehicle data (Warranty, LCDV, Recalls) from the dashboard HTML.
        Refactored for robustness to handle dynamic fields.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        data = {
            "warranty": {},
            "lcdv": {},
            "recalls": {
                "status": "Unknown",
                "message": ""
            }
        }
        
        # 1. Warranty Info - Dynamic Parsing
        try:
            # Locate the table by a known anchor text
            anchor = soup.find(string=re.compile(r'Garantiebeginn', re.IGNORECASE))
            if anchor:
                # Walk up to the containing table
                warranty_table = anchor.find_parent('table')
                if warranty_table:
                    # Iterate over all rows to capture any key-value pairs
                    for tr in warranty_table.find_all('tr'):
                        cells = tr.find_all('td', recursive=False)
                        # The structure is typically: Label | Value | Spacer | Label | Value ...
                        # We iterate and check for 'textbold' class indicating a label
                        for i, cell in enumerate(cells):
                            classes = cell.get('class', [])
                            if classes and 'textbold' in classes:
                                key = self._clean_text(cell.get_text()).rstrip(':').strip()
                                # The value should be in the next cell
                                if i + 1 < len(cells):
                                    val = self._clean_text(cells[i+1].get_text())
                                    val = self._clean_text(cells[i+1].get_text())
                                    if key:
                                        data['warranty'][key] = val
        except Exception as e:
            logger.error(f"Error extracting warranty: {e}")

        # 2. LCDV - Context-based Search
        try:
            # Find "LCDV :" label
            lcdv_label = soup.find(string=re.compile(r'LCDV\s*:', re.IGNORECASE))
            if lcdv_label:
                # The data table is usually nested in the same container or nearby
                container = lcdv_label.find_parent('table')
                if container:
                    # Look for the data table within this container
                    data_table = container.find('table', class_='data')
                    if data_table:
                        rows = data_table.find_all('tr')
                        if len(rows) >= 2:
                            headers = [self._clean_text(th.get_text()) for th in rows[0].find_all(['th', 'td'])]
                            values = [self._clean_text(td.get_text()) for td in rows[1].find_all(['th', 'td'])]
                            
                            # Filter empty headers
                            clean_headers = []
                            clean_values = []
                            for h, v in zip(headers, values):
                                if h:
                                    clean_headers.append(h)
                                    clean_values.append(v)
                            
                            if clean_headers:
                                data['lcdv'] = dict(zip(clean_headers, clean_values))
        except Exception as e:
            logger.error(f"Error extracting LCDV: {e}")

        # 3. Recalls
        try:
            # Look for tab text
            # Example: "Überprüfungsaktion (1)"
            tab = soup.find('a', string=re.compile(r'Überprüfungsaktion', re.IGNORECASE))
            if tab:
                tab_text = self._clean_text(tab.get_text())
                data['recalls']['tab_text'] = tab_text
                
                # Check for (0) vs (1+)
                # Extract number in parentheses
                match = re.search(r'\((\d+)\)', tab_text)
                if match:
                    count = int(match.group(1))
                    if count > 0:
                        data['recalls']['status'] = "Active"
                        # If active, we expect a message. 
                        # Try to find the message content.
                        # 1. Strict search (original)
                        msg = soup.find('p', class_='message', string=re.compile(r'Überprüfungsaktion', re.IGNORECASE))
                        if not msg:
                             # 2. Relaxed search: Just any 'message' paragraph, as it might just describe the recall
                             msg = soup.find('p', class_='message')
                        
                        if msg:
                            data['recalls']['message'] = self._clean_text(msg.get_text())
                        else:
                            # Fallback if we can't find the text but know there is a recall
                            data['recalls']['message'] = f"Active Recall detected ({count}). See ServiceBox for details."
                    else:
                        data['recalls']['status'] = "None"
                        data['recalls']['message'] = "No recalls"
            
            # Legacy/Fallback if tab not found but message exists
            if data['recalls']['status'] == "Unknown":
                msg = soup.find('p', class_='message', string=re.compile(r'Überprüfungsaktion', re.IGNORECASE))
                if msg:
                    dt = self._clean_text(msg.get_text())
                    data['recalls']['message'] = dt
                    if "keine" in dt.lower() or "aucun" in dt.lower():
                         data['recalls']['status'] = "None"
                    else:
                         data['recalls']['status'] = "Active"
        except Exception as e:
            logger.error(f"Error extracting recalls: {e}")

        # 4. Model / Vehicle Title Extraction (Heuristic)
        try:
            model_text = None
            # Try H1
            h1 = soup.find('h1')
            if h1: model_text = self._clean_text(h1.get_text())
            
            # Try .titre
            if not model_text:
                titre = soup.select_one('.titre')
                if titre: model_text = self._clean_text(titre.get_text())

            # Try finding the element containing the VIN and looking at siblings
            if not model_text:
                # Assuming VIN is somewhere in the header
                pass 

            if model_text:
                # Clean up "Service Box" prefix if present
                model_text = model_text.replace('Service Box', '').strip()
                # Store in warranty so it saves to DB without schema change
                data['warranty']['Model'] = model_text # Changed to warranty to match existing structure
                logger.info(f"Extracted Model: {model_text}")

        except Exception as e:
            logger.warning(f"Failed to extract model name: {e}")

            
        return data

    async def download_maintenance_plan(self, vin: str):
        """
        Attempts to download the maintenance plan for the given VIN.
        Returns a dictionary with status and details.
        """
        start_time = time.time()
        logger.info(f"[ServiceBoxDownloader] Starting download for VIN: {vin}")
        result = {
            "success": False,
            "vin": vin,
            "file_path": None,
            "message": "",
            "vehicle_data": {},
            "details": {},
            "duration_seconds": 0
        }
        
        async with async_playwright() as p:
            launch_args = []
            if self.headless:
                # Use new headless mode which supports extensions/popups better on Windows
                launch_args.append("--headless=new")
            
            # We set headless=False in launch() because we are passing the flag manually via args
            # if we want the "new" mode. If self.headless is False, we just launch normally (headful).
            # Effectively: headless=False always, but args control the actual mode if headless is requested.
            
            browser = await p.chromium.launch(
                headless=False, # We control headless via args for 'new' mode
                args=launch_args
            )
            context = await browser.new_context(
                http_credentials={
                    "username": config.get("user_id"),
                    "password": config.get("password"),
                }
            )
            
            try:
                page = await context.new_page()
                login_url = config.get("login_url")
                print(f"Navigating to {login_url}...")
                await page.goto(login_url)
                
                # Determine main page (popup or current)
                # Determine main page (popup or current)
                target_page = page
                try:
                    popup = await context.wait_for_event("page", timeout=self.short_timeout)
                    await popup.wait_for_load_state()
                    logger.info(f"Popup detected: {popup.url}")
                    target_page = popup
                except:
                    logger.info("No new popup detected, using current page.")

                # Working with frames
                frame_hub = None
                for frame in target_page.frames:
                    if "frameHub" in frame.name or "loadFrameHub" in frame.url:
                        frame_hub = frame
                        break
                
                working_frame = frame_hub if frame_hub else target_page
                
                # Ensure loaded
                try:
                    await working_frame.wait_for_load_state('networkidle', timeout=self.short_timeout)
                except:
                    pass

                # Enter VIN
                logger.info(f"Attempting to enter VIN: {vin}")
                vin_selector = "#short-vin"
                if await working_frame.query_selector(vin_selector):
                    await working_frame.evaluate(f"document.querySelector('{vin_selector}').removeAttribute('disabled')")
                    await working_frame.click(vin_selector, force=True)
                    await working_frame.fill(vin_selector, vin, force=True)
                    
                    ok_btn_selector = "input[name='VIN_OK_BUTTON']"
                    if await working_frame.query_selector(ok_btn_selector):
                        try:
                            # Navigation can take time
                            async with target_page.expect_navigation(timeout=self.timeout):
                                await working_frame.click(ok_btn_selector, force=True)
                        except:
                            logger.info("Navigation timeout. Checking content...")
                    else:
                        await working_frame.press(vin_selector, "Enter")
                else:
                    result["success"] = False
                    result["message"] = "VIN input not found (Login failed?)"
                    return result

                # Validate Dashboard
                try:
                    await working_frame.wait_for_selector("text=DOKUMENTATION", timeout=self.timeout)
                except:
                    result["success"] = False
                    result["message"] = "Dashboard not loaded (Invalid VIN?)"
                    return result

                # --- EXTRACTION STEP ---
                logger.info("Dashboard loaded. Extracting vehicle data (initial)...")
                content = await working_frame.content()
                vehicle_data = self.extract_vehicle_data(content)
                
                # Check for Recall Tab interaction
                # If we detected a potential recall count > 0 in the initial extraction
                # based on tab text like "Überprüfungsaktion (1)", we need to click it into view.
                recall_tab_text = vehicle_data.get('recalls', {}).get('tab_text', '')
                match = re.search(r'\((\d+)\)', recall_tab_text)
                recall_count = int(match.group(1)) if match else 0
                
                if recall_count > 0:
                    logger.info(f"Detected {recall_count} recalls. Clicking tab to extract details...")
                    try:
                        # Click the tab
                        # Selector: anchor with text matching "Überprüfungsaktion"
                        tab_selector = "a:text-matches('Überprüfungsaktion', 'i')"
                        if await working_frame.query_selector(tab_selector):
                            await working_frame.click(tab_selector)
                            await working_frame.wait_for_timeout(2000) # Wait for dynamic load
                            
                            # Re-extract content with the table visible
                            content_detailed = await working_frame.content()
                            
                            # Parse the table using BS4 again (or extend extract_vehicle_data)
                            # We can do it inline or update the method. Use inline here for clarity/separation.
                            soup = BeautifulSoup(content_detailed, 'html.parser')
                            
                            # Find the table. It usually has headers like "Code", "Wortlaut", "Zustand"
                            # We look for a table containing "Zustand"
                            recall_table = None
                            for tbl in soup.find_all('table'):
                                if tbl.find(string=re.compile(r'Zustand', re.IGNORECASE)):
                                    recall_table = tbl
                                    break
                            
                            if recall_table:
                                details = []
                                active_codes = []
                                # Iterate rows (skipping header)
                                rows = recall_table.find_all('tr')
                                for row in rows:
                                    cells = row.find_all('td')
                                    # Expected columns: Code | Wortlaut | ... | Zustand | ...
                                    # We need to find indices or just iterate
                                    if len(cells) >= 4: # Assuming at least 4 cols
                                        code = self._clean_text(cells[0].get_text())
                                        description = self._clean_text(cells[1].get_text())
                                        
                                        # Zustand (Status) is usually column index 3 (0-based)
                                        # But let's look for the classes 'picto_rouge' or 'picto_vert' in the whole row or specific cell
                                        # logic based on debug dump:
                                        # <div class="picto_rouge"> -> Red (Open)
                                        # <div class="picto_vert"> -> Green (Done)
                                        
                                        status = "Unknown"
                                        # Check the whole row for these specific classes to be safe, 
                                        # or strictly check the 'Zustand' cell if we are sure of the index.
                                        # Table headers: Code, Wortlaut, Typ, Zustand, ...
                                        # So Zustand is likely index 3.
                                        
                                        # Let's check for the classes in the row
                                        if row.find('div', class_='picto_rouge'):
                                            status = "Open"
                                        elif row.find('div', class_='picto_red'): # Fallback just in case
                                            status = "Open"
                                        elif row.find('div', class_='picto_vert'):
                                            status = "Done"
                                        elif row.find('div', class_='picto_green'): # Fallback
                                            status = "Done"
                                        
                                        if code and len(code) < 10: # Sanity check
                                            details.append({
                                                "code": code,
                                                "description": description,
                                                "status": status
                                            })
                                            if status == "Open":
                                                active_codes.append(code)
                                
                                # Update vehicle_data
                                vehicle_data['recalls']['details'] = details
                                if active_codes:
                                    vehicle_data['recalls']['status'] = "Active"
                                    vehicle_data['recalls']['message'] = f"Active Codes: {', '.join(active_codes)}"
                                else:
                                    # If all are done (Green)
                                    vehicle_data['recalls']['status'] = "None"
                                    vehicle_data['recalls']['message'] = "All recalls completed"
                                    
                            else:
                                logger.warning("Recall table not found after clicking tab.")
                                
                    except Exception as e:
                        logger.error(f"Error extracting detailed recalls: {e}")

                result["vehicle_data"] = vehicle_data
                logger.info(f"Extracted data: {vehicle_data}")
                # -----------------------

                # Navigate to Documentation
                await working_frame.evaluate("goTo('/docapvpr/')")
                
                try:
                    await working_frame.wait_for_selector("text=Wartungspläne", timeout=self.timeout)
                except:
                    result["success"] = False
                    result["message"] = "Timeout waiting for 'Wartungspläne'"
                    return result

                # Access Maintenance Plans
                wartung_link = working_frame.get_by_text(re.compile("Wartungspläne", re.IGNORECASE)).first
                await wartung_link.click()
                await working_frame.wait_for_load_state('networkidle')

                # Maintenance Overview Tab
                overview_tab = working_frame.locator("#onglet\\.synthese")
                is_selected = await overview_tab.get_attribute("class")
                if "titreSectionSelected" not in str(is_selected):
                    await overview_tab.click()
                    await working_frame.wait_for_load_state('networkidle')
                    await working_frame.wait_for_selector("form[name='synthesePEForm']", timeout=self.timeout)

                # Select Normal Conditions
                select_elem = working_frame.locator("#listeCU")
                if await select_elem.is_visible():
                    option_val = await working_frame.evaluate("""
                        () => {
                            const sel = document.getElementById('listeCU');
                            for (let i = 0; i < sel.options.length; i++) {
                                if (sel.options[i].text.includes('Normale Bedingungen')) {
                                    return sel.options[i].value;
                                }
                            }
                            return null;
                        }
                    """)
                    
                    if option_val:
                        await select_elem.select_option(value=option_val)
                        search_btn = working_frame.locator("#btnRechercher")
                        
                        popup_page = None
                        if await search_btn.is_visible():
                            try:
                                async with context.expect_page(timeout=self.short_timeout) as popup_info:
                                    await search_btn.click()
                                popup_page = await popup_info.value
                            except:
                                pass
                        
                        if not popup_page:
                            try:
                                async with context.expect_page(timeout=self.timeout) as popup_info:
                                    await working_frame.evaluate("callActionSynth()")
                                popup_page = await popup_info.value
                            except:
                                # Start checking existing pages if popup opening failed
                                for p in context.pages:
                                    if "synthesePE" in p.url:
                                        popup_page = p
                                        break
                        
                        if popup_page:
                            # Wait for valid URL
                            url = "unknown"
                            logger.info("Waiting for popup URL to settle...")
                            for i in range(30):
                                try:
                                    url = popup_page.url
                                    logger.debug(f"Popup URL check {i}: {url}")
                                    if url and url.startswith("http"):
                                        break
                                except Exception as e:
                                    logger.error(f"Popup URL check error: {e}")
                                await asyncio.sleep(1)
                            
                            logger.info(f"Final Popup URL: {url}")
                            
                            if not url or not url.startswith("http"):
                                try:
                                    # Attempt debug capture
                                    debug_shot = os.path.join(self.output_dir, f"debug_popup_{vin}.png")
                                    await popup_page.screenshot(path=debug_shot)
                                except:
                                    pass
                                result["success"] = False
                                result["message"] = f"Invalid Popup URL: {url}"
                                return result

                            try:
                                api_response = await context.request.get(url)
                                content_type = api_response.headers.get("content-type", "").lower()
                                
                                timestamp = time.strftime("%Y%m%d_%H%M%S")
                                filename = os.path.join(self.output_dir, f"{vin}_{timestamp}_Wartungsplan.pdf")
                                
                                if "application/pdf" in content_type:
                                    data = await api_response.body()
                                    with open(filename, "wb") as f:
                                        f.write(data)
                                    result["success"] = True
                                    result["file_path"] = os.path.abspath(filename)
                                    result["message"] = "PDF Downloaded successfully"
                                else:
                                    # CDP Fallback
                                    cdp = await popup_page.context.new_cdp_session(popup_page)
                                    await popup_page.wait_for_timeout(2000)
                                    res = await cdp.send("Page.printToPDF", {"format": "A4", "printBackground": True})
                                    pdf_data = base64.b64decode(res['data'])
                                    with open(filename, "wb") as f:
                                        f.write(pdf_data)
                                    result["success"] = True
                                    result["file_path"] = os.path.abspath(filename)
                                    result["message"] = "PDF Generated via CDP"
                                    
                            except Exception as e:
                                result["success"] = False
                                result["message"] = f"Download failed: {str(e)}"
                                return result
                        else:
                            result["success"] = False
                            result["message"] = "Failed to open popup"
                            return result
                    else:
                        result["success"] = False
                        result["message"] = "'Normale Bedingungen' option not found"
                        return result
                else:
                    result["success"] = False
                    result["message"] = "Dropdown #listeCU not found"
                    return result
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                result["message"] = f"Automation error: {str(e)}"
            finally:
                await browser.close()
                end_time = time.time()
                result["duration_seconds"] = round(end_time - start_time, 2)
                
        return result

# Simple run check
if __name__ == "__main__":
    downloader = ServiceBoxDownloader()
    # async_playwright must be run in async loop
    # Testing with NEW VIN: VF7SH8FP0CT512351
    res = asyncio.run(downloader.download_maintenance_plan("VF7SH8FP0CT512351"))
    print("\n--- FINAL RESULT ---")
    print(res)

