# ServiceBox API Reference

**Auth Header**: All endpoints require `X-Auth-Token: <your_token>`.

---

### 1. Request Maintenance Plan (Async)
**POST** `/api/maintenance-plan`

Pushes a new VIN extraction job to the background queue.

**Request Body (JSON):**
```json
{
  "vin": "VF3EBRHD8BZ038648",
  "priority": false,
  "force_refresh": false
}
```

**Response (JSON):**
```json
{
  "success": true,
  "job_id": "c05794c7-c363-410b-b5d5-d19092457390",
  "status": "queued",
  "message": "Job added to queue",
  "queue_position": 0
}
```

---

### 2. Check Job Status
**GET** `/api/jobs/{job_id}`

Retrieves the current standing of the job.

**Response (JSON):**
```json
{
  "job_id": "c05794c7-...",
  "status": "processing",  // 'queued', 'processing', 'success', 'error'
  "vin": "VF3EBRHD8BZ038648",
  "error_message": null,
  "result": { ... } // Present if 'success'
}
```

---

### 3. Retrieve Extraction History
**GET** `/api/history?vin=VF3...&limit=50`

Returns the DB history of all extractions, including data like Warranty, LCDV, Recalls.

---

### 4. Direct PDF Download (Proxy)
**GET** `/api/files/{filename}`

If the file is stored in Paperless, the API automatically proxies the stream from Paperless to the user without touching the local disk.

---

### 5. Fetch Dashboard Stats
**GET** `/api/stats`

Returns aggregated stats for the Cockpit (Total Success, Error Count, Live Queue, Active Nodes).
