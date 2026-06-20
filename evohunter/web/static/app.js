// EvoHunter — I'm Hiring / I'm Looking

const API = (p, b) => fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then(r => r.json());
const DB = () => { try { return localStorage.getItem('evohunter_db_path') || '.evohunter/workbench.db'; } catch { return '.evohunter/workbench.db'; } };

let mode = 'hiring';
let pool = { jds: [], candidates: [] };
let selectedJD = null, selectedCandidate = null;
let results = [], selectedResult = -1;

// ═══════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════

async function init() {
  document.querySelectorAll('.mode-tab').forEach(tab => {
    tab.onclick = () => switchMode(tab.dataset.mode);
  });

  document.getElementById('h-search-btn').onclick = () => searchJDs();
  document.getElementById('l-search-btn').onclick = () => searchCandidates();
  document.getElementById('seed-btn').onclick = seed;

  document.getElementById('h-import-btn').onclick = importJD;
  document.getElementById('l-import-btn').onclick = importResume;

  ['h-search-skills', 'h-search-loc', 'l-search-skills', 'l-search-loc'].forEach(id => {
    document.getElementById(id).onkeydown = e => { if (e.key === 'Enter') mode === 'hiring' ? searchJDs() : searchCandidates(); };
  });

  await checkApiKey();
  await updateStatusBar();
  await loadAll();
}

function switchMode(m) {
  mode = m;
  document.querySelectorAll('.mode-tab').forEach(t => t.classList.toggle('active', t.dataset.mode === m));
  document.getElementById('mode-hiring').hidden = m !== 'hiring';
  document.getElementById('mode-looking').hidden = m !== 'looking';
  selectedJD = null; selectedCandidate = null;
  results = []; selectedResult = -1;
  renderAll();
}

async function checkApiKey() {
  try {
    const c = await API('/api/config');
    document.getElementById('api-dot').classList.toggle('on', c.has_api_key);
    document.getElementById('api-status').textContent = c.has_api_key ? 'API ready' : 'no key';
  } catch { document.getElementById('api-status').textContent = 'offline'; }
}

async function updateStatusBar() {
  try {
    const d = await API('/api/evolution/data', { db_path: DB() });
    const last = (d.generations || []).slice(-1)[0];
    document.getElementById('sb-generation').textContent = last ? `Gen ${last.generation}` : 'Gen 0';
    document.getElementById('gen-badge').textContent = last ? `Gen ${last.generation}` : 'Gen 0';
    document.getElementById('sb-strategy').textContent = (d.current_strategy || {}).strategy || 'balanced';
  } catch {}
}

async function loadAll() {
  try {
    pool = await API('/api/pool/search', { side: 'both' });
  } catch { pool = { jds: [], candidates: [] }; }
  updateCounts();
}

function updateCounts() {
  document.getElementById('sb-jds').textContent = `${pool.jds.length} JDs`;
  document.getElementById('sb-candidates').textContent = `${pool.candidates.length} candidates`;
}

// ═══════════════════════════════════════════════════════════
// Search
// ═══════════════════════════════════════════════════════════

async function searchJDs() {
  const skills = document.getElementById('h-search-skills').value.trim();
  const location = document.getElementById('h-search-loc').value.trim();
  const level = document.getElementById('h-search-level').value;

  try {
    const r = await API('/api/pool/search', { db_path: DB(), skills, location, seniority_level: level, side: 'jd' });
    pool.jds = r.jds;
  } catch { pool.jds = []; }
  selectedJD = null;
  results = [];
  renderAll();
}

async function searchCandidates() {
  const skills = document.getElementById('l-search-skills').value.trim();
  const location = document.getElementById('l-search-loc').value.trim();
  const level = document.getElementById('l-search-level').value;

  try {
    const r = await API('/api/pool/search', { db_path: DB(), skills, location, seniority_level: level, side: 'candidate' });
    pool.candidates = r.candidates;
  } catch { pool.candidates = []; }
  selectedCandidate = null;
  results = [];
  renderAll();
}

// ═══════════════════════════════════════════════════════════
// Render
// ═══════════════════════════════════════════════════════════

function renderAll() {
  renderJDList();
  renderCandidateList();
  renderHiringResults();
  renderLookingResults();
  updateCounts();
}

function renderJDList() {
  const list = document.getElementById('h-jd-list');
  document.getElementById('h-jd-count').textContent = String(pool.jds.length);
  if (!pool.jds.length) { list.innerHTML = '<div class="empty-hint"><p>No JDs found.</p></div>'; return; }
  list.innerHTML = pool.jds.map(jd => `
    <div class="item-card${selectedJD === jd.job_id ? ' selected' : ''}" onclick="selectJD('${jd.job_id}')">
      <span class="item-icon">🏢</span>
      <div class="item-body">
        <div class="item-title">${esc(jd.job_title)}</div>
        <div class="item-meta">${[jd.location, jd.salary_range, jd.seniority_level, (jd.required_skills||[]).slice(0,3).join('·')].filter(Boolean).join(' · ')}</div>
      </div>
    </div>
  `).join('');
}

function renderCandidateList() {
  const list = document.getElementById('l-candidate-list');
  document.getElementById('l-candidate-count').textContent = String(pool.candidates.length);
  if (!pool.candidates.length) { list.innerHTML = '<div class="empty-hint"><p>No candidates found.</p></div>'; return; }
  list.innerHTML = pool.candidates.map(c => `
    <div class="item-card${selectedCandidate === c.candidate_id ? ' selected' : ''}" onclick="selectCandidate('${c.candidate_id}')">
      <span class="item-icon">👤</span>
      <div class="item-body">
        <div class="item-title">${esc(c.candidate_id)}</div>
        <div class="item-meta">${[c.seniority_level, c.salary_expectation, c.location_preference, (c.skill_vector||[]).slice(0,3).join('·')].filter(Boolean).join(' · ')}</div>
      </div>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════════════════
// Select & Match
// ═══════════════════════════════════════════════════════════

async function selectJD(jobId) {
  selectedJD = jobId;
  selectedResult = -1;
  renderJDList();

  const jd = pool.jds.find(j => j.job_id === jobId);
  if (!jd) return;
  document.getElementById('h-selected-title').textContent = jd.job_title;
  document.getElementById('h-result-label').hidden = false;

  // Match against ALL candidates
  results = [];
  document.getElementById('h-results').innerHTML = '<div class="empty-hint"><p>Matching...</p></div>';
  document.getElementById('h-detail').hidden = true;

  // Ensure we have candidates loaded
  if (!pool.candidates.length) {
    try { const r = await API('/api/pool/search', { side: 'candidate' }); pool.candidates = r.candidates; } catch {}
  }

  for (const c of pool.candidates) {
    const resumeText = [c.candidate_id, (c.skill_vector||[]).join(', '), `${c.years_of_experience||0}yr`, c.seniority_level, c.salary_expectation, c.location_preference].filter(Boolean).join('. ');
    try {
      const a = await API('/api/recruiter/assess', { job_gene: jd, resume_text: resumeText, language: 'zh' });
      results.push({ candidateId: c.candidate_id, jdId: jd.job_id, jdTitle: jd.job_title, assessment: a, score: a.match_degree || 0 });
    } catch (e) {
      results.push({ candidateId: c.candidate_id, jdId: jd.job_id, jdTitle: jd.job_title, assessment: { error: e.message }, score: 0 });
    }
  }
  results.sort((a, b) => b.score - a.score);
  renderHiringResults();
}

function renderHiringResults() {
  const list = document.getElementById('h-results');
  if (!results.length) { list.innerHTML = ''; return; }
  list.innerHTML = results.map((r, i) => {
    const s = r.score; const a = r.assessment;
    const attr = s >= 8 ? 'data-high' : s >= 6 ? 'data-mid' : 'data-low';
    const tags = (a.tech_tags || []).slice(0, 5);
    return `
      <div class="result-card${i === selectedResult ? ' selected' : ''}" onclick="showHiringDetail(${i})">
        <div class="result-name">${esc(a.candidate_name || r.candidateId)}</div>
        <div class="result-tags">${tags.map(t => `<span class="result-tag">${esc(t)}</span>`).join('')}</div>
        <div class="result-score" ${attr}>${s}/10</div>
      </div>
    `;
  }).join('');
}

async function selectCandidate(candidateId) {
  selectedCandidate = candidateId;
  selectedResult = -1;
  renderCandidateList();

  const c = pool.candidates.find(c => c.candidate_id === candidateId);
  if (!c) return;
  document.getElementById('l-selected-name').textContent = c.candidate_id;
  document.getElementById('l-result-label').hidden = false;

  results = [];
  document.getElementById('l-results').innerHTML = '<div class="empty-hint"><p>Matching...</p></div>';
  document.getElementById('l-detail').hidden = true;

  if (!pool.jds.length) {
    try { const r = await API('/api/pool/search', { side: 'jd' }); pool.jds = r.jds; } catch {}
  }

  for (const jd of pool.jds) {
    const resumeText = [c.candidate_id, (c.skill_vector||[]).join(', '), `${c.years_of_experience||0}yr`, c.seniority_level, c.salary_expectation, c.location_preference].filter(Boolean).join('. ');
    try {
      const a = await API('/api/recruiter/assess', { job_gene: jd, resume_text: resumeText, language: 'zh' });
      results.push({ candidateId: c.candidate_id, jdId: jd.job_id, jdTitle: jd.job_title, assessment: a, score: a.match_degree || 0 });
    } catch (e) {
      results.push({ candidateId: c.candidate_id, jdId: jd.job_id, jdTitle: jd.job_title, assessment: { error: e.message }, score: 0 });
    }
  }
  results.sort((a, b) => b.score - a.score);
  renderLookingResults();
}

function renderLookingResults() {
  const list = document.getElementById('l-results');
  if (!results.length) { list.innerHTML = ''; return; }
  list.innerHTML = results.map((r, i) => {
    const s = r.score; const a = r.assessment;
    const attr = s >= 8 ? 'data-high' : s >= 6 ? 'data-mid' : 'data-low';
    const tags = (a.tech_tags || []).slice(0, 5);
    return `
      <div class="result-card${i === selectedResult ? ' selected' : ''}" onclick="showLookingDetail(${i})">
        <div class="result-name">${esc(r.jdTitle)}</div>
        <div class="result-tags">${tags.map(t => `<span class="result-tag">${esc(t)}</span>`).join('')}</div>
        <div class="result-score" ${attr}>${s}/10</div>
      </div>
    `;
  }).join('');
}

// ═══════════════════════════════════════════════════════════
// Detail
// ═══════════════════════════════════════════════════════════

function showHiringDetail(i) {
  selectedResult = i;
  renderHiringResults();
  const r = results[i]; if (!r) return;
  const wrap = document.getElementById('h-detail');
  wrap.hidden = false;
  document.getElementById('h-detail-content').innerHTML = detailHTML(r);
  wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showLookingDetail(i) {
  selectedResult = i;
  renderLookingResults();
  const r = results[i]; if (!r) return;
  const wrap = document.getElementById('l-detail');
  wrap.hidden = false;
  document.getElementById('l-detail-content').innerHTML = detailHTML(r);
  wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function detailHTML(r) {
  const a = r.assessment; const s = a.match_degree || 0;
  const sc = s >= 8 ? 'var(--success)' : s >= 6 ? 'var(--warning)' : 'var(--error)';
  const tags = a.tech_tags || [];
  const points = a.main_match_points || [];
  const deductions = a.main_deductions || [];
  const reasons = a.reasons_for_recommendation || [];
  const rec = a.recommendation_text || '';

  return `
    <div class="detail-name">${esc(a.candidate_name || r.candidateId)} → ${esc(r.jdTitle)}</div>
    <div class="detail-score-row">
      <div class="detail-score-big" style="color:${sc}">${s}</div>
      <div class="detail-score-label">/ 10 · ${esc(a.conclusion || '')}</div>
    </div>
    <div class="detail-bidirectional">
      <div><div class="detail-bid-label">Hard Match</div><div class="detail-bid-score" style="color:${sc}">${(a.hard_match_score||0).toFixed(1)}/7</div></div>
      <div><div class="detail-bid-label">HR Bonus</div><div class="detail-bid-score" style="color:var(--accent)">${(a.hr_bonus_score||0).toFixed(1)}/3</div></div>
    </div>
    ${points.length ? `<div class="detail-section"><h3>Match Points</h3><ul class="detail-reasons">${points.map(p => `<li>${esc(p)}</li>`).join('')}</ul></div>` : ''}
    ${deductions.length ? `<div class="detail-section"><h3>Deductions</h3><ul class="detail-reasons">${deductions.map(d => `<li style="border-left-color:var(--error)">${esc(d)}</li>`).join('')}</ul></div>` : ''}
    ${reasons.length ? `<div class="detail-section"><h3>Recommendation</h3><ul class="detail-reasons">${reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul></div>` : ''}
    ${tags.length ? `<div class="detail-section"><h3>Tech Tags</h3><div class="detail-tags">${tags.map(t => `<span class="detail-tag">${esc(t)}</span>`).join('')}</div></div>` : ''}
    ${a.current_salary||a.current_level ? `<div class="detail-section"><h3>Compensation</h3><p style="font-size:0.8125rem">${esc(a.current_salary||'—')} · ${esc(a.current_level||'—')}</p></div>` : ''}
    ${a.reason_for_leaving ? `<div class="detail-section"><h3>Reason</h3><p style="font-size:0.8125rem">${esc(a.reason_for_leaving)}</p></div>` : ''}
    ${rec ? `<div class="detail-section"><h3>Recommendation Text</h3><div class="detail-rec-text">${esc(rec)}</div></div>` : ''}
    ${a.requires_human_input ? `<div class="detail-section"><p style="color:var(--warning);font-weight:600">⚠ Match below 7</p></div>` : ''}
  `;
}

// ═══════════════════════════════════════════════════════════
// Import
// ═══════════════════════════════════════════════════════════

async function importJD() {
  const text = document.getElementById('h-import-text').value.trim();
  if (!text) return;
  const msg = document.getElementById('h-import-msg');
  msg.textContent = 'Importing...';
  try {
    await API('/api/parse-job', { text, db_path: DB() });
    document.getElementById('h-import-text').value = '';
    msg.textContent = 'Imported!';
    await searchJDs();
  } catch (e) { msg.textContent = 'Failed: ' + e.message; }
}

async function importResume() {
  const text = document.getElementById('l-import-text').value.trim();
  if (!text) return;
  const msg = document.getElementById('l-import-msg');
  msg.textContent = 'Importing...';
  try {
    await API('/api/parse-candidates', { text, db_path: DB() });
    document.getElementById('l-import-text').value = '';
    msg.textContent = 'Imported!';
    await searchCandidates();
  } catch (e) { msg.textContent = 'Failed: ' + e.message; }
}

// ═══════════════════════════════════════════════════════════
// Seed
// ═══════════════════════════════════════════════════════════

async function seed() {
  const btn = document.getElementById('seed-btn');
  btn.textContent = 'Seeding...'; btn.disabled = true;
  try {
    await API('/api/pool/seed', { db_path: DB() });
    await loadAll();
    if (mode === 'hiring') { pool.jds.length && selectJD(pool.jds[0].job_id); }
    else { pool.candidates.length && selectCandidate(pool.candidates[0].candidate_id); }
  } catch (e) { console.error(e); }
  finally { btn.textContent = 'Seed Demo'; btn.disabled = false; }
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div'); d.textContent = String(s); return d.innerHTML;
}

init();
