import asyncio
import os
from playwright.async_api import async_playwright

USER_ID = "DP92228"
PASSWORD = "Win2026D"
VIN = "VF3EBRHD8BZ038648"
LOGIN_URL = "https://servicebox.peugeot.com/"

async def run():
    async with async_playwright() as p:
        # Use headless=False to ensure correct rendering as per API findings
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(http_credentials={"username": USER_ID, "password": PASSWORD})
        page = await context.new_page()
        
        print(f"Navigating to {LOGIN_URL}...")
        await page.goto(LOGIN_URL)
        
        # Determine main page (popup or current)
        target_page = page
        try:
            popup = await context.wait_for_event("page", timeout=5000)
            await popup.wait_for_load_state()
            print(f"Popup detected: {popup.url}")
            target_page = popup
        except:
            print("No new popup detected, using current page.")

        # Find FrameHub
        frame_hub = None
        for frame in target_page.frames:
            if "frameHub" in frame.name or "loadFrameHub" in frame.url:
                frame_hub = frame
                break
        working_frame = frame_hub if frame_hub else target_page

        # Enter VIN
        print(f"Entering VIN: {VIN}")
        vin_selector = "#short-vin"
        if await working_frame.query_selector(vin_selector):
            await working_frame.evaluate(f"document.querySelector('{vin_selector}').removeAttribute('disabled')")
            await working_frame.click(vin_selector, force=True)
            await working_frame.fill(vin_selector, VIN, force=True)
            await working_frame.press(vin_selector, "Enter")
            
            # Wait for dashboard
            print("Waiting for dashboard (DOKUMENTATION)...")
            try:
                await working_frame.wait_for_selector("text=DOKUMENTATION", timeout=20000)
                print("Dashboard loaded.")
            except:
                print("Dashboard load timeout.")
                
            # Wait a bit for async content
            await asyncio.sleep(5)
            
            # Additional check for tabs
            print("Checking active tabs...")
            # Screenshot specifically for dashboard analysis
            await target_page.screenshot(path="dashboard_inspection.png")
            
            # Dump all frames HTML to find the data
            print(f"Dumping content from {len(target_page.frames)} frames...")
            for i, frame in enumerate(target_page.frames):
                try:
                    f_name = frame.name if frame.name else f"frame_{i}"
                    f_url = frame.url
                    print(f"Dumping Frame {i}: {f_name} ({f_url})")
                    content = await frame.content()
                    safe_name = "".join([c for c in f_name if c.isalnum() or c in (' ', '.', '_')]).rstrip()
                    filename = f"dashboard_dump_frame_{i}_{safe_name}.html"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(content)
                except Exception as e:
                    print(f"Error dumping frame {i}: {e}")
            print("Frames dumped.")

        else:
            print("VIN input not found.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
