import asyncio
import os
import time
from playwright.async_api import async_playwright
import config_loader

async def manual_test():
    output_dir = os.getcwd()
    vin = 'VF7SH8FP0CT512351'
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            http_credentials={
                "username": config_loader.config.get("user_id"),
                "password": config_loader.config.get("password"),
            },
            locale="de-DE"
        )
        page = await context.new_page()
        
        await page.goto(config_loader.config.get("login_url"))
        
        target_page = page
        try:
            popup = await context.wait_for_event("page", timeout=5000)
            await popup.wait_for_load_state()
            target_page = popup
        except:
            pass
            
        frame_hub = None
        for frame in target_page.frames:
            if "frameHub" in frame.name or "loadFrameHub" in frame.url:
                frame_hub = frame
                break
        
        working_frame = frame_hub if frame_hub else target_page
        
        print("Entering VIN...")
        vin_selector = "#short-vin"
        await working_frame.evaluate(f"document.querySelector('{vin_selector}').removeAttribute('disabled')")
        await working_frame.fill(vin_selector, vin)
        
        ok_btn_selector = "input[name='VIN_OK_BUTTON']"
        await working_frame.click(ok_btn_selector, force=True)
        
        print("Waiting for DOKUMENTATION tab...")
        await working_frame.wait_for_timeout(5000)
        
        print("Clicking DOKUMENTATION tab...")
        try:
            doc_link = working_frame.locator("text=DOKUMENTATION").first
            await doc_link.click(force=True)
            print("Clicked!")
        except Exception as e:
            print(f"Failed to click DOKUMENTATION: {e}")
            
        print("Waiting for dropdown to appear...")
        await working_frame.wait_for_timeout(2000)
        
        print("Searching for 'Documentation technique' in dropdown...")
        try:
            submenu_loc = working_frame.locator("a:has-text('Documentation technique')").first
            if await submenu_loc.is_visible():
                print(f"Found submenu text: {await submenu_loc.inner_text()}")
                await submenu_loc.click(force=True)
                print("Clicked submenu!")
            else:
                print("Submenu not visible. Dumping all links for debugging...")
                links = await working_frame.locator("a").all_inner_texts()
                print("Available links:", [l for l in links if l.strip()])
        except Exception as e:
            print(f"Failed to find/click submenu: {e}")
            
        print("Waiting to see what happens...")
        await working_frame.wait_for_timeout(5000)
        
        await target_page.screenshot(path=os.path.join(output_dir, "debug_manual_click.png"), full_page=True)
        print("Saved debug_manual_click.png")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(manual_test())
