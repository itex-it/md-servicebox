import database
import json

vins = ['VR1UJZKWZPW124195', 'VR1FCYHZ3S1020847']

for vin in vins:
    print(f"--- VIN: {vin} ---")
    history = database.get_history(vin=vin, limit=1)
    if history:
        record = history[0]
        print(f"File Path: {record.get('file_path')}")
        print(f"Recall Message: {row['recall_message'] if 'recall_message' in dir() else record.get('recall_message')}")
        print("Recalls Data:")
        print(json.dumps(record.get('recalls_data', {}), indent=2))
        print("LCDV:")
        print(json.dumps(record.get('lcdv_data', {}), indent=2))
        print("Warranty:")
        print(json.dumps(record.get('warranty_data', {}), indent=2))
    else:
        print("No history found in DB.")
