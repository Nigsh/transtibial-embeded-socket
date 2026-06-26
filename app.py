"""
SmartFit | app.py
==================
Flask web server — serves the SmartFit UI and exposes a REST API
that drives the heatmap dashboard.

Run:
    python app.py
Then open:  http://localhost:5000

API endpoints:
    POST /api/analyze      — run full pipeline, return JSON
    GET  /api/faults       — list available fault types
"""

from flask import Flask, render_template_string, request, jsonify
import json
from pipeline import SmartFitPipeline
from pressure_calculator import PatientProfile
from fsr_sensor import FaultType

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML template — white / black / brown theme, red / yellow / green heatmap
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SmartFit — Socket Fitting System</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=Instrument+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
/* ─── RESET & BASE ─── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --white:     #F8F5F0;
  --off-white: #EDE8DF;
  --cream:     #E2D9CC;
  --brown-lt:  #C4A882;
  --brown:     #8B6442;
  --brown-dk:  #5C3D1E;
  --espresso:  #2C1A0E;
  --black:     #0F0A06;
  --green:     #2D7A3A;
  --green-lt:  #4AAD5A;
  --yellow:    #C98A00;
  --yellow-lt: #F5C842;
  --red:       #B52A2A;
  --red-lt:    #E84848;
  --blue:      #2A5FAD;
  --blue-lt:   #5A8FE8;
  --radius:    6px;
  --shadow:    0 2px 12px rgba(44,26,14,0.10);
}

html { scroll-behavior: smooth; }
body {
  background: var(--white);
  color: var(--espresso);
  font-family: 'Instrument Sans', sans-serif;
  font-size: 14px;
  min-height: 100vh;
}

/* ─── LAYOUT ─── */
.page { display: grid; grid-template-rows: auto 1fr; min-height: 100vh; }

header {
  background: var(--black);
  color: var(--white);
  padding: 0 32px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid var(--brown-dk);
}
.logo {
  font-family: 'DM Serif Display', serif;
  font-size: 22px;
  letter-spacing: 0.01em;
  color: var(--brown-lt);
}
.logo span { color: var(--white); }
.header-sub {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--brown-lt);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.main {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 0;
  height: calc(100vh - 56px);
  overflow: hidden;
}

/* ─── SIDEBAR ─── */
.sidebar {
  background: var(--espresso);
  color: var(--off-white);
  padding: 24px 20px;
  overflow-y: auto;
  border-right: 1px solid var(--brown-dk);
}
.sidebar-title {
  font-family: 'DM Serif Display', serif;
  font-size: 18px;
  color: var(--brown-lt);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--brown-dk);
}
.form-section { margin-bottom: 20px; }
.form-section-label {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--brown-lt);
  margin-bottom: 10px;
  display: block;
}
.field { margin-bottom: 12px; }
.field label {
  display: block;
  font-size: 12px;
  color: var(--cream);
  margin-bottom: 4px;
}
.field input, .field select {
  width: 100%;
  background: rgba(255,255,255,0.06);
  border: 1px solid var(--brown-dk);
  border-radius: var(--radius);
  color: var(--white);
  padding: 8px 10px;
  font-size: 13px;
  font-family: 'Instrument Sans', sans-serif;
  outline: none;
  transition: border-color 0.2s;
}
.field input:focus, .field select:focus { border-color: var(--brown-lt); }
.field select option { background: var(--espresso); }
.field input[type=range] {
  padding: 4px 0;
  accent-color: var(--brown-lt);
  cursor: pointer;
}
.range-row { display: flex; align-items: center; gap: 8px; }
.range-row input { flex: 1; }
.range-val {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: var(--brown-lt);
  width: 36px;
  text-align: right;
  flex-shrink: 0;
}

.divider { border: none; border-top: 1px solid var(--brown-dk); margin: 16px 0; }

.btn-analyze {
  width: 100%;
  background: var(--brown);
  color: var(--white);
  border: none;
  border-radius: var(--radius);
  padding: 11px;
  font-family: 'Instrument Sans', sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: background 0.2s, transform 0.1s;
}
.btn-analyze:hover { background: var(--brown-lt); }
.btn-analyze:active { transform: scale(0.98); }
.btn-analyze:disabled { background: var(--brown-dk); cursor: not-allowed; opacity: 0.6; }

/* ─── CONTENT AREA ─── */
.content {
  display: grid;
  grid-template-rows: auto 1fr auto;
  overflow: hidden;
  background: var(--white);
}

/* ─── METRICS BAR ─── */
.metrics-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--cream);
  border-bottom: 1px solid var(--cream);
}
.metric {
  background: var(--white);
  padding: 14px 20px;
}
.metric-label {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--brown);
  margin-bottom: 4px;
}
.metric-value {
  font-family: 'DM Serif Display', serif;
  font-size: 26px;
  color: var(--espresso);
  line-height: 1;
}
.metric-unit { font-size: 12px; color: var(--brown); margin-top: 2px; }
.metric-value.good  { color: var(--green); }
.metric-value.warn  { color: var(--yellow); }
.metric-value.bad   { color: var(--red); }

/* ─── HEATMAP + RECS ─── */
.dashboard {
  display: grid;
  grid-template-columns: 1fr 280px;
  overflow: hidden;
}

.heatmap-panel {
  padding: 20px 24px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.panel-title {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--brown);
  margin-bottom: 14px;
}
.canvas-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--off-white);
  border-radius: var(--radius);
  border: 1px solid var(--cream);
  padding: 12px;
  overflow: hidden;
}
canvas#heatmap {
  max-width: 100%;
  max-height: 100%;
}
.legend {
  display: flex;
  gap: 16px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--brown-dk);
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* ─── RECOMMENDATIONS ─── */
.recs-panel {
  background: var(--off-white);
  border-left: 1px solid var(--cream);
  padding: 20px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.recs-title {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--brown);
  margin-bottom: 4px;
}
.rec-card {
  background: var(--white);
  border-radius: var(--radius);
  border-left: 3px solid var(--cream);
  padding: 10px 12px;
  box-shadow: var(--shadow);
}
.rec-card.critical { border-left-color: var(--red); }
.rec-card.warning  { border-left-color: var(--yellow); }
.rec-card.info     { border-left-color: var(--blue); }
.rec-card.ok       { border-left-color: var(--green); }
.rec-severity {
  font-family: 'DM Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  margin-bottom: 3px;
}
.rec-card.critical .rec-severity { color: var(--red); }
.rec-card.warning  .rec-severity { color: var(--yellow); }
.rec-card.info     .rec-severity { color: var(--blue); }
.rec-card.ok       .rec-severity { color: var(--green); }
.rec-text {
  font-size: 12px;
  color: var(--espresso);
  line-height: 1.45;
  margin-bottom: 4px;
}
.rec-action {
  font-size: 11px;
  font-weight: 600;
  color: var(--brown);
}
.rec-arrow { color: var(--brown-lt); margin-right: 3px; }

/* ─── SENSOR TABLE ─── */
.table-bar {
  background: var(--espresso);
  padding: 0 24px;
  max-height: 180px;
  overflow-y: auto;
}
.sensor-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.sensor-table th {
  font-family: 'DM Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--brown-lt);
  padding: 8px 6px 6px;
  text-align: left;
  position: sticky;
  top: 0;
  background: var(--espresso);
  border-bottom: 1px solid var(--brown-dk);
}
.sensor-table td {
  padding: 5px 6px;
  color: var(--off-white);
  border-bottom: 1px solid rgba(92,61,30,0.3);
  font-family: 'DM Mono', monospace;
}
.sensor-table tr:last-child td { border-bottom: none; }
.status-pill {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 20px;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.status-pill.optimal  { background: rgba(45,122,58,0.25); color: #4AAD5A; }
.status-pill.elevated { background: rgba(201,138,0,0.25); color: #F5C842; }
.status-pill.hotspot  { background: rgba(181,42,42,0.25); color: #E84848; }
.status-pill.low      { background: rgba(42,95,173,0.25); color: #5A8FE8; }

/* ─── EMPTY STATE ─── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--brown-lt);
  gap: 10px;
  text-align: center;
  padding: 40px;
}
.empty-icon {
  font-size: 40px;
  opacity: 0.4;
}
.empty-text {
  font-family: 'DM Serif Display', serif;
  font-size: 18px;
  color: var(--brown);
}
.empty-sub { font-size: 13px; color: var(--brown-lt); max-width: 280px; }

/* ─── LOADING ─── */
.loading-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(15,10,6,0.55);
  z-index: 100;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 14px;
  color: var(--white);
  font-family: 'DM Mono', monospace;
  font-size: 13px;
  letter-spacing: 0.06em;
}
.loading-overlay.active { display: flex; }
.spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--brown-dk);
  border-top-color: var(--brown-lt);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── SCROLLBAR ─── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--brown-dk); border-radius: 3px; }
</style>
</head>
<body>
<div class="page">

<header>
  <div class="logo"><span>Smart</span>Fit</div>
  <div class="header-sub">Transtibial Socket Fitting System · 12 FSR Sensors</div>
</header>

<div class="main">

  <!-- SIDEBAR -->
  <aside class="sidebar">
    <div class="sidebar-title">Patient Parameters</div>

    <div class="form-section">
      <span class="form-section-label">Patient Info</span>
      <div class="field">
        <label>Full Name</label>
        <input type="text" id="f-name" value="Abebe Girma" placeholder="Patient name">
      </div>
      <div class="field">
        <label>Age</label>
        <input type="number" id="f-age" value="35" min="18" max="90">
      </div>
      <div class="field">
        <label>Activity Level</label>
        <select id="f-activity">
          <option value="low">Low</option>
          <option value="moderate" selected>Moderate</option>
          <option value="high">High</option>
        </select>
      </div>
    </div>

    <hr class="divider">

    <div class="form-section">
      <span class="form-section-label">Anthropometrics</span>
      <div class="field">
        <label>Body Weight (kg)</label>
        <div class="range-row">
          <input type="range" id="f-weight" min="40" max="120" value="70" step="1"
                 oninput="document.getElementById('f-weight-v').textContent=this.value">
          <span class="range-val" id="f-weight-v">70</span>
        </div>
      </div>
      <div class="field">
        <label>Residuum Length (cm)</label>
        <div class="range-row">
          <input type="range" id="f-length" min="8" max="22" value="14" step="0.5"
                 oninput="document.getElementById('f-length-v').textContent=this.value">
          <span class="range-val" id="f-length-v">14</span>
        </div>
      </div>
      <div class="field">
        <label>Socket Tightness</label>
        <div class="range-row">
          <input type="range" id="f-tight" min="0.5" max="1.5" value="1.0" step="0.05"
                 oninput="document.getElementById('f-tight-v').textContent=parseFloat(this.value).toFixed(2)">
          <span class="range-val" id="f-tight-v">1.00</span>
        </div>
      </div>
    </div>

    <hr class="divider">

    <div class="form-section">
      <span class="form-section-label">Simulation</span>
      <div class="field">
        <label>Inject Fault (simulates poor fit)</label>
        <select id="f-fault">
          <option value="none">None — Ideal fit</option>
          <option value="tibia">Tibia crest hotspot</option>
          <option value="distal">Distal end overload</option>
          <option value="medial">Medial bony prominence</option>
          <option value="posterior">Posterior slack</option>
          <option value="multi">Multi-zone mismatch</option>
        </select>
      </div>
      <div class="field">
        <label>Sensor Noise Level</label>
        <div class="range-row">
          <input type="range" id="f-noise" min="0" max="0.15" value="0.05" step="0.01"
                 oninput="document.getElementById('f-noise-v').textContent=parseFloat(this.value).toFixed(2)">
          <span class="range-val" id="f-noise-v">0.05</span>
        </div>
      </div>
    </div>

    <button class="btn-analyze" id="btn-run" onclick="runAnalysis()">
      ▶  Run Analysis
    </button>
  </aside>

  <!-- CONTENT -->
  <div class="content">

    <!-- METRICS BAR -->
    <div class="metrics-bar">
      <div class="metric">
        <div class="metric-label">Fit Quality Score</div>
        <div class="metric-value" id="m-fqs">—</div>
        <div class="metric-unit">out of 100</div>
      </div>
      <div class="metric">
        <div class="metric-label">Peak Pressure</div>
        <div class="metric-value" id="m-peak">—</div>
        <div class="metric-unit">kPa</div>
      </div>
      <div class="metric">
        <div class="metric-label">Hotspot Zones</div>
        <div class="metric-value" id="m-hot">—</div>
        <div class="metric-unit">&gt; 150% ideal</div>
      </div>
      <div class="metric">
        <div class="metric-label">Status</div>
        <div class="metric-value" id="m-status" style="font-size:17px;margin-top:5px">—</div>
        <div class="metric-unit" id="m-patient">—</div>
      </div>
    </div>

    <!-- DASHBOARD -->
    <div class="dashboard">
      <div class="heatmap-panel">
        <div class="panel-title">Socket Pressure Heatmap — Unfolded View</div>
        <div class="canvas-wrap" id="canvas-wrap">
          <div class="empty-state" id="empty-state">
            <div class="empty-icon">⬡</div>
            <div class="empty-text">No data yet</div>
            <div class="empty-sub">Enter patient parameters and click Run Analysis to generate the heatmap.</div>
          </div>
          <canvas id="heatmap" style="display:none"></canvas>
        </div>
        <div class="legend">
          <div class="legend-item"><div class="legend-dot" style="background:var(--green-lt)"></div> Optimal (80–120%)</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--yellow-lt)"></div> Elevated (120–150%)</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--red-lt)"></div> Hotspot (&gt;150%)</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--blue-lt)"></div> Low (&lt;80%)</div>
        </div>
      </div>

      <div class="recs-panel">
        <div class="recs-title">Recommendations</div>
        <div id="recs-list">
          <div style="color:var(--brown-lt);font-size:12px;margin-top:8px">
            Run analysis to see adjustment recommendations.
          </div>
        </div>
      </div>
    </div>

    <!-- SENSOR TABLE -->
    <div class="table-bar">
      <table class="sensor-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Sensor Name</th>
            <th>Zone</th>
            <th>Ideal kPa</th>
            <th>Measured kPa</th>
            <th>Ratio</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="sensor-tbody">
          <tr><td colspan="7" style="color:var(--brown-lt);padding:10px 6px">No data — run analysis first.</td></tr>
        </tbody>
      </table>
    </div>

  </div>
</div>
</div>

<!-- LOADING OVERLAY -->
<div class="loading-overlay" id="loading">
  <div class="spinner"></div>
  <span>Simulating sensor readings...</span>
</div>

<script>
let lastData = null;

async function runAnalysis() {
  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  document.getElementById('loading').classList.add('active');

  const payload = {
    name:     document.getElementById('f-name').value || 'Patient',
    age:      parseInt(document.getElementById('f-age').value),
    weight:   parseFloat(document.getElementById('f-weight').value),
    length:   parseFloat(document.getElementById('f-length').value),
    tightness:parseFloat(document.getElementById('f-tight').value),
    activity: document.getElementById('f-activity').value,
    fault:    document.getElementById('f-fault').value,
    noise:    parseFloat(document.getElementById('f-noise').value),
  };

  try {
    const res  = await fetch('/api/analyze', {
      method:  'POST',
      headers: {'Content-Type':'application/json'},
      body:    JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    lastData = data;
    renderDashboard(data);
  } catch(e) {
    alert('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    document.getElementById('loading').classList.remove('active');
  }
}

function renderDashboard(d) {
  // Metrics
  const fqs   = d.fit_quality_score;
  const fqsEl = document.getElementById('m-fqs');
  fqsEl.textContent = fqs;
  fqsEl.className   = 'metric-value ' + (fqs>=80?'good':fqs>=60?'warn':'bad');

  const peak   = d.peak_pressure_kpa;
  const peakEl = document.getElementById('m-peak');
  peakEl.textContent = peak.toFixed(1);
  peakEl.className   = 'metric-value ' + (peak>500?'bad':peak>300?'warn':'good');

  const hot   = d.hotspot_count;
  const hotEl = document.getElementById('m-hot');
  hotEl.textContent = hot;
  hotEl.className   = 'metric-value ' + (hot>2?'bad':hot>0?'warn':'good');

  const stEl = document.getElementById('m-status');
  stEl.textContent  = d.status_label;
  stEl.style.color  = d.status_color;
  stEl.className    = 'metric-value';
  document.getElementById('m-patient').textContent = d.patient_name;

  // Heatmap
  document.getElementById('empty-state').style.display = 'none';
  const canvas = document.getElementById('heatmap');
  canvas.style.display = 'block';
  drawHeatmap(canvas, d.sensors);

  // Recommendations
  const recEl = document.getElementById('recs-list');
  recEl.innerHTML = d.recommendations.map(r => `
    <div class="rec-card ${r.severity}">
      <div class="rec-severity">${r.severity}</div>
      <div class="rec-text">${r.text}</div>
      <div class="rec-action"><span class="rec-arrow">→</span>${r.action}</div>
    </div>
  `).join('');

  // Table
  const tbody = document.getElementById('sensor-tbody');
  tbody.innerHTML = d.sensors.map(s => `
    <tr>
      <td>${s.id}</td>
      <td>${s.name}</td>
      <td>${s.zone}</td>
      <td>${s.ideal_kpa.toFixed(1)}</td>
      <td>${s.measured_kpa.toFixed(1)}</td>
      <td>${s.ratio.toFixed(2)}</td>
      <td><span class="status-pill ${s.status}">${s.status}</span></td>
    </tr>
  `).join('');
}

function drawHeatmap(canvas, sensors) {
  const wrap  = document.getElementById('canvas-wrap');
  const W     = Math.min(wrap.clientWidth  - 24, 500);
  const H     = Math.min(wrap.clientHeight - 24, 360);
  canvas.width  = W;
  canvas.height = H;
  const ctx   = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);

  // Background
  ctx.fillStyle = '#EDE8DF';
  roundRect(ctx, 0, 0, W, H, 8);
  ctx.fill();

  // Socket outline (stylised unfolded socket)
  ctx.strokeStyle = '#C4A882';
  ctx.lineWidth   = 1.5;
  ctx.setLineDash([4,4]);
  roundRect(ctx, 10, 10, W-20, H-20, 6);
  ctx.stroke();
  ctx.setLineDash([]);

  // Zone labels
  ctx.fillStyle = '#8B6442';
  ctx.font = '9px DM Mono, monospace';
  ctx.textAlign = 'center';
  ctx.fillText('ANTERIOR', W/2, 22);
  ctx.fillText('DISTAL', W/2, H-8);
  ctx.save(); ctx.translate(20, H/2); ctx.rotate(-Math.PI/2);
  ctx.fillText('MEDIAL', 0, 0); ctx.restore();
  ctx.save(); ctx.translate(W-14, H/2); ctx.rotate(Math.PI/2);
  ctx.fillText('LATERAL', 0, 0); ctx.restore();

  // Draw sensors
  sensors.forEach(s => {
    const x = 30 + s.canvas_x * (W - 60);
    const y = 30 + s.canvas_y * (H - 60);
    const col  = statusColor(s.status);
    const r    = 14 + Math.min(10, (s.ratio - 0.5) * 6);

    // Glow
    const grd = ctx.createRadialGradient(x, y, 0, x, y, r + 10);
    grd.addColorStop(0, col + '55');
    grd.addColorStop(1, col + '00');
    ctx.fillStyle = grd;
    ctx.beginPath(); ctx.arc(x, y, r + 10, 0, Math.PI*2); ctx.fill();

    // Circle
    ctx.fillStyle = col;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2); ctx.fill();

    // Border
    ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.lineWidth   = 1.5;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2); ctx.stroke();

    // Sensor number
    ctx.fillStyle   = '#fff';
    ctx.font        = `bold ${r > 18 ? 11 : 9}px Instrument Sans, sans-serif`;
    ctx.textAlign   = 'center';
    ctx.textBaseline= 'middle';
    ctx.fillText(s.id + 1, x, y);

    // kPa label
    ctx.fillStyle   = '#2C1A0E';
    ctx.font        = '8px DM Mono, monospace';
    ctx.textBaseline= 'top';
    ctx.fillText(s.measured_kpa.toFixed(0) + ' kPa', x, y + r + 3);
  });

  ctx.textBaseline = 'alphabetic';
}

function statusColor(status) {
  return {
    optimal:  '#2D7A3A',
    elevated: '#C98A00',
    hotspot:  '#B52A2A',
    low:      '#2A5FAD',
  }[status] || '#8B6442';
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r, y);
  ctx.lineTo(x+w-r, y); ctx.quadraticCurveTo(x+w, y, x+w, y+r);
  ctx.lineTo(x+w, y+h-r); ctx.quadraticCurveTo(x+w, y+h, x+w-r, y+h);
  ctx.lineTo(x+r, y+h); ctx.quadraticCurveTo(x, y+h, x, y+h-r);
  ctx.lineTo(x, y+r); ctx.quadraticCurveTo(x, y, x+r, y);
  ctx.closePath();
}

window.addEventListener('resize', () => {
  if (lastData) drawHeatmap(document.getElementById('heatmap'), lastData.sensors);
});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        body = request.get_json()
        patient = PatientProfile(
            name              = body.get("name", "Patient"),
            age               = int(body.get("age", 35)),
            body_weight_kg    = float(body["weight"]),
            residuum_length_cm= float(body["length"]),
            socket_tightness  = float(body["tightness"]),
            activity_level    = body.get("activity", "moderate"),
        )
        fault  = FaultType(body.get("fault", "none"))
        noise  = float(body.get("noise", 0.05))

        pipeline = SmartFitPipeline(patient, fault=fault, noise=noise, seed=None)
        result   = pipeline.run(n_samples=10)
        return jsonify(result.to_dict())

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/faults")
def faults():
    return jsonify([{"value": f.value, "label": f.value.title()} for f in FaultType])


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n  SmartFit Socket Fitting System")
    print("  ─────────────────────────────────")
    print("  Open your browser at:  http://localhost:5000\n")
    app.run(debug=True, port=5000)
