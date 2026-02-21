import asyncio
import os
import re
import time
from playwright.async_api import async_playwright, Page

# Credentials provided by the user
USER_ID = "DP92228"
PASSWORD = "Win2026D"
VIN = "VF7FCKFVC9A101965"

# URLs
LOGIN_URL = "https://servicebox.peugeot.com/"

async def run():
    async with async_playwright() as p:
        # Launch browser in headless mode for silent execution
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            http_credentials={
                "username": USER_ID,
                "password": PASSWORD,
            }
        )

        # Set up popup handling
        page = await context.new_page()
        
        print(f"Navigating to {LOGIN_URL}...")
        await page.goto(LOGIN_URL)
        
        # Determine main page (popup or current)
        target_page = page
        try:
            # Check if a popup opens automatically
            popup = await context.wait_for_event("page", timeout=5000)
            await popup.wait_for_load_state()
            print(f"Popup detected: {popup.url}")
            target_page = popup
        except:
            print("No new popup detected, using current page.")

        print(f"Working on page: {target_page.url}")
        
        # Working with frames: The VIN input is likely in 'frameHub'
        frame_hub = None
        for frame in target_page.frames:
            if "frameHub" in frame.name or "loadFrameHub" in frame.url:
                frame_hub = frame
                print(f"Found Hub Frame: {frame.name}")
                break
        
        # Fallback to main page if frame not found (or if it's not a frameset page unexpectedly)
        working_frame = frame_hub if frame_hub else target_page

        # Dump content BEFORE VIN entry just in case
        try:
            await working_frame.wait_for_load_state('networkidle', timeout=5000)
        except:
            pass # Continue even if timeout

        try:
            content = await working_frame.content()
            with open("servicebox_pre_vin.html", "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"Warning: Could not dump pre-VIN content: {e}")

        # Attempt to enter VIN
        print(f"Attempting to enter VIN: {VIN} in frame {working_frame.name}")
        try:
            # Based on analysis: input id="short-vin" name="shortvin"
            # Button input name="VIN_OK_BUTTON"
            
            # Determine Brand based on VIN (Simple heuristic)
            brand_name = "Citroën" if "VF7" in VIN else "Peugeot"
            print(f"Detected brand for VIN {VIN}: {brand_name}")

            # 1. VIN ENTRY
            # Direct navigation failed (redirects back to login). Reverting to interaction method.
            print("Attempting VIN entry via interaction...")
            
            vin_selector = "#short-vin"
            if await working_frame.query_selector(vin_selector):
                print(f"Found VIN input: {vin_selector}")
                
                # Input is disabled in HTML. Enable it via JS first.
                print("Enabling VIN input via JS...")
                await working_frame.evaluate(f"document.querySelector('{vin_selector}').removeAttribute('disabled')")
                
                # Clear default value if needed (often "VIN/VIS")
                await working_frame.click(vin_selector, force=True)
                await working_frame.fill(vin_selector, "", force=True)
                await working_frame.fill(vin_selector, VIN, force=True)
                print("VIN filled.")
                
                # Click OK
                ok_btn_selector = "input[name='VIN_OK_BUTTON']"
                if await working_frame.query_selector(ok_btn_selector):
                    print("Clicking OK button...")
                    
                    # Click and wait for navigation
                    # Note: The page might reload or the frame might navigate.
                    # We accept either a navigation event or a change in content.
                    try:
                        async with target_page.expect_navigation(timeout=10000):
                             await working_frame.click(ok_btn_selector, force=True)
                    except:
                        print("Navigation timeout or no navigation event. Checking content...")
                else:
                    print("OK button not found. Probing alternatives...")
                    await working_frame.press(vin_selector, "Enter")
            else:
                print("Could not find #short-vin input.")

            # Validate success
            print("Waiting for dashboard to load...")
            try:
                # Wait up to 20s for "DOKUMENTATION"
                await working_frame.wait_for_selector("text=DOKUMENTATION", timeout=20000)
                print("Dashboard loaded successfully.")
            except:
                print("!! Dashboard element 'DOKUMENTATION' not found. We might be on an error page. !!")
                # Continue anyway to dump debug info

            
            # 2. NAVIGATE TO DOCUMENTS
            print("Accessing Documentation...")

            # Execute navigation directly via JS to be robust against overlay/click issues
            # The link is: javascript:goTo('/docapvpr/')
            # We invoke this directly in the frame context.
            print("Triggering goTo('/docapvpr/') via JS...")
            await working_frame.evaluate("goTo('/docapvpr/')")
            
            # Instead of expecting a generic page navigation (which might fail if it's just a frame update),
            # we wait for the expected element on the NEXT page: "Wartungspläne"
            print("Waiting for 'Wartungspläne' to appear...")
            try:
                # Give it time to load
                await working_frame.wait_for_selector("text=Wartungspläne", timeout=30000)
                print("Found 'Wartungspläne'. Navigation successful.")
            except Exception as e:
                print("Timeout waiting for 'Wartungspläne'. The page might have loaded something else or failed.")
                raise e

            # 3. NAVIGATE TO MAINTENANCE PLANS
            print("Accessing Maintenance Plans...")
            # Click "Wartungspläne" (Maintenance Plans)
            
            # We just confirmed it's visible or at least present
            wartung_link = working_frame.get_by_text(re.compile("Wartungspläne", re.IGNORECASE)).first
            await wartung_link.click()
            await working_frame.wait_for_load_state('networkidle')

            # 4. MAINTENANCE OVERVIEW
            # 4. MAINTENANCE OVERVIEW
            print("Accessing Maintenance Overview...")
            
            # Use specific ID for the tab "Wartungsübersicht"
            # Based on HTML: id="onglet.synthese"
            overview_tab = working_frame.locator("#onglet\\.synthese") 
            
            # Check if already selected? Class contains "titreSectionSelected"
            is_selected = await overview_tab.get_attribute("class")
            if "titreSectionSelected" not in str(is_selected):
                print("Clicking 'Wartungsübersicht' tab...")
                await overview_tab.click()
                await working_frame.wait_for_load_state('networkidle')
                # Wait for the form to update/appear
                await working_frame.wait_for_selector("form[name='synthesePEForm']", timeout=10000)
            else:
                print("'Wartungsübersicht' is already selected.")

            # 5. SELECT NORMAL CONDITIONS & DOWNLOAD
            print("Selecting Normal Conditions to trigger download...")
            
            # In Wartungsübersicht, the form is 'synthesePEForm'
            # The select ID is 'listeCU'
            
            select_elem = working_frame.locator("#listeCU")
            if await select_elem.is_visible():
                print("Found dropdown #listeCU")
                
                # "Normale Bedingungen" value from HTML: "8819_0244613299918KCO"
                # But it might be dynamic. Let's find the option by text.
                # We can't use 'val' from previous steps as it might differ.
                
                # Find the value for "Normale Bedingungen"
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
                    print(f"Found option value: {option_val}")
                    await select_elem.select_option(value=option_val)
                    
                    # Click Search Button
                    # Button ID: btnRechercher calls callActionSynth()
                    search_btn = working_frame.locator("#btnRechercher")
                    
                    print("Triggering Search/Download Popup...")
                    popup_page = None
                    
                    # Try Click
                    if await search_btn.is_visible():
                        try:
                            async with context.expect_page(timeout=5000) as popup_info:
                                await search_btn.click()
                            popup_page = await popup_info.value
                            print("Popup opened via click.")
                        except:
                            print("Click failed/timed out.")
                    
                    # Fallback JS
                    if not popup_page:
                        print("Trying JS callActionSynth()...")
                        try:
                            async with context.expect_page(timeout=10000) as popup_info:
                                await working_frame.evaluate("callActionSynth()")
                            popup_page = await popup_info.value
                            print("Popup opened via JS.")
                        except:
                            print("JS failed/timed out. Checking existing pages...")
                            for p in context.pages:
                                if "synthesePE" in p.url:
                                    popup_page = p
                                    print(f"Found existing popup: {p.url}")
                                    break
                    
                    if popup_page:
                        print("Popup detected! Starting processing...", flush=True)
                        
                        # Wait for URL to be valid
                        url = "unknown"
                        for _ in range(10):
                            try:
                                url = popup_page.url
                                if url and url.startswith("http"):
                                    break
                            except:
                                pass
                            await asyncio.sleep(1)
                        
                        print(f"DEBUG: Final Popup URL: '{url}'", flush=True)

                        await popup_page.wait_for_load_state('networkidle', timeout=30000)
                        print("Popup loaded.", flush=True)
                            
                        # Inspect Content-Type via API Request (sharing session)
                        print("Checking Content-Type...", flush=True)
                        
                        if not url or not url.startswith("http"):
                            print(f"ERROR: Invalid URL for request: '{url}'. Skipping download.", flush=True)
                            try:
                                await popup_page.screenshot(path=f"debug_popup_{VIN}.png")
                                print(f"Saved debug screenshot: debug_popup_{VIN}.png", flush=True)
                                with open(f"debug_popup_{VIN}.html", "w", encoding="utf-8") as f:
                                    f.write(await popup_page.content())
                                print(f"Saved debug HTML: debug_popup_{VIN}.html", flush=True)
                            except Exception as e:
                                print(f"Failed to capture debug info: {e}", flush=True)
                        else:
                            try:
                                # Use the context's request context to fetch the URL
                                api_response = await context.request.get(url)
                                content_type = api_response.headers.get("content-type", "").lower()
                                print(f"Content-Type: {content_type}", flush=True)
                                
                                base_filename = f"{VIN}_Wartungsplan.pdf"
                                filename = base_filename
                                
                                # Check if file exists and is locked? Just try to open.
                                try:
                                    # Create/Open file with write permission to check lock
                                    # If we can't open it here, we fail early and switch name
                                    pass 
                                except:
                                    pass

                                if "application/pdf" in content_type:
                                    print("Detected direct PDF stream. Downloading...", flush=True)
                                    data = await api_response.body()
                                    
                                    try:
                                        with open(filename, "wb") as f:
                                            f.write(data)
                                    except PermissionError:
                                        print(f"Warning: {filename} is locked or read-only. Saving with timestamp.")
                                        filename = f"{VIN}_Wartungsplan_{int(time.time())}.pdf"
                                        with open(filename, "wb") as f:
                                            f.write(data)
                                            
                                    print(f"SUCCESS: PDF Downloaded (Size: {len(data)} bytes) to {filename}", flush=True)
                                    
                                else:
                                    print("Content is NOT PDF (likely HTML container). Analyzing frames...", flush=True)
                                    # Dump frame structure
                                    for i, frame in enumerate(popup_page.frames):
                                        print(f"Frame {i}: {frame.name} - {frame.url}", flush=True)
                                    
                                    # If it's HTML, we might need to print it, BUT we need to ensure we print the content.
                                    # Often these are framesets. content frame is usually named 'bottom' or 'main' or similar.
                                    # Or just use CDP on the page itself if it renders visually.
                                    
                                    # Let's try to capture the page content again but with a different strategy if needed.
                                    # Since previous printToPDF was 12KB (empty), maybe we need to focus a specific frame?
                                    
                                    print(f"Attempting CDP PDF Generation for {filename} (Legacy Mode)...", flush=True)
                                    
                                    # Create CDP session
                                    cdp = await popup_page.context.new_cdp_session(popup_page)
                                    print("CDP Session created.", flush=True)
                                    
                                    # Ensure layout
                                    await popup_page.wait_for_timeout(2000)
                                    
                                    result = await cdp.send("Page.printToPDF", {
                                        "format": "A4",
                                        "printBackground": True
                                    })
                                    print("PDF generated via CDP.", flush=True)
                                    
                                    pdf_data = result['data']
                                    import base64
                                    decoded_data = base64.b64decode(pdf_data)
                                    
                                    with open(filename, "wb") as f:
                                        f.write(decoded_data)
                                    
                                    print(f"SUCCESS: PDF Generated via CDP (Size: {len(decoded_data)} bytes) to {filename}", flush=True)
                                    
                                    # Also save HTML of the main frame just in case
                                    html_file = f"{VIN}_Wartungsplan.html"
                                    with open(html_file, "w", encoding="utf-8") as f:
                                        f.write(await popup_page.content())
                                        
                            except Exception as e:
                                print(f"API Request/Download failed: {e}", flush=True)
                                import traceback
                                traceback.print_exc()


                    else:
                        print("ERROR: Failed to open popup.", flush=True)
                        
                else:
                    print("Could not find 'Normale Bedingungen' in #listeCU")
            
            else:
                print("Could not find #listeCU dropdown. Are we on the right tab?")
                
            return # End run here for now
            
            # Old Code below is obsolete with new targeting
            """
            cond_link = working_frame.get_by_text(re.compile("Normale Bedingungen", re.IGNORECASE)).first
            ...
            """
            
        except Exception as e:
            print(f"Error during automation: {e}")
            print("Dumping current state for debug...")
            try:
                content = await working_frame.content()
                with open("servicebox_debug_state.html", "w", encoding="utf-8") as f:
                    f.write(content)
                await target_page.screenshot(path="servicebox_debug_error.png")
            except:
                pass


        # Dump post-VIN content
        print("Dumping final state...")
        # Brief wait for reload
        await asyncio.sleep(5)
        
        content = await working_frame.content()
        with open("servicebox_post_vin.html", "w", encoding="utf-8") as f:
            f.write(content)
        
        # Screenshot
        await target_page.screenshot(path="servicebox_post_vin.png")
        print("Scraping complete. Files saved: servicebox_pre_vin.html, servicebox_post_vin.html, servicebox_post_vin.png")

        print("\nClosing in 30 seconds...")
        await asyncio.sleep(30)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
