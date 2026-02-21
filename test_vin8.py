import asyncio
from servicebox_downloader import ServiceBoxDownloader
import os

async def test_vin8():
    vin8 = "BZ038648"  # Last 8 of VF3EBRHD8BZ038648
    print(f"Testing downloader with VIN8: {vin8}")
    
    downloader = ServiceBoxDownloader(output_dir=os.path.join(os.getcwd(), "downloads"))
    
    try:
        # We only care if it gets past the search phase
        result = await downloader.download_maintenance_plan(vin8)
        print("Success:", result.get('success'))
        print("Error:", result.get('error'))
        if result.get('success'):
            print("Successfully processed vehicle using VIN8!")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_vin8())
