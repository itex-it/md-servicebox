import asyncio
import os
import json
from downloader_factory import DownloaderFactory
import pdf_parser

async def main():
    vin = 'VR1UJZKWZPW124195'
    print(f"Downloading {vin}...")
    
    downloader = DownloaderFactory.get_downloader(vin)
    print(f"Using downloader: {type(downloader)}")
    
    result = await downloader.download_maintenance_plan(vin)
    print("Download result:")
    print(json.dumps(result, indent=2))
    
    if result.get('success') and result.get('file_path'):
        pdf_path = result['file_path']
        print(f"Parsing PDF at {pdf_path}...")
        
        services = pdf_parser.extract_maintenance_services(pdf_path)
        print("--- EXTRACTED DATA ---")
        print(json.dumps(services, indent=2))
        
if __name__ == "__main__":
    asyncio.run(main())
