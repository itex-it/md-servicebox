# ServiceBox API & Downloader

A robust, automated tool to retrieve "Maintenance Plan" (Wartungsplan) PDFs and vehicle data (Warranty, LCDV, Recalls) from the Peugeot/Citroën Service Box website for a given VIN.

**Output Location**: All downloaded PDFs are saved to the `downloads/` directory by default.

## Features
- **Automated PDF Retrieval**: Downloads the official maintenance plan PDF.
- **Data Extraction**: Parses the dashboard to extract Warranty dates, Technical Data (LCDV), and Recall status.
- **History Tracking**: Automatically saves all extractions to a local SQLite database (`servicebox_history.db`) and timestamps PDFs to prevent overwrites.
- **Robustness**: Handles dynamic table layouts and varying data fields automatically.
- **Headless Support**: Fully functional in background mode using modern Chromium headless.
- **API Interface**: Simple REST API (FastAPI) for easy integration.

## Quick Start (Windows)

1.  **Run `install.bat`**:
    -   Double-click to automatically set up the Python environment and install all dependencies.
    -   Requires Python 3.8+ to be installed and in your PATH.

2.  **Run `start_api.bat`**:
    -   Starts the API server at `http://localhost:8000`.
    -   Keep this window open while using the tool.

## Deployment / Transfer

To move this tool to another machine:
1.  Copy the entire folder (excluding `.venv`, `downloads`, and `__pycache__` to save space).
2.  On the new machine, run `install.bat` once.
3.  Ready to use!

## Manual Installation (Advanced)

If you prefer using the command line manually:

1.  **Create Environment**: `python -m venv .venv`
2.  **Activate**: `.venv\Scripts\activate`
3.  **Install Dependencies**: `pip install -r requirements.txt`
4.  **Install Browsers**: `playwright install chromium`
5.  **Run**: `python servicebox_api.py`

## Configuration (`config.json`)

The application is configured via `config.json`. You can change these values without touching the code.

```json
{
    "user_id": "DP92228",
    "password": "YOUR_PASSWORD",
    "login_url": "https://servicebox.peugeot.com/",
    "headless": true, 
    "log_level": "INFO", 
    "output_dir": "downloads",
    "timeout_seconds": 30000,
    "short_timeout_seconds": 5000,
    "auth_token": "SECRET_TOKEN_123"
}
```
*   **headless**: Set to `false` if you want to see the browser window.
*   **timeout_seconds**: Max time (ms) for main operations (default: 30000).
*   **auth_token**: Secret token for API access.

## Usage (API)

**Authentication**: All endpoints require the `auth_token` defined in `config.json`.
*   **Header**: `X-Auth-Token: SECRET_TOKEN_123`
*   **Query Param**: `?token=SECRET_TOKEN_123` (Easy for browser/files)

### Request Data
**POST** `/api/maintenance-plan` (Header: `X-Auth-Token: ...`)
```json
{ "vin": "VF7..." }
```

### Download File
**GET** `/api/files/{filename}?token=SECRET_TOKEN_123`

## Web Dashboard (Cockpit)

The system includes a visual dashboard to monitor activity, view logs, and control the server.

*   **URL**: `http://localhost:8005/` (Redirects to Login)
*   **Login**: Enter the `auth_token` from your `config.json`.

### Features
*   **Live KPIs**: Monitor total downloads, success rates, and last activity.
*   **Search**: Filter history by VIN or status.
*   **System Control**: Restart or Shutdown the server directly from the UI.
*   **Live Logs**: View `servicebox.log` in real-time.

### 3. Response Structure
```json
{
  "success": true,
  "vin": "VF7FCKFVC9A101965",
  "file_path": "C:\\path\\to\\VF7FCKFVC9A101965_Wartungsplan.pdf",
  "vehicle_data": {
    "warranty_details": {
      "Garantiebeginndatum": "27/07/2009",
      "Garantieende": "27/07/2011",
      "Garantieende Korrosion": "27/07/2021"
    },
    "lcdv": {
      "G": "1", "M": "C", "LP": "A3", "..." : "..."
    },
    "recalls": {
      "status": "None",
      "message": "Mit dieser VIN sind keine Überprüfungsaktionen verbunden"
    }
  }
}
```

### Request History
Get all past extractions for a VIN:
**GET** `/api/history/{vin}`

```json
{
  "vin": "VF7...",
  "history": [
    {
      "timestamp": "2023-10-27 10:00:00",
      "file_path": "..._20231027_100000_Wartungsplan.pdf",
      "recall_status": "None",
      "warranty_data": {...}
    }
  ]
}
```

## Architecture & Decisions

### 1. Headless Mode (`--headless=new`)
- **Challenge**: Standard `headless=True` in older Playwright/Chromium versions often disrupted popup handling and redirects on Windows.
- **Solution**: We use the new Chrome headless mode (`--headless=new`). This renders the full browser stack invisibly, ensuring popups and PDF streams behave exactly as they do in headful mode.

### 2. PDF Stream Detection
- **Challenge**: The "Maintenance Plan" is often delivered as a direct binary stream in a popup, not a downloadable file link.
- **Solution**: The script intercepts the popup's request. If the Content-Type is `application/pdf`, it downloads the stream directly. If it renders as HTML (older vehicles), it falls back to `Page.printToPDF`.

### 3. Dynamic Data Extraction
- **Challenge**: Vehicles have different warranty lines (e.g., Paint, Hybrid Battery) and varying LCDV table columns.
- **Solution**: The extractor uses purely structural constraints (finding tables relative to semantic headers like "Garantiebeginn") and iterates all rows/cells dynamically. It does not rely on fixed XPaths or IDs for data values.


## Error Handling & Robustness

The system is designed to handle common failures gracefully:

1.  **Network/Site Issues**:
    -   Implements **timeouts** (e.g., 30s for critical elements).
    -   If the site is slow or down, the API returns `400 Bad Request` with a descriptive message (e.g., "Timeout waiting for 'Wartungspläne'").
2.  **Invalid VINs**:
    -   Detects if the dashboard fails to load.
    -   Returns `success: false` and message "Dashboard not loaded (Invalid VIN?)".
3.  **Popup Failures**:
    -   If the PDF popup doesn't open (e.g., specific vehicle data missing), strict checks prevent the script from hanging.
    -   It captures a debug screenshot (`debug_popup_<VIN>.png`) locally before returning an error.

## Maintenance & Troubleshooting

For a detailed explanation of the system's architecture (Headless mode, PDF streams, Dynamic extraction), please refer to:
**[ADR_001_VehicleDataExtraction.md](ADR_001_VehicleDataExtraction.md)**

### Logging
The system writes detailed logs to **`servicebox.log`**.
- Checks this file if something goes wrong.
- It rotates automatically (max 5MB, keeps last 3 files).

### Common Issues
- **"Invalid Popup URL"**: Requires `--headless=new` (already default). Only occurs if standard `headless=True` is forced on Windows.
- **Empty PDF**: Checks if the VIN has a valid maintenance plan. The script handles "HTML view" vs "Direct Stream" automatically.

## File Structure
- `servicebox_api.py`: FastAPI entry point.
- `servicebox_downloader.py`: Core logic class.
- `config.json`: Configuration file (Credentials, Settings).
- `servicebox.log`: Log file.
- `servicebox_history.db`: SQLite database for history.
- `requirements.txt`: Python package list.
- `install.bat` / `start_api.bat`: Automation scripts.
- `downloads/`: Directory where PDFs are saved.
