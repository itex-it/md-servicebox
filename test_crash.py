import asyncio
import os
import time
from servicebox_downloader import ServiceBoxDownloader
import config_loader

async def test_extraction():
    # Force headless=False to match local debugging
    config_loader.config['headless'] = False
    config_loader.save_config(config_loader.config)
    
    vin = "VF3MCYHZRKS406609"
    print(f"Testing downloader with crashing VIN: {vin}")
    dl = ServiceBoxDownloader(os.path.join(os.getcwd(), "downloads"))
    
    start_time = time.time()
    try:
        result = await dl.download_maintenance_plan(vin)
        print("\n=== Result ===")
        print(f"Success: {result.get('success')}")
        print(f"Error: {result.get('error')}")
        print(f"Message: {result.get('message')}")
        
    except Exception as e:
        print(f"\n=== CRITICAL ERROR ===")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_extraction())
