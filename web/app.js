/* ================================================================
   Echoes app.js — Main application logic
   ================================================================ */

const API = 'http://127.0.0.1:8000';

/* ── State ──────────────────────────────────────────────────────── */
const state = {
  view: 'dashboard',
  status: null,
  presets: [],
  patients: [],
  currentPatient: null,
  currentSession: null,
  activeChapterIndex: 0,
  chapterReactions: {},
  intakeSeeds: [],
  searchDebounce: null,
  seedSearchDebounce: null,
};

/* ── Helpers ────────────────────────────────────────────────────── */
async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = { success: '✓', error: '✗', info: '◆' };
  el.innerHTML = `<span>${icons[type]}</span><span>${msg}</span>`;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function $(sel, root = document) { return root.querySelector(sel); }
function $$(sel, root = document) { return [...root.querySelectorAll(sel)]; }

function navigateTo(view) {
  state.view = view;
  $$('.view').forEach(v => v.classList.remove('active'));
  $$('.nav-item').forEach(n => n.classList.remove('active'));
  const v = $(`#view-${view}`);
  if (v) v.classList.add('active');
  const n = $(`.nav-item[data-view="${view}"]`);
  if (n) n.classList.add('active');
  if (view === 'dashboard') loadDashboard();
  if (view === 'patients') loadPatients();
  if (view === 'intake') prepareIntake();
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  if (loading) btn.classList.add('btn-loading');
  else btn.classList.remove('btn-loading');
}

function formatEra(birthYear) {
  return `${birthYear + 12} – ${birthYear + 28}`;
}

function domainIcon(domain) {
  return { artist: '♪', movie: '◉', tv_show: '▷', brand: '◈', place: '◎' }[domain] || '●';
}

function domainLabel(domain) {
  return { artist: 'Music', movie: 'Cinema', tv_show: 'Television', brand: 'Heritage Brand', place: 'Hometown Place' }[domain] || domain;
}

function entityTypeShort(typeUrn) {
  return (typeUrn || '').split(':').pop() || 'entity';
}

/* ── Bootstrap ──────────────────────────────────────────────────── */
async function bootstrap() {
  // Load status
  try {
    state.status = await api('GET', '/api/status');
    updateStatusBadge();
  } catch (e) {
    toast('Cannot reach Echoes API server', 'error');
  }

  // Load presets
  try {
    state.presets = await api('GET', '/api/presets');
  } catch (_) {}

  // Wire nav
  $$('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => navigateTo(item.dataset.view));
  });

  // Mode badge click
  document.getElementById('mode-badge').addEventListener('click', toggleMode);

  // Wire modal close
  document.getElementById('modal-overlay').addEventListener('click', (e) => {
    if (e.target === document.getElementById('modal-overlay')) closeModal();
  });
  document.getElementById('modal-close').addEventListener('click', closeModal);

  navigateTo('dashboard');
}

function updateStatusBadge() {
  const s = state.status;
  if (!s) return;
  const badge = document.getElementById('mode-badge');
  if (!badge) return;
  const isLive = s.mode === 'live';
  badge.className = `mode-badge ${isLive ? 'live' : 'mock'}`;
  badge.innerHTML = `<span class="dot"></span>${isLive ? 'Live Qloo API' : 'Offline Mock'}`;
  badge.title = `Base URL: ${s.base_url || 'Unknown'}`;
}

async function toggleMode() {
  const currently = state.status?.mode === 'mock';
  const want_live = currently;
  try {
    const res = await api('POST', '/api/toggle-mock', { enable_mock: !want_live });
    state.status = await api('GET', '/api/status');
    updateStatusBadge();
    toast(`Switched to ${res.mode === 'live' ? 'Live Qloo API' : 'Offline Mock'} mode`, 'success');
  } catch (e) {
    toast('Failed to toggle mode: ' + e.message, 'error');
  }
}

/* ── Dashboard ──────────────────────────────────────────────────── */
async function loadDashboard() {
  try {
    state.status = await api('GET', '/api/status');
    updateStatusBadge();
    $('#stat-patients').textContent = state.status.total_patients;
    $('#stat-sessions').textContent = state.status.total_sessions;
    renderPresets('#dashboard-presets');
  } catch (e) {
    toast('Failed to load dashboard: ' + e.message, 'error');
  }
}

function renderPresets(containerSel, onSelect = null) {
  const cont = $(containerSel);
  if (!cont) return;
  cont.innerHTML = '';
  state.presets.forEach(p => {
    const card = document.createElement('div');
    card.className = 'preset-card';
    card.innerHTML = `
      <div class="preset-flag">${p.flag}</div>
      <div>
        <div class="preset-name">${p.name}</div>
        <div class="preset-era">${p.golden_era}</div>
      </div>
      <div class="preset-hometown">📍 ${p.hometown}</div>
      <div class="preset-culture-tag">${p.culture}</div>
    `;
    card.addEventListener('click', () => {
      if (onSelect) { onSelect(p); closeModal(); }
      else { prepareSessionWithPreset(p); }
    });
    cont.appendChild(card);
  });
}

/* ── Intake View ────────────────────────────────────────────────── */
function prepareIntake() {
  state.intakeSeeds = [];
  renderSeedTags();
  document.getElementById('intake-birth-year').addEventListener('input', onBirthYearChange);
  onBirthYearChange();

  // Seed search
  const seedInput = document.getElementById('seed-search');
  seedInput.addEventListener('input', () => {
    clearTimeout(state.seedSearchDebounce);
    const q = seedInput.value.trim();
    if (q.length < 2) { closeSearchDropdown('seed-dropdown'); return; }
    state.seedSearchDebounce = setTimeout(() => runSeedSearch(q), 350);
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrap')) closeSearchDropdown('seed-dropdown');
  });

  document.getElementById('btn-load-preset').addEventListener('click', openPresetModal);
  document.getElementById('btn-generate-session').addEventListener('click', generateSession);
}

function prepareSessionWithPreset(preset) {
  navigateTo('intake');
  setTimeout(() => {
    document.getElementById('intake-name').value = preset.name;
    document.getElementById('intake-birth-year').value = preset.birth_year;
    document.getElementById('intake-hometown').value = preset.hometown;
    document.getElementById('intake-culture').value = preset.culture;
    document.getElementById('intake-preset-id').value = preset.id;
    onBirthYearChange();
    state.intakeSeeds = (preset.seeds || []).map(s => ({ ...s }));
    renderSeedTags();
    toast(`Loaded persona: ${preset.name}`, 'success');
  }, 100);
}

function onBirthYearChange() {
  const yr = parseInt(document.getElementById('intake-birth-year').value);
  if (!yr || yr < 1900 || yr > 2010) return;
  document.getElementById('era-display').textContent = formatEra(yr);
  document.getElementById('era-desc').textContent = `Ages 12–28 of ${document.getElementById('intake-name').value || 'recipient'}`;
}

async function runSeedSearch(q) {
  const typeEl = document.getElementById('seed-type');
  const typeVal = typeEl ? typeEl.value : null;
  try {
    const res = await api('POST', '/api/search', { query: q, types: typeVal || null, take: 6 });
    renderSearchDropdown('seed-dropdown', res.results || [], (item) => {
      addSeed({ name: item.name, type: item.type, qloo_id: item.id });
      document.getElementById('seed-search').value = '';
      closeSearchDropdown('seed-dropdown');
    });
  } catch (_) {}
}

function renderSearchDropdown(id, results, onPick) {
  const dd = document.getElementById(id);
  if (!dd) return;
  dd.innerHTML = '';
  if (!results.length) { dd.classList.remove('open'); return; }
  results.forEach(r => {
    const item = document.createElement('div');
    item.className = 'search-result-item';
    item.innerHTML = `
      <span class="search-result-name">${r.name}</span>
      <span class="search-result-type">${entityTypeShort(r.type)}</span>
    `;
    item.addEventListener('click', () => onPick(r));
    dd.appendChild(item);
  });
  dd.classList.add('open');
}

function closeSearchDropdown(id) {
  const dd = document.getElementById(id);
  if (dd) dd.classList.remove('open');
}

function addSeed(seed) {
  const alreadyExists = state.intakeSeeds.some(s => s.name.toLowerCase() === seed.name.toLowerCase());
  if (alreadyExists) { toast('Seed already added', 'info'); return; }
  if (state.intakeSeeds.length >= 5) { toast('Max 5 seeds allowed', 'info'); return; }
  state.intakeSeeds.push(seed);
  renderSeedTags();
}

function removeSeed(idx) {
  state.intakeSeeds.splice(idx, 1);
  renderSeedTags();
}

function renderSeedTags() {
  const cont = document.getElementById('seed-tags-container');
  if (!cont) return;
  cont.innerHTML = '';
  if (!state.intakeSeeds.length) {
    cont.innerHTML = '<span style="color:var(--text-muted);font-size:13px;">Search and add cultural seeds above...</span>';
    return;
  }
  state.intakeSeeds.forEach((seed, i) => {
    const tag = document.createElement('span');
    tag.className = 'seed-tag';
    tag.innerHTML = `
      <span>${seed.name}</span>
      <span class="seed-tag-type">${entityTypeShort(seed.type)}</span>
      <span class="seed-remove" onclick="removeSeed(${i})" title="Remove">×</span>
    `;
    cont.appendChild(tag);
  });
}

async function generateSession() {
  const name = document.getElementById('intake-name').value.trim();
  const birthYear = parseInt(document.getElementById('intake-birth-year').value);
  const hometown = document.getElementById('intake-hometown').value.trim();
  const culture = document.getElementById('intake-culture').value.trim();
  const presetId = document.getElementById('intake-preset-id').value.trim() || null;

  if (!name || !birthYear || !hometown) {
    toast('Please fill in name, birth year, and hometown', 'error'); return;
  }

  setLoading('btn-generate-session', true);
  try {
    const payload = { name, birth_year: birthYear, hometown, culture, seeds: state.intakeSeeds, preset_id: presetId };
    const result = await api('POST', '/api/sessions/generate', payload);
    state.currentSession = result;
    state.activeChapterIndex = 0;
    state.chapterReactions = {};
    navigateTo('session');
    renderSession(result);
    toast('Session generated successfully', 'success');
  } catch (e) {
    toast('Failed to generate session: ' + e.message, 'error');
  } finally {
    setLoading('btn-generate-session', false);
  }
}

/* ── Session View ───────────────────────────────────────────────── */
function renderSession(result) {
  const session = result.session;
  const baseline = result.generic_baseline;
  const sessionId = result.session_id;

  // Header
  $('#session-title').textContent = session.title;
  $('#session-meta').textContent = `${session.hometown} · ${session.golden_era} · ${session.total_duration_minutes} min`;

  // Grounding Score Ring
  const score = parseInt(session.stats.grounding_score);
  const fg = $('.fg-ring');
  if (fg) {
    setTimeout(() => {
      const offset = 163 * (1 - score / 100);
      fg.style.strokeDashoffset = offset;
    }, 200);
  }
  $('#grounding-percent').textContent = session.stats.grounding_score;
  $('#grounding-count').textContent = `${session.stats.qloo_verified_entities}/${session.stats.total_anchors} Qloo verified`;

  // Progress dots
  renderProgressDots(session.chapters.length);

  // Chapters
  renderChapters(session.chapters, sessionId, session);

  // Comparison
  renderComparison(baseline, session.chapters);
}

function renderProgressDots(count) {
  const wrap = $('#session-steps');
  if (!wrap) return;
  wrap.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const dot = document.createElement('div');
    dot.className = 'step-dot' + (i === 0 ? ' active' : '');
    dot.id = `step-dot-${i}`;
    wrap.appendChild(dot);
  }
}

function updateProgressDots(activeIdx) {
  $$('.step-dot').forEach((dot, i) => {
    dot.classList.toggle('done', i < activeIdx);
    dot.classList.toggle('active', i === activeIdx);
  });
}

function renderChapters(chapters, sessionId, session) {
  const cont = $('#session-chapters');
  if (!cont) return;
  cont.innerHTML = '';
  chapters.forEach((ch, i) => {
    const card = document.createElement('div');
    card.className = 'chapter-card' + (i === 0 ? ' active-chapter' : '');
    card.id = `chapter-${i}`;

    const alts = (ch.alternative_entities || []).map(a =>
      `<span class="alt-pill" title="${a.id}">${a.name}</span>`
    ).join('');

    const hasReaction = state.chapterReactions[i];

    card.innerHTML = `
      <div class="chapter-header">
        <div class="chapter-step">
          <div class="step-number">${i + 1}</div>
          <div>
            <div class="chapter-domain">${ch.domain_title}</div>
            <div class="chapter-domain-type">${domainLabel(ch.domain)}</div>
          </div>
        </div>
        <div style="font-size:20px;opacity:0.5;">${domainIcon(ch.domain)}</div>
      </div>

      <div>
        <div class="chapter-entity">${ch.primary_entity.name}</div>
        <div class="chapter-entity-meta" style="margin-top:6px;">
          ${ch.primary_entity.qloo_verified
            ? `<span class="entity-qloo-badge">✓ Qloo Verified</span>`
            : `<span style="font-size:11px;color:var(--text-muted);">Seed (unverified)</span>`}
          ${ch.primary_entity.affinity != null
            ? `<span class="entity-affinity">Affinity: ${(ch.primary_entity.affinity * 100).toFixed(0)}%</span>` : ''}
        </div>
      </div>

      ${alts ? `<div><div class="chapter-section-label">Also Curated by Qloo</div><div class="alternatives-strip">${alts}</div></div>` : ''}

      <div>
        <div class="chapter-section-label">Caregiver Conversation Opener</div>
        <div class="chapter-prompt">${ch.conversation_prompt}</div>
      </div>

      <div class="sensory-cue">
        <span class="sensory-icon">✦</span>
        <span>${ch.sensory_cue}</span>
      </div>

      <div class="reaction-bar">
        <span class="reaction-label">How did they respond?</span>
        <button class="reaction-btn lit-up ${hasReaction === 'lit_up' ? 'selected' : ''}" data-chapter="${i}" data-reaction="lit_up" data-entity-id="${ch.primary_entity.id}" data-entity-name="${ch.primary_entity.name}" data-entity-type="${ch.primary_entity.type}" data-session-id="${sessionId}">
          <span class="reaction-emoji">🌟</span> Lit Up
        </button>
        <button class="reaction-btn neutral-r ${hasReaction === 'neutral' ? 'selected' : ''}" data-chapter="${i}" data-reaction="neutral" data-entity-id="${ch.primary_entity.id}" data-entity-name="${ch.primary_entity.name}" data-entity-type="${ch.primary_entity.type}" data-session-id="${sessionId}">
          <span class="reaction-emoji">😐</span> Neutral
        </button>
        <button class="reaction-btn upset-r ${hasReaction === 'upset' ? 'selected' : ''}" data-chapter="${i}" data-reaction="upset" data-entity-id="${ch.primary_entity.id}" data-entity-name="${ch.primary_entity.name}" data-entity-type="${ch.primary_entity.type}" data-session-id="${sessionId}">
          <span class="reaction-emoji">💔</span> Upset
        </button>
      </div>
    `;

    card.addEventListener('click', (e) => {
      if (e.target.closest('.reaction-btn')) return;
      setActiveChapter(i);
    });

    cont.appendChild(card);
  });

  // Wire reaction buttons
  $$('.reaction-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const chapterIdx = parseInt(btn.dataset.chapter);
      recordReaction(btn, chapterIdx, state.currentSession?.session?.patient_id);
    });
  });
}

function setActiveChapter(idx) {
  state.activeChapterIndex = idx;
  $$('.chapter-card').forEach((c, i) => c.classList.toggle('active-chapter', i === idx));
  updateProgressDots(idx);
  const card = $(`#chapter-${idx}`);
  if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function recordReaction(btn, chapterIdx, patientId) {
  const { reaction, entityId, entityName, entityType, sessionId } = btn.dataset;

  if (!patientId) {
    // No patient saved, just track locally
    state.chapterReactions[chapterIdx] = reaction;
    const bar = btn.closest('.reaction-bar');
    if (bar) {
      $$('.reaction-btn', bar).forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    }
    const emoji = { lit_up: '🌟', neutral: '😐', upset: '💔' }[reaction];
    toast(`Marked as ${emoji} ${reaction.replace('_', ' ')}`, reaction === 'upset' ? 'error' : 'success');
    return;
  }

  try {
    await api('POST', '/api/sessions/adapt', {
      patient_id: patientId,
      entity_id: entityId,
      entity_name: entityName,
      entity_type: entityType,
      reaction,
      session_id: sessionId,
    });
    state.chapterReactions[chapterIdx] = reaction;
    const bar = btn.closest('.reaction-bar');
    if (bar) {
      $$('.reaction-btn', bar).forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    }
    const emoji = { lit_up: '🌟', neutral: '😐', upset: '💔' }[reaction];
    const msg = reaction === 'upset'
      ? `"${entityName}" added to safety exclusion list`
      : `Recorded: ${emoji} ${reaction.replace('_', ' ')}`;
    toast(msg, reaction === 'upset' ? 'error' : 'success');
  } catch (e) {
    toast('Error recording reaction: ' + e.message, 'error');
  }
}

/* ── Comparison View ────────────────────────────────────────────── */
function renderComparison(baseline, chapters) {
  // LLM Flaws
  const flawsCont = $('#llm-flaws');
  if (flawsCont) {
    flawsCont.innerHTML = '';
    (baseline.critical_flaws || []).forEach(f => {
      const div = document.createElement('div');
      div.className = 'flaw-item';
      div.innerHTML = `<span class="flaw-icon">✗</span><span>${f}</span>`;
      flawsCont.appendChild(div);
    });
  }

  // LLM Simulated output
  const llmItems = $('#llm-items');
  if (llmItems && baseline.simulated_output) {
    llmItems.innerHTML = '';
    Object.entries(baseline.simulated_output).forEach(([domain, value], idx) => {
      const item = document.createElement('div');
      item.className = 'comparison-item';
      item.style.animationDelay = `${idx * 0.07}s`;
      item.innerHTML = `
        <div class="comparison-item-domain">${domainLabel(domain)}</div>
        <div class="comparison-item-name">
          <span class="llm-unverified">✗</span>
          ${value}
        </div>
        <div class="comparison-item-meta" style="color:var(--text-muted);font-style:italic;">No Qloo ID · Unverified · Culturally Displaced</div>
      `;
      llmItems.appendChild(item);
    });
  }

  // Hazard Rating
  const riskEl = $('#llm-risk');
  if (riskEl) riskEl.textContent = baseline.hallucination_risk || '—';

  // Qloo items from real chapters
  const qlooItems = $('#qloo-items');
  if (qlooItems) {
    qlooItems.innerHTML = '';
    chapters.forEach((ch, idx) => {
      const item = document.createElement('div');
      item.className = 'comparison-item';
      item.style.animationDelay = `${idx * 0.07}s`;
      item.innerHTML = `
        <div class="comparison-item-domain">${domainLabel(ch.domain)}</div>
        <div class="comparison-item-name">
          <span class="qloo-verified">${ch.primary_entity.qloo_verified ? '✓' : '~'}</span>
          ${ch.primary_entity.name}
        </div>
        <div class="comparison-item-meta">
          ${ch.primary_entity.qloo_verified ? `ID: ${ch.primary_entity.id.substring(0, 20)}...` : 'Seed entity'}
          ${ch.primary_entity.affinity != null ? ` · Affinity: ${(ch.primary_entity.affinity * 100).toFixed(0)}%` : ''}
        </div>
      `;
      qlooItems.appendChild(item);
    });
  }

  // Grounding score verdict
  const qlooVerdict = $('#qloo-verdict');
  if (qlooVerdict) qlooVerdict.textContent = 'Culturally grounded, safety-filtered, no hallucination risk';

  const llmVerdict = $('#llm-verdict');
  if (llmVerdict) llmVerdict.textContent = baseline.verdict || '';
}

/* ── Patients View ──────────────────────────────────────────────── */
async function loadPatients() {
  try {
    state.patients = await api('GET', '/api/patients');
    renderPatientList();
  } catch (e) {
    toast('Failed to load patients: ' + e.message, 'error');
  }
}

function renderPatientList() {
  const cont = $('#patient-list');
  if (!cont) return;
  cont.innerHTML = '';

  if (!state.patients.length) {
    cont.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">◌</div>
        <div class="empty-state-title">No care recipients yet</div>
        <div class="empty-state-desc">Create a profile in the Intake Studio to get started with a personalized session.</div>
      </div>`;
    return;
  }

  state.patients.forEach(p => {
    const card = document.createElement('div');
    card.className = 'patient-card';
    const initials = p.name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
    card.innerHTML = `
      <div class="patient-avatar">${initials}</div>
      <div class="patient-info">
        <div class="patient-name">${p.name}</div>
        <div class="patient-meta">${p.hometown} · Born ${p.birth_year} · Era ${formatEra(p.birth_year)}</div>
        <div class="patient-meta" style="margin-top:3px;color:var(--text-muted);">${p.culture || 'General'}</div>
      </div>
      <div class="patient-stats">
        <span class="mini-badge lit">🌟 ${p.positive_count || 0} lit up</span>
        <span class="mini-badge excl">❌ ${p.excluded_count || 0} excluded</span>
      </div>
    `;
    card.addEventListener('click', () => loadPatientDetail(p.id));
    cont.appendChild(card);
  });
}

async function loadPatientDetail(patientId) {
  try {
    const p = await api('GET', `/api/patients/${patientId}`);
    state.currentPatient = p;
    openPatientModal(p);
  } catch (e) {
    toast('Failed to load patient: ' + e.message, 'error');
  }
}

function openPatientModal(p) {
  const modal = document.getElementById('modal-overlay');
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');

  title.textContent = `${p.name} — Memory Profile`;

  const litUp = (p.feedback || []).filter(f => f.reaction === 'lit_up');
  const upset = (p.feedback || []).filter(f => f.reaction === 'upset');

  body.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:18px;">
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
        <div class="stat-card amber"><div class="stat-icon">◉</div><div class="stat-value">${p.birth_year}</div><div class="stat-label">Birth Year</div></div>
        <div class="stat-card emerald"><div class="stat-icon">⊕</div><div class="stat-value">${formatEra(p.birth_year).replace(' – ', '–')}</div><div class="stat-label" style="font-size:10px;">Golden Era</div></div>
        <div class="stat-card lilac"><div class="stat-icon">♦</div><div class="stat-value">${p.sessions?.length || 0}</div><div class="stat-label">Sessions</div></div>
      </div>
      <div>
        <div style="font-size:12px;font-weight:700;color:var(--text-muted);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px;">High-Affinity Triggers</div>
        ${litUp.length ? litUp.map(f => `<div style="padding:8px 12px;border-radius:8px;background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.2);margin-bottom:6px;font-size:13px;color:var(--lit-up);">🌟 ${f.entity_name}</div>`).join('') : '<div style="color:var(--text-muted);font-size:13px;">No recorded positive triggers yet</div>'}
      </div>
      ${upset.length ? `<div>
        <div style="font-size:12px;font-weight:700;color:var(--text-muted);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px;">Safety Exclusions</div>
        ${upset.map(f => `<div style="padding:8px 12px;border-radius:8px;background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.2);margin-bottom:6px;font-size:13px;color:var(--upset);">❌ ${f.entity_name}</div>`).join('')}
      </div>` : ''}
      <div style="display:flex;gap:10px;padding-top:6px;border-top:1px solid var(--border);">
        <button class="btn btn-primary" onclick="loadCareSheet('${p.id}');closeModal();">View Care Sheet</button>
        <button class="btn btn-secondary" onclick="prepareSessionForPatient('${p.id}');closeModal();">New Session</button>
      </div>
    </div>
  `;

  modal.classList.add('open');
}

/* ── Care Sheet View ────────────────────────────────────────────── */
async function loadCareSheet(patientId) {
  navigateTo('caresheet');
  const body = $('#care-sheet-body');
  if (body) body.innerHTML = '<div class="skeleton" style="height:400px;"></div>';

  try {
    const sheet = await api('GET', `/api/patients/${patientId}/care-sheet`);
    if (body) {
      const md = sheet.markdown
        .replace(/^# (.+)/gm, '<h1>$1</h1>')
        .replace(/^## (.+)/gm, '<h2>$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^- (.+)/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
        .replace(/^---$/gm, '<hr>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/^(?!<[h|u|l|p])/gm, '<p>');
      body.innerHTML = md;
    }
    toast('Care sheet loaded', 'success');
  } catch (e) {
    toast('Failed to load care sheet: ' + e.message, 'error');
  }
}

async function prepareSessionForPatient(patientId) {
  try {
    const p = await api('GET', `/api/patients/${patientId}`);
    navigateTo('intake');
    setTimeout(() => {
      document.getElementById('intake-name').value = p.name;
      document.getElementById('intake-birth-year').value = p.birth_year;
      document.getElementById('intake-hometown').value = p.hometown;
      document.getElementById('intake-culture').value = p.culture || '';
      document.getElementById('intake-patient-id').value = p.id;
      onBirthYearChange();
      state.intakeSeeds = (p.seeds || []).map(s => ({ name: s.name, type: s.entity_type }));
      renderSeedTags();
    }, 100);
  } catch (e) {
    toast('Failed to load patient: ' + e.message, 'error');
  }
}

/* ── Modals ─────────────────────────────────────────────────────── */
function openPresetModal() {
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');
  title.textContent = 'Quick-Load a Cultural Persona';
  body.innerHTML = '<div id="modal-preset-grid" class="preset-grid"></div>';
  document.getElementById('modal-overlay').classList.add('open');
  renderPresets('#modal-preset-grid', (preset) => prepareSessionWithPreset(preset));
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
}

/* ── Init ───────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', bootstrap);
