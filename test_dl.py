import asyncio
import os
import sys

# Add path so we can import servicebox modules
sys.path.append(os.getcwd())

import config_loader
from servicebox_downloader import ServiceBoxDownloader

async def main():
    print("Starting download...")
    dl = ServiceBoxDownloader(os.getcwd())
    try:
        res = await dl.download_maintenance_plan('VR1JJEHZRKY091028')
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
