// EvoHunter Evolution Dashboard — Canvas charts + strategy controls

const COLORS = {
  skill: 'oklch(0.42 0.09 195)',       // blue
  experience: 'oklch(0.52 0.12 150)',   // green
  salary: 'oklch(0.56 0.16 38)',        // amber
  location: 'oklch(0.45 0.1 290)',      // purple
  seniority: 'oklch(0.53 0.16 28)',     // red
};

const EVENT_COLORS = {
  reply_positive: 'oklch(0.52 0.12 150)',
  interview_passed: 'oklch(0.45 0.1 160)',
  interview_failed: 'oklch(0.53 0.16 28)',
  salary_mismatch: 'oklch(0.62 0.12 75)',
  location_mismatch: 'oklch(0.55 0.08 50)',
  no_reply: 'oklch(0.5 0.02 260)',
};

const DIMS = ['skill', 'experience', 'salary', 'location', 'seniority'];
const DIM_LABELS = {
  skill: 'Skill',
  experience: 'Experience',
  salary: 'Salary',
  location: 'Location',
  seniority: 'Seniority',
};
const STATUS_COLORS = {
  stable: 'oklch(0.52 0.12 150)',
  converging: 'oklch(0.62 0.12 75)',
  adjusting: 'oklch(0.53 0.16 28)',
  no_feedback: 'oklch(0.5 0.02 260)',
  no_data: 'oklch(0.7 0.02 260)',
};

let visibility = { skill: true, experience: true, salary: true, location: true, seniority: true };
let evolutionData = null;

// ═══════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════

async function init() {
  await loadData();
  renderGauge();
  renderRiver();
  renderPulse();
  renderSnapshots();
  renderOverview();
  initLegend();
  initStrategyForm();
  // Auto-refresh every 30s
  setInterval(async () => { await loadData(); renderAll(); }, 30000);
}

async function loadData() {
  try {
    const res = await fetch('/api/evolution/data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ db_path: getDbPath() }),
    });
    evolutionData = await res.json();
  } catch (e) {
    console.error('Failed to load evolution data', e);
    evolutionData = { generations: [], feedback_summary: {}, current_strategy: {} };
  }
}

function getDbPath() {
  // Share db_path with workbench if set
  try { return localStorage.getItem('evohunter_db_path') || '.evohunter/workbench.db'; }
  catch { return '.evohunter/workbench.db'; }
}

function renderAll() {
  renderGauge();
  renderRiver();
  renderPulse();
  renderSnapshots();
  renderOverview();
}

// ═══════════════════════════════════════════════════════════════
// 1. Convergence Gauge
// ═══════════════════════════════════════════════════════════════

function renderGauge() {
  const canvas = document.getElementById('gauge-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H - 10;
  const r = Math.min(cx - 10, cy - 5);

  ctx.clearRect(0, 0, W, H);

  // Arc segments
  const segments = [
    { start: Math.PI, end: Math.PI * 1.33, color: STATUS_COLORS.stable, label: 'stable' },
    { start: Math.PI * 1.33, end: Math.PI * 1.67, color: STATUS_COLORS.converging, label: 'converging' },
    { start: Math.PI * 1.67, end: Math.PI * 2, color: STATUS_COLORS.adjusting, label: 'adjusting' },
  ];

  const arcW = 14;
  for (const seg of segments) {
    ctx.beginPath();
    ctx.arc(cx, cy, r, seg.start, seg.end);
    ctx.lineWidth = arcW;
    ctx.strokeStyle = seg.color;
    ctx.lineCap = 'butt';
    ctx.stroke();
  }

  // Needle
  const lastGen = getLastGeneration();
  let angle = Math.PI * 1.5; // default: converging
  const conv = lastGen ? lastGen.convergence : 'no_data';
  if (conv === 'stable') angle = Math.PI * 1.1;
  else if (conv === 'converging') angle = Math.PI * 1.5;
  else if (conv === 'adjusting') angle = Math.PI * 1.9;

  const needleLen = r - arcW - 4;
  const nx = cx + Math.cos(angle) * needleLen;
  const ny = cy + Math.sin(angle) * needleLen;

  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(nx, ny);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = 'oklch(0.2 0.01 260)';
  ctx.lineCap = 'round';
  ctx.stroke();

  // Center dot
  ctx.beginPath();
  ctx.arc(cx, cy, 5, 0, Math.PI * 2);
  ctx.fillStyle = 'oklch(0.2 0.01 260)';
  ctx.fill();

  // Label
  const label = document.getElementById('gauge-label');
  const mag = lastGen ? lastGen.change_magnitude.toFixed(4) : '—';
  label.textContent = `${conv.replace('_', ' ')} · Δ${mag}`;
}

function getLastGeneration() {
  if (!evolutionData || !evolutionData.generations.length) return null;
  return evolutionData.generations[evolutionData.generations.length - 1];
}

// ═══════════════════════════════════════════════════════════════
// 2. Weight Evolution River
// ═══════════════════════════════════════════════════════════════

function renderRiver() {
  const canvas = document.getElementById('river-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const pad = { top: 24, right: 40, bottom: 40, left: 48 };
  const pw = W - pad.left - pad.right;
  const ph = H - pad.top - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  const gens = evolutionData.generations;
  if (gens.length < 1) {
    ctx.fillStyle = 'oklch(0.48 0.01 260)';
    ctx.font = '14px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('No evolution data yet', W / 2, H / 2);
    return;
  }

  // Grid
  ctx.strokeStyle = 'oklch(0.88 0.005 260)';
  ctx.lineWidth = 1;
  const gridLines = 5;
  for (let i = 0; i <= gridLines; i++) {
    const y = pad.top + (ph / gridLines) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W - pad.right, y);
    ctx.stroke();
  }

  // Y axis labels
  ctx.fillStyle = 'oklch(0.48 0.01 260)';
  ctx.font = '10px system-ui';
  ctx.textAlign = 'right';
  for (let i = 0; i <= gridLines; i++) {
    const v = 1 - i / gridLines;
    const y = pad.top + (ph / gridLines) * i;
    ctx.fillText(v.toFixed(1), pad.left - 6, y + 4);
  }

  // X axis labels
  ctx.textAlign = 'center';
  const maxLabels = Math.min(gens.length, 10);
  const step = Math.max(1, Math.floor((gens.length - 1) / Math.max(maxLabels - 1, 1)));
  for (let i = 0; i < gens.length; i += step) {
    const x = pad.left + (pw / Math.max(gens.length - 1, 1)) * i;
    ctx.fillText(`Gen ${gens[i].generation}`, x, H - pad.bottom + 16);
    // tick
    ctx.beginPath();
    ctx.moveTo(x, H - pad.bottom);
    ctx.lineTo(x, H - pad.bottom + 4);
    ctx.strokeStyle = 'oklch(0.88 0.005 260)';
    ctx.stroke();
  }

  // Dashed baseline at y = 0.2
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = 'oklch(0.7 0.01 260)';
  ctx.beginPath();
  const baseY = pad.top + ph * 0.8;
  ctx.moveTo(pad.left, baseY);
  ctx.lineTo(W - pad.right, baseY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Draw lines
  for (const dim of DIMS) {
    if (!visibility[dim]) continue;
    ctx.beginPath();
    ctx.strokeStyle = COLORS[dim];
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    for (let i = 0; i < gens.length; i++) {
      const w = gens[i].weights[dim] || 0.2;
      const x = pad.left + (pw / Math.max(gens.length - 1, 1)) * i;
      const y = pad.top + ph * (1 - w);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Dot at last point
    if (gens.length > 0) {
      const last = gens[gens.length - 1];
      const w = last.weights[dim] || 0.2;
      const lx = pad.left + (pw / Math.max(gens.length - 1, 1)) * (gens.length - 1);
      const ly = pad.top + ph * (1 - w);
      ctx.beginPath();
      ctx.arc(lx, ly, 4, 0, Math.PI * 2);
      ctx.fillStyle = COLORS[dim];
      ctx.fill();
    }
  }

  // Hover interaction
  canvas.onmousemove = function (e) {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const tooltip = document.getElementById('river-tooltip');

    if (gens.length < 2) { tooltip.hidden = true; return; }

    const genIdx = Math.round(((mx - pad.left) / pw) * (gens.length - 1));
    if (genIdx < 0 || genIdx >= gens.length) { tooltip.hidden = true; return; }

    const gen = gens[genIdx];
    const cx = pad.left + (pw / Math.max(gens.length - 1, 1)) * genIdx;

    let html = `<b>Gen ${gen.generation}</b><br>`;
    for (const dim of DIMS) {
      html += `<span style="color:${COLORS[dim]}">${DIM_LABELS[dim]}: ${gen.weights[dim].toFixed(3)}</span><br>`;
    }
    html += `Δ ${gen.change_magnitude.toFixed(4)} · ${gen.convergence}`;

    tooltip.innerHTML = html;
    tooltip.hidden = false;
    tooltip.style.left = cx + 'px';
    tooltip.style.top = (rect.height * 0.15) + 'px';
  };

  canvas.onmouseleave = function () {
    document.getElementById('river-tooltip').hidden = true;
  };
}

function initLegend() {
  const container = document.getElementById('river-legend');
  container.innerHTML = '';
  for (const dim of DIMS) {
    const item = document.createElement('span');
    item.className = 'legend-item';
    item.innerHTML = `<span class="legend-swatch" style="background:${COLORS[dim]}"></span>${DIM_LABELS[dim]}`;
    item.onclick = function () {
      visibility[dim] = !visibility[dim];
      item.classList.toggle('dimmed', !visibility[dim]);
      renderRiver();
    };
    container.appendChild(item);
  }
}

// ═══════════════════════════════════════════════════════════════
// 3. Feedback Pulse
// ═══════════════════════════════════════════════════════════════

function renderPulse() {
  const canvas = document.getElementById('pulse-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const pad = { top: 16, right: 20, bottom: 16, left: 110 };
  const pw = W - pad.left - pad.right;
  const ph = H - pad.top - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  const summary = evolutionData.feedback_summary || {};
  const entries = Object.entries(summary);
  if (entries.length === 0) {
    ctx.fillStyle = 'oklch(0.48 0.01 260)';
    ctx.font = '13px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('No feedback events recorded', W / 2, H / 2);
    return;
  }

  entries.sort((a, b) => b[1] - a[1]);
  const maxCount = entries[0][1];
  const barH = Math.min(28, (ph / entries.length) - 6);

  for (let i = 0; i < entries.length; i++) {
    const [eventType, count] = entries[i];
    const barW = (count / maxCount) * pw;
    const y = pad.top + (ph / entries.length) * i + ((ph / entries.length) - barH) / 2;

    // Label
    ctx.fillStyle = 'oklch(0.35 0.01 260)';
    ctx.font = '11px system-ui';
    ctx.textAlign = 'right';
    ctx.fillText(eventType.replace(/_/g, ' '), pad.left - 6, y + barH / 2 + 4);

    // Bar
    const color = EVENT_COLORS[eventType] || 'oklch(0.55 0.02 260)';
    ctx.fillStyle = color;
    roundRect(ctx, pad.left, y, barW, barH, 3);
    ctx.fill();

    // Count
    ctx.fillStyle = 'oklch(0.25 0.01 260)';
    ctx.font = 'bold 11px system-ui';
    ctx.textAlign = 'left';
    ctx.fillText(String(count), pad.left + barW + 8, y + barH / 2 + 4);
  }
}

// ═══════════════════════════════════════════════════════════════
// 4. Generation Overview
// ═══════════════════════════════════════════════════════════════

function renderOverview() {
  const lastGen = getLastGeneration();
  const totalEvents = Object.values(evolutionData.feedback_summary || {}).reduce((a, b) => a + b, 0);
  const strategy = evolutionData.current_strategy || {};

  document.getElementById('ov-generation').textContent = lastGen ? `Gen ${lastGen.generation}` : '—';
  document.getElementById('ov-events').textContent = String(totalEvents);
  document.getElementById('ov-magnitude').textContent = lastGen ? lastGen.change_magnitude.toFixed(4) : '—';
  document.getElementById('ov-strategy').textContent = strategy.strategy || 'balanced';

  const conv = document.getElementById('ov-convergence');
  conv.textContent = lastGen ? lastGen.convergence.replace(/_/g, ' ') : 'no data';
  conv.dataset.status = lastGen ? lastGen.convergence : 'no_data';

  document.getElementById('ov-time').textContent = lastGen && lastGen.created_at
    ? lastGen.created_at.slice(0, 16).replace('T', ' ')
    : '—';
}

// ═══════════════════════════════════════════════════════════════
// 5. Generation Snapshots
// ═══════════════════════════════════════════════════════════════

function renderSnapshots() {
  const container = document.getElementById('snapshot-timeline');
  const gens = evolutionData.generations;

  if (gens.length === 0 || (gens.length === 1 && gens[0].convergence === 'no_data')) {
    container.innerHTML = '<p class="empty-state">No evolution data yet. Run a workflow with feedback to see generations.</p>';
    return;
  }

  container.innerHTML = '';
  for (const gen of gens) {
    const card = document.createElement('div');
    card.className = 'snapshot-card';
    card.onclick = function () { card.classList.toggle('expanded'); };

    card.innerHTML = `
      <div class="snapshot-gen">Gen ${gen.generation}</div>
      <div class="snapshot-score">${gen.change_magnitude.toFixed(4)}</div>
      <div class="snapshot-dims">
        ${DIMS.map(d => `
          <div class="snapshot-dim">
            <span>${DIM_LABELS[d]}</span>
            <span style="color:${COLORS[d]}">${gen.weights[d].toFixed(3)}</span>
          </div>
        `).join('')}
      </div>
      <div class="snapshot-events">${gen.convergence.replace(/_/g, ' ')}</div>
      <div class="snapshot-detail">
        <h4>Evolution Events</h4>
        ${(gen.evolution_events || []).length
          ? gen.evolution_events.map(e => `<span class="event-tag">${e.intent || 'evolution'}</span>`).join('')
          : 'No events recorded'}
      </div>
    `;

    container.appendChild(card);
  }
}

// ═══════════════════════════════════════════════════════════════
// 6. Strategy Control
// ═══════════════════════════════════════════════════════════════

function initStrategyForm() {
  const strategy = evolutionData.current_strategy || {};
  if (strategy.strategy) document.getElementById('strategy-select').value = strategy.strategy;
  if (strategy.mutation_rate) {
    document.getElementById('mutation-rate').value = strategy.mutation_rate;
    document.getElementById('mutation-rate-val').textContent = strategy.mutation_rate.toFixed(2);
  }
  if (strategy.mutation_strength) {
    document.getElementById('mutation-strength').value = strategy.mutation_strength;
    document.getElementById('mutation-strength-val').textContent = strategy.mutation_strength.toFixed(2);
  }
  if (strategy.target_dimensions) {
    const checkboxes = document.querySelectorAll('input[name="dim"]');
    checkboxes.forEach(cb => {
      cb.checked = strategy.target_dimensions.includes(cb.value);
    });
  }

  // Range sliders live update
  document.getElementById('mutation-rate').oninput = function () {
    document.getElementById('mutation-rate-val').textContent = parseFloat(this.value).toFixed(2);
  };
  document.getElementById('mutation-strength').oninput = function () {
    document.getElementById('mutation-strength-val').textContent = parseFloat(this.value).toFixed(2);
  };

  // Submit
  document.getElementById('strategy-form').onsubmit = async function (e) {
    e.preventDefault();
    const msg = document.getElementById('strategy-message');
    const dims = [...document.querySelectorAll('input[name="dim"]:checked')].map(cb => cb.value);

    const payload = {
      db_path: getDbPath(),
      strategy: document.getElementById('strategy-select').value,
      mutation_rate: parseFloat(document.getElementById('mutation-rate').value),
      mutation_strength: parseFloat(document.getElementById('mutation-strength').value),
      target_dimensions: dims,
    };

    try {
      const res = await fetch('/api/evolution/strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.saved) {
        msg.textContent = 'Strategy saved. Will apply on next evolution cycle.';
        msg.className = 'message success';
        // Update local state
        evolutionData.current_strategy = payload;
      } else {
        msg.textContent = 'Save failed.';
        msg.className = 'message error';
      }
    } catch (err) {
      msg.textContent = 'Network error: ' + err.message;
      msg.className = 'message error';
    }
  };
}

// ═══════════════════════════════════════════════════════════════
// Canvas helper
// ═══════════════════════════════════════════════════════════════

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

// ═══════════════════════════════════════════════════════════════
// Boot
// ═══════════════════════════════════════════════════════════════

init();
