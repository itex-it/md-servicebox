// AUTH & CONFIG
const TOKEN = localStorage.getItem('sb_token');
if (!TOKEN) window.location.href = '/static/login.html';

const API_HEADERS = { 'X-Auth-Token': TOKEN };

// INITIAL LOAD
document.addEventListener('DOMContentLoaded', () => {
    refreshAll();
    // Auto-refresh logs and history every 5s
    setInterval(() => {
        fetchLogs();
        fetchHistory(); // Auto-refresh history
    }, 5000);
});

async function fetchStats() {
    try {
        const res = await fetch('/api/stats', { headers: API_HEADERS });
        if (res.status === 401) logout();
        const data = await res.json();

        document.getElementById('kpi-total').innerText = data.total_downloads;
        document.getElementById('kpi-last').innerText = new Date(data.last_active + "Z").toLocaleString(); // Fix Timezone by assuming UTC
        document.getElementById('kpi-success').innerText = data.success_rate + "%";

        // Active Tasks
        const activeCount = data.active_tasks || 0;
        document.querySelector('.card:nth-child(4) .kpi-value').innerText = activeCount;
        document.querySelector('.card:nth-child(4) .kpi-sub').innerText = activeCount > 0 ? "Processing..." : "Idle";

    } catch (e) {
        showClientError("Stats Error: " + e.message);
    }
}

function showClientError(msg) {
    const errDiv = document.getElementById('client-errors');
    if (errDiv) {
        const ts = new Date().toLocaleTimeString();
        errDiv.innerHTML += `<div>[${ts}] ${msg}</div>`;
        errDiv.style.display = 'block';
    }
    console.error(msg);
}

async function fetchHistory() {
    const query = document.getElementById('vinSearch').value;
    let url = '/api/history?limit=25'; // Fixed limit for now
    if (query) url += `&search=${encodeURIComponent(query)}`;

    try {
        const res = await fetch(url, { headers: API_HEADERS });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();

        const tbody = document.querySelector('#historyTable tbody');
        tbody.innerHTML = '';

        if (!data.history || !Array.isArray(data.history)) return;

        data.history.forEach(row => {
            try {
                const tr = document.createElement('tr');

                // Date Parsing (Fix Timezone)
                let dateStr = 'Unknown';
                if (row.timestamp) {
                    try {
                        const dateObj = new Date(row.timestamp.replace(' ', 'T') + "Z");
                        dateStr = dateObj.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' }) +
                            ' <span style="color:#666">' + dateObj.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) + '</span>';
                    } catch (e) { dateStr = row.timestamp; }
                }

                // Filename
                const filename = row.file_path ? row.file_path.split(/[\\/]/).pop() : null;

                // Data Parsing
                let warranty = {};
                let recalls = { status: 'Unknown', message: '', details: [] };
                let lcdv = {};

                try { warranty = typeof row.warranty_data === 'string' ? JSON.parse(row.warranty_data) : row.warranty_data || {}; } catch (e) { }
                try { recalls = typeof row.recall_message === 'string' ? (row.recall_message.startsWith('{') ? JSON.parse(row.recall_message) : { message: row.recall_message }) : { message: (typeof row.recall_message === 'string' ? row.recall_message : '') }; } catch (e) { }
                try { lcdv = typeof row.lcdv_data === 'string' ? JSON.parse(row.lcdv_data) : row.lcdv_data || {}; } catch (e) { }

                // --- Brand Logic ---
                let brandBadge = '<span style="background:#444; color:#fff; padding:2px 6px; border-radius:4px; font-size:0.8em">?</span>';
                if (row.vin) {
                    const vin = row.vin.toUpperCase();
                    if (vin.startsWith('VF3')) { brandBadge = '<span style="background:#003399; color:#fff; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em">PEUGEOT</span>'; }
                    else if (vin.startsWith('VF7')) { brandBadge = '<span style="background:#DB0020; color:#fff; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em">CITROEN</span>'; }
                    else if (vin.startsWith('W0V')) { brandBadge = '<span style="background:#FFC800; color:#000; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em">OPEL</span>'; }
                    else if (vin.startsWith('VR3')) { brandBadge = '<span style="background:#1e1e1e; border:1px solid #c8a45e; color:#c8a45e; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.8em">DS</span>'; }
                }

                // --- Vehicle Info Logic (Model & Plate) ---
                const plateKeys = ['Kennzeichen', 'Amtl. Kennzeichen', 'Immatriculation', 'Plate', 'Registration'];
                const modelKeys = ['Modell', 'Model', 'Baureihe', 'Vehicle Type'];

                const findValue = (obj, keys) => {
                    if (!obj) return null;
                    for (const k of Object.keys(obj)) {
                        if (keys.some(pk => k.toLowerCase().includes(pk.toLowerCase()))) {
                            const val = obj[k];
                            if (val && typeof val === 'string' && !val.match(/^\d{2}[\/.]\d{2}[\/.]\d{4}/)) return val;
                        }
                    }
                    return null;
                };

                let plate = findValue(warranty, plateKeys) || findValue(lcdv, plateKeys) || '';
                let model = findValue(warranty, modelKeys) || findValue(lcdv, modelKeys) || (lcdv ? lcdv.Engine : '') || '';

                const plateDisplay = plate ? `<span style="border:1px solid #fff; color:#000; background:#fff; padding:0 4px; border-radius:2px; font-weight:bold; margin-left:8px; font-family:sans-serif; font-size:0.9em">${plate}</span>` : '';
                const modelDisplay = model ? `<div style="font-size:0.8em; color:#bbb">${model}</div>` : '';


                // --- LED LOGIC ---
                const ledStyle = "display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:middle;";

                // 1. Status LED
                let statusColor = '#555';
                if (row.status === 'Success') statusColor = '#03dac6';
                else if (row.status === 'Failed') statusColor = '#cf6679';

                let statusLed = `<span style="${ledStyle} background-color:${statusColor}; box-shadow:0 0 4px ${statusColor}" title="Extraction Status: ${row.status || 'Unknown'}"></span>`;

                // 2. Recall LED & Count
                let recallColor = '#03dac6'; // Default Green (Safe)
                let recallTitle = 'No Recalls';
                let recallCount = 0;

                if (recalls && recalls.details && Array.isArray(recalls.details)) {
                    recalls.details.forEach(r => {
                        if (r.status === 'Open' || r.status === 'Unknown') recallCount++;
                    });
                } else if (recalls && recalls.message && /Rückruf|Recall/i.test(recalls.message)) {
                    recallCount = 1; // Fallback
                }

                if ((recalls && recalls.status === 'Active') || recallCount > 0) {
                    recallColor = '#cf6679'; // Red (Danger)
                    recallTitle = `⚠ ACTIVE RECALLS: ${recallCount}`;
                } else if ((!recalls || !recalls.message) && (recalls && recalls.status !== 'None')) {
                    recallColor = '#555'; // Unknown
                    recallTitle = 'Recall Status Unknown';
                }

                let recallLabel = 'Recall';
                if (recallCount > 0) recallLabel += ` <span style="background:#cf6679; color:white; padding:0 4px; border-radius:8px; font-size:0.8em">${recallCount}</span>`;

                let recallLed = `<span style="${ledStyle} background-color:${recallColor}; box-shadow:0 0 4px ${recallColor}" title="${recallTitle}"></span>`;

                // 3. Warranty LED
                let warrantyColor = '#555'; // Default Grey
                let warrantyTitle = 'Warranty Unknown';
                if (warranty && warranty.Garantieende) {
                    warrantyTitle = `Warranty Ends: ${warranty.Garantieende}`;
                    const endParts = warranty.Garantieende.split('/');
                    if (endParts.length === 3) {
                        const endDate = new Date(`${endParts[2]}-${endParts[1]}-${endParts[0]}`);
                        if (endDate < new Date()) {
                            warrantyColor = '#cf6679'; // Expired
                            warrantyTitle += ' (EXPIRED)';
                        } else {
                            warrantyColor = '#03dac6'; // Valid
                            warrantyTitle += ' (Active)';
                        }
                    }
                }
                let warrantyLed = `<span style="${ledStyle} background-color:${warrantyColor}; box-shadow:0 0 4px ${warrantyColor}" title="${warrantyTitle}"></span>`;


                tr.innerHTML = `
                            <td style="white-space:nowrap">${statusLed} ${dateStr}</td>
                            <td>
                                <div style="display:flex; align-items:center; margin-bottom:2px">
                                    ${brandBadge} ${plateDisplay}
                                </div>
                                <div style="font-family:monospace; font-weight:bold; color:var(--accent-color); font-size:1.05em">${row.vin || 'UNKNOWN'}</div>
                                ${modelDisplay}
                            </td>
                            <td>
                                 <div style="display:flex; gap:15px; align-items:center;">
                                    <div title="${recallTitle}">
                                        ${recallLed} <span style="font-size:0.85em; color:#bbb">${recallLabel}</span>
                                    </div>
                                    <div title="${warrantyTitle}">
                                        ${warrantyLed} <span style="font-size:0.85em; color:#bbb">Warranty</span>
                                    </div>
                                 </div>
                            </td>
                            <td style="text-align:right">
                                ${filename ? `<a href="/api/files/${filename}?token=${TOKEN}" target="_blank" class="btn btn-small btn-primary" style="text-decoration:none">⬇ PDF</a>` : ''}
                            </td>
                        `;
                tbody.appendChild(tr);
            } catch (rowErr) {
                showClientError("Row Render Error: " + rowErr.message + " (VIN: " + row.vin + ")");
            }
        });
    } catch (e) {
        showClientError("History Fetch Error: " + e.message);
    }
}

async function fetchLogs() {
    try {
        const res = await fetch('/api/logs?lines=50', { headers: API_HEADERS });
        const data = await res.json();

        const term = document.getElementById('logTerminal');
        term.innerHTML = '';

        data.logs.forEach(line => {
            const div = document.createElement('div');
            div.className = 'log-entry';

            if (line.includes('[INFO]')) div.classList.add('log-info');
            else if (line.includes('WARNING')) div.classList.add('log-warn');
            else if (line.includes('ERROR')) div.classList.add('log-error');

            div.innerText = line;
            term.appendChild(div);
        });

        // Auto-scroll if near bottom
        term.scrollTop = term.scrollHeight;
    } catch (e) {
        showClientError("Log Fetch Error: " + e.message);
    }
}

// Functions called by HTML buttons
function refreshAll() {
    fetchStats();
    fetchHistory();
    fetchLogs();
    document.getElementById('vinSearch').value = '';
}

async function apiAction(action) {
    if (!confirm(`Are you sure you want to ${action} the server?`)) return;
    try {
        await fetch(`/api/system/${action}`, { method: 'POST', headers: API_HEADERS });
        alert(`Server ${action} initiated.`);
    } catch (e) {
        alert("Action failed: " + e);
    }
}

function logout() {
    localStorage.removeItem('sb_token');
    window.location.href = '/static/login.html';
}

function searchHistory() {
    fetchHistory();
}
