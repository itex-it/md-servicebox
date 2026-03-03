import asyncio
import os
import re
import time
import base64
from playwright.async_api import async_playwright, Page, Frame
from typing import Dict, Any, List, Optional
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

    async def _find_in_frames(self, target_page, text_pattern, timeout_sec=10):
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            for f in target_page.frames:
                try:
                    locs = f.get_by_text(text_pattern)
                    count = await locs.count()
                    for i in range(count):
                        nth_loc = locs.nth(i)
                        if await nth_loc.is_visible():
                            return f, nth_loc
                except:
                    pass
            await asyncio.sleep(0.5)
        return None, None

    async def _find_locator_in_frames(self, target_page, selector, timeout_sec=10):
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            for f in target_page.frames:
                try:
                    locs = f.locator(selector)
                    count = await locs.count()
                    for i in range(count):
                        nth_loc = locs.nth(i)
                        if await nth_loc.is_visible():
                            return f, nth_loc
                except:
                    pass
            await asyncio.sleep(0.5)
        return None, None

    def extract_vehicle_data(self, html_content):
        """
        Extracts vehicle data (Warranty, LCDV, Recalls) from the dashboard HTML.
        Refactored for robustness to handle dynamic fields.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        data: Dict[str, Any] = {
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

    async def download_maintenance_plan(self, vin: str, recalls_only: bool = False, progress_callback=None):
        """
        Attempts to download the maintenance plan for the given VIN.
        If recalls_only is True, skips PDF generation and returns early.
        Returns a dictionary with status and details.
        """
        def notify(msg):
            if progress_callback:
                progress_callback(msg)

        start_time = time.time()
        logger.info(f"[ServiceBoxDownloader] Starting download for VIN: {vin}")
        notify("Starting browser...")
        result: Dict[str, Any] = {
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
            playwright_headless = self.headless
            
            if os.name == 'nt':
                # Windows: Use new headless mode which supports extensions/popups better
                playwright_headless = False
                if self.headless:
                    launch_args.append("--headless=new")
            else:
                # Linux/Docker: Must use native headless mode to avoid X11 errors.
                # Unconditionally force True because Docker has no GUI, even if config is blank.
                launch_args = ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
                playwright_headless = True
            
            # Proxy implementation
            proxy_config = config.get("proxy", {})
            playwright_proxy = None
            
            if proxy_config and proxy_config.get("server"):
                logger.info(f"[ServiceBoxDownloader] Launching with proxy server: {proxy_config.get('server')}")
                playwright_proxy = {
                    "server": proxy_config.get("server"),
                }
                if proxy_config.get("username"):
                    playwright_proxy["username"] = proxy_config.get("username")
                if proxy_config.get("password"):
                    playwright_proxy["password"] = proxy_config.get("password")
            
            browser = await p.chromium.launch(
                headless=playwright_headless,
                args=launch_args,
                proxy=playwright_proxy
            )
            context = await browser.new_context(
                http_credentials={
                    "username": config.get("user_id"),
                    "password": config.get("password"),
                },
                locale="de-DE",
                timezone_id="Europe/Vienna",
                accept_downloads=True
            )
            
            # Start Playwright Tracing for Docker Debugging
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            
            try:
                page = await context.new_page()
                
                # Resource blocking removed to ensure full SPA layout stability.
                
                login_url = config.get("login_url") or "https://servicebox.peugeot.com/"
                if not login_url:
                    result["message"] = "Configuration error: login_url is not set in config.json"
                    return result
                print(f"Navigating to {login_url}...")
                notify("Navigating to Login URL...")
                await page.goto(login_url, timeout=self.timeout)
                
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
                notify("Entering VIN...")
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

                # Validate Dashboard or capture explicit errors
                try:
                    error_locator = working_frame.locator("text=Die eingegebene VIN/VIS ist unbekannt").first
                    dashboard_locator = working_frame.locator("text=DOKUMENTATION").first
                    
                    wait_seconds = int(self.timeout / 1000) + 1
                    for _ in range(wait_seconds):
                        if await error_locator.is_visible():
                            result["success"] = False
                            result["message"] = "VIN is unknown (Die eingegebene VIN/VIS ist unbekannt)"
                            logger.error(f"VIN explicitly rejected by ServiceBox: {vin}")
                            return result
                        if await dashboard_locator.is_visible():
                            break
                        await working_frame.wait_for_timeout(1000)
                    else:
                        result["success"] = False
                        result["message"] = "Dashboard not loaded (Timeout or Website unreachable)"
                        logger.error(f"Dashboard timeout for VIN {vin}")
                        return result
                        
                except Exception as e:
                    result["success"] = False
                    result["message"] = f"Dashboard validation failed: {str(e)}"
                    return result

                # --- EXTRACTION STEP ---
                logger.info("Dashboard loaded. Extracting vehicle data (initial)...")
                notify("Extracting vehicle data...")
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
                    notify("Extracting detailed recalls...")
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
                                details: List[Dict[str, Any]] = []
                                active_codes: List[str] = []
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
                
                if recalls_only:
                    logger.info("recalls_only flag is set. Exiting download early.")
                    result["success"] = True
                    result["message"] = "Recalls extracted successfully"
                    result["duration_seconds"] = round(time.time() - start_time, 2)
                    return result
                    
                # -----------------------

                # Navigate to Documentation
                logger.info("Navigating to 'Dokumentation' tab via UI clicks...")
                notify("Navigating to Maintenance Documentation...")
                try:
                    doc_link = working_frame.locator("text=DOKUMENTATION").first
                    if await doc_link.is_visible():
                        await doc_link.click(force=True)
                        await working_frame.wait_for_timeout(2000)
                        
                        # Click "Documentation technique" using JS evaluation to bypass strict Playwright visibility checks
                        clicked = False
                        try:
                            # Use locator().all() instead of element_handles, and text_content() which bypasses CSS rendering
                            links = await working_frame.locator("a").all()
                            logger.info(f"Dumping {len(links)} links for debugging...")
                            dumped_texts = []
                            for lnk in links:
                                text = await lnk.text_content()
                                if text: 
                                    text_clean = re.sub(r'\s+', ' ', text.strip()).lower()
                                    dumped_texts.append(text.strip())
                                    
                                    # Very loose matching to ensure we catch it, print repr for debugging
                                    if "technique" in text_clean or "dokumentation" in text_clean:
                                        if ("documentation technique" in text_clean) or ("technische dokumentation" in text_clean) or ("dokumentation citro" in text_clean) or ("dokumentation peugeot" in text_clean) or ("dokumentation ds" in text_clean) or ("dokumentation opel" in text_clean):
                                            # Avoid clicking instructional documentation links
                                            if "was sollte eine did-a" not in text_clean and "verkaufsdokumentation" not in text_clean:
                                                await lnk.evaluate("el => el.click()")
                                                logger.info(f"Clicked submenu via JS: {text.strip()}")
                                                clicked = True
                                                await asyncio.sleep(2)
                                                break
                            if not clicked:
                                logger.warning(f"Dumped links: {dumped_texts}")
                        except Exception as inner_e:
                            logger.warning(f"Failed to find/click via handles: {inner_e}")
                            
                        if not clicked:
                            logger.warning("Documentation technique submenu not found or clickable.")
                    else:
                        logger.warning("DOKUMENTATION tab not visible. Trying legacy goTo fallback...")
                        for f in target_page.frames:
                            try:
                                await f.evaluate("if(typeof goTo === 'function') { goTo('synthesePE', '1', '1'); }")
                            except: pass
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to navigate to Documentation explicitly: {e}")
                
                logger.info("Searching for Wartungspläne across all frames...")
                notify("Searching for Wartungspläne...")
                wartung_frame, wartung_link = await self._find_in_frames(target_page, re.compile("Wartungspläne", re.IGNORECASE), timeout_sec=int(self.timeout/1000))
                
                if wartung_link:
                    await wartung_link.click()
                    try:
                        await wartung_frame.wait_for_load_state('networkidle', timeout=self.short_timeout)
                    except: pass
                else:
                    # Take screenshot for debugging
                    try:
                        debug_dir = os.path.join(os.getcwd(), "debug")
                        os.makedirs(debug_dir, exist_ok=True)
                        await target_page.screenshot(path=os.path.join(debug_dir, f"debug_wartungsplaene_{vin}.png"), full_page=True)
                        logger.info(f"Saved debug screenshot for {vin}")
                    except Exception as ss_e:
                        logger.error(f"Failed to save debug screenshot: {ss_e}")
                    result["success"] = False
                    result["message"] = "Timeout waiting for 'Wartungspläne'"
                    return result

                # Maintenance Overview Tab
                logger.info("Searching for Wartungsübersicht tab...")
                overview_frame, overview_tab = await self._find_locator_in_frames(target_page, "#onglet\\.synthese", timeout_sec=int(self.short_timeout/1000))
                
                if overview_tab:
                    is_selected = await overview_tab.get_attribute("class")
                    if "titreSectionSelected" not in str(is_selected):
                        await overview_tab.click()
                        try:
                            await overview_frame.wait_for_load_state('networkidle', timeout=self.short_timeout)
                            await overview_frame.wait_for_selector("form[name='synthesePEForm']", timeout=self.short_timeout)
                        except: pass

                # Select Normal Conditions
                logger.info("Searching for Einsatzbedingungen dropdown...")
                select_frame, select_elem = await self._find_locator_in_frames(target_page, "#listeCU", timeout_sec=int(self.timeout/1000))
                
                if select_elem:
                    option_val = await select_frame.evaluate("""
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
                        logger.info("Searching for btnRechercher...")
                        btn_frame, search_btn = await self._find_locator_in_frames(target_page, "#btnRechercher", timeout_sec=int(self.short_timeout/1000))
                        
                        popup_page = None
                        if search_btn:
                            try:
                                async with context.expect_page(timeout=self.short_timeout) as popup_info:
                                    await search_btn.click()
                                popup_page = await popup_info.value
                            except:
                                pass
                        
                        if not popup_page:
                            try:
                                async with context.expect_page(timeout=self.timeout) as popup_info:
                                    if btn_frame:
                                        await btn_frame.evaluate("callActionSynth()")
                                    else:
                                        for f in target_page.frames:
                                            try:
                                                await f.evaluate("callActionSynth()")
                                            except: pass
                                popup_page = await popup_info.value
                            except:
                                # Start checking existing pages if popup opening failed
                                for p in context.pages:
                                    if "synthesePE" in p.url:
                                        popup_page = p
                                        break
                        
                        if popup_page:
                            # Wait for the popup to navigate away from about:blank to a real http URL.
                            # wait_for_url() is the correct Playwright API for this — it waits
                            # for the page navigation to complete, unlike polling popup_page.url.
                            logger.info("Waiting for popup to navigate to real URL...")
                            url = ""
                            try:
                                await popup_page.wait_for_url(
                                    lambda u: u.startswith("http"),
                                    timeout=self.timeout
                                )
                                url = popup_page.url
                                logger.info(f"Popup navigated to: {url}")
                            except Exception as nav_err:
                                logger.warning(f"wait_for_url failed: {nav_err}. Trying JS evaluate fallback...")
                                # Fallback: try reading URL via JavaScript
                                try:
                                    url = await popup_page.evaluate("window.location.href")
                                    logger.info(f"JS fallback URL: {url}")
                                except Exception as js_err:
                                    logger.error(f"JS URL fallback also failed: {js_err}")
                                    url = popup_page.url or ""
                            
                            notify("Downloading Maintenance PDF...")
                            logger.info(f"Final Popup URL: {url}")
                            
                            if not url or not url.startswith("http"):
                                try:
                                    debug_dir = os.path.join(os.getcwd(), "debug")
                                    os.makedirs(debug_dir, exist_ok=True)
                                    await popup_page.screenshot(path=os.path.join(debug_dir, f"debug_popup_{vin}.png"))
                                    logger.info(f"Saved popup debug screenshot for {vin}")
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
                                    notify("Generating PDF via CDP fallback...")
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
                
                # Save trace on failure
                try:
                    trace_filename = f"trace_{vin}_{int(time.time())}.zip"
                    # In docker, we'll map /app/debug to ./debug
                    trace_dir = os.path.join(os.getcwd(), "debug")
                    if not os.path.exists(trace_dir):
                        os.makedirs(trace_dir, exist_ok=True)
                    
                    trace_path = os.path.join(trace_dir, trace_filename)
                    await context.tracing.stop(path=trace_path)
                    logger.error(f"Saved failure trace to {trace_path}")
                    
                    # Cleanup old traces to prevent disk-full errors
                    try:
                        import glob
                        trace_files = glob.glob(os.path.join(trace_dir, "trace_*.zip"))
                        if len(trace_files) > 5:
                            # Sort by modified time, oldest first
                            trace_files.sort(key=os.path.getmtime)
                            # Delete until only 5 are left
                            for old_trace in trace_files[:-5]:
                                try:
                                    os.remove(old_trace)
                                except:
                                    pass
                    except Exception as cleanup_e:
                        logger.error(f"Could not cleanly delete old traces: {cleanup_e}")
                        
                except Exception as trace_e:
                    logger.error(f"Could not save trace: {trace_e}")
                    
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

