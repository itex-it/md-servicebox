import os
import sys

# Füge aktuellen Pfad zum Python Path hinzu, damit Module gefunden werden
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db
from models import VehicleHistory, Vehicle
from paperless_client import paperless_client
from job_manager import _extract_fuel_from_paperless

def main():
    init_db()
    print("Starte Backfill für Energy Types...")
    if not paperless_client.enabled:
        print("Paperless ist nicht aktiviert. Abbruch.")
        return

    with SessionLocal() as db:
        # Finde alle Fahrzeuge ohne Energy Type
        vehicles = db.query(Vehicle).filter(Vehicle.energy_type == None).all()
        print(f"Gefundene Fahrzeuge ohne Energy Type: {len(vehicles)}")
        
        updated = 0
        for v in vehicles:
            if not v.file_path or not v.file_path.startswith("paperless:"):
                continue
                
            doc_id_str = v.file_path.split(":")[1]
            if doc_id_str == "PROCESSING_IN_PAPERLESS" or doc_id_str == "OFFLINE" or not doc_id_str.isdigit():
                continue
                
            doc_id = int(doc_id_str)
            fuel = _extract_fuel_from_paperless(doc_id)
            if fuel:
                print(f"[{v.vin}] Treibstoff erkannt: {fuel}")
                v.energy_type = fuel
                db.query(VehicleHistory).filter(VehicleHistory.vin == v.vin, VehicleHistory.file_path == v.file_path).update({"energy_type": fuel})
                updated += 1
            else:
                print(f"[{v.vin}] Kein Treibstoff im OCR Text gefunden.")
                
            db.commit()
            
        print(f"Fertig! {updated} Fahrzeuge aktualisiert.")

if __name__ == "__main__":
    main()
