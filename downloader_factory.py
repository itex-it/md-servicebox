import logging
from servicebox_downloader import ServiceBoxDownloader
from config_loader import logger

# Placeholder for future downloaders
class DummyDownloader:
    def __init__(self, brand_name):
        self.brand_name = brand_name
        
    async def download_maintenance_plan(self, vin: str):
        logger.warning(f"[{self.brand_name}] Downloader not yet implemented for VIN: {vin}")
        return {
            "success": False,
            "error": f"Scraper for brand '{self.brand_name}' is not yet implemented.",
            "vehicle_data": {}
        }

class DownloaderFactory:
    """
    Routes the extraction job to the correct scraper based on the VIN's WMI (World Manufacturer Identifier).
    """
    
    # Mapping of WMI (first 3 chars of VIN) to brand
    WMI_MAPPING = {
        # PSA / Stellantis (ServiceBox)
        "VR1": "DS", "VF3": "Peugeot", "VR3": "Peugeot",
        "VF7": "Citroen", "VR7": "Citroen",
        "VSX": "Opel", "W0L": "Opel", 
        "1G1": "Chevrolet", "1GC": "Chevrolet", # Used in some older shared platforms or specific regions
        
        # FCA / Stellantis (Future Implementation)
        "ZFA": "Fiat", "ZAR": "Alfa Romeo", "ZAM": "Maserati", "ZHW": "Lamborghini",
        "1C4": "Jeep", "1C3": "Chrysler", "2C4": "Chrysler",
        
        # VW Group (Future Implementation)
        "WVW": "Volkswagen", "WV1": "Volkswagen", "WV2": "Volkswagen", "WVG": "Volkswagen",
        "WAU": "Audi", "TRU": "Audi", 
        "WP0": "Porsche", "WP1": "Porsche",
        "TMB": "Skoda", "VSS": "Seat",
        
        # BMW Group (Future Implementation)
        "WBA": "BMW", "WBS": "BMW", "WBX": "BMW", "WMW": "Mini",
        
        # Mercedes-Benz (Future Implementation)
        "WDB": "Mercedes-Benz", "WDC": "Mercedes-Benz", "WDD": "Mercedes-Benz"
    }
    
    @classmethod
    def get_brand(cls, vin: str) -> str:
        if not vin or len(vin) < 3:
            return "Unknown"
        wmi = vin[:3].upper()
        return cls.WMI_MAPPING.get(wmi, "Unknown")
        
    @classmethod
    def get_downloader(cls, vin: str):
        brand = cls.get_brand(vin)
        logger.info(f"[Factory] Routing VIN {vin} (WMI: {vin[:3]}) -> Recognized Brand: {brand}")
        
        if brand in ["Peugeot", "Citroen", "DS", "Opel", "Chevrolet"]:
            # Uses the existing ServiceBox portal
            return ServiceBoxDownloader()
            
        elif brand in ["Fiat", "Jeep", "Alfa Romeo", "Chrysler"]:
            # Placeholder for FCA eper / technical portals
            return DummyDownloader(brand)
            
        elif brand in ["Volkswagen", "Audi", "Skoda", "Seat", "Porsche"]:
            # Placeholder for erWin portal
            return DummyDownloader(brand)
            
        elif brand in ["BMW", "Mini"]:
            # Placeholder for BMW AOS / ISTA
            return DummyDownloader(brand)
            
        elif brand == "Mercedes-Benz":
            # Placeholder for Mercedes XENTRY / B2B Connect
            return DummyDownloader(brand)
            
        else:
            logger.warning(f"[Factory] Unknown brand for VIN {vin}. Falling back to default ServiceBoxDownloader.")
            # Default fallback for unknown brands just in case they are Stellantis but missing from mapping
            return ServiceBoxDownloader()
