# ServiceBox API Reference

**POST** `/api/maintenance-plan`

Allows you to request the PDF download and data extraction for a specific VIN.

**Request Body (JSON):**
```json
{
  "vin": "VF3EBRHD8BZ038648"
}
```

**Response (JSON):**
```json
{
  "success": true,
  "vin": "VF3EBRHD8BZ038648",
  "file_path": "C:\\path\\to\\VF3EBRHD8BZ038648_Wartungsplan.pdf",
  "download_url": "/api/files/VF3EBRHD8BZ038648_Wartungsplan.pdf",
  "duration_seconds": 23.5,
  "vehicle_data": {
    "warranty_details": {
      "Garantiebeginndatum": "05/07/2011",
      "Garantieende": "05/07/2013"
    },
    "lcdv": {
      "G": "1",
      "M": "P",
      "..." : "..."
    },
    "recalls": {
      "status": "None",
      "message": "Mit dieser VIN sind keine Überprüfungsaktionen verbunden"
    }
  }
}
```
*Note: Returns HTTP 400 if the download fails.*

---

### 2. Download File

**GET** `/api/files/{filename}`

Direct link to download the generated PDF file. The filename is provided in the response of the previous call.

---

## Example Usage with Curl

```bash
curl -X POST "http://localhost:8000/api/maintenance-plan" ^
     -H "Content-Type: application/json" ^
     -d "{\"vin\": \"VF3EBRHD8BZ038648\"}"
```
