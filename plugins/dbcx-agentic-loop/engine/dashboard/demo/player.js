// Demo mode of the run dashboard: plays the bundled recording (recording.js, window.DBCX_DEMO) in the browser in the shapes of /api/state and
// /api/scope, and answers the page's writes in memory the way the orchestrator would: a sent answer, keep or reopen shows as awaiting and is
// applied a few seconds later, a pause is acknowledged and holds the recording, a checkpoint refreshes the report's date, a changed cell of a
// method panel ("Impact per system", "Gap decisions") shows as awaiting and is then recorded as an override. Nothing is sent, started or saved. dashboard.html loads this file only when it is opened from file:// with ?demo=1 or #demo.
window.DBCX_DEMO_PLAYER = (R, changed, seen) => {   // seen: the page's read marks, set to the recording's own at the start and after a jump
  'use strict';
  const TS = /^(\d{4})-(\d\d)-(\d\d)([T ])(\d\d):(\d\d)(?::(\d\d))?$/, p2 = n => String(n).padStart(2, '0');
  const at = (ms, sep = 'T', sec = true) => { const d = new Date(ms); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}${sep}${p2(d.getHours())}:${p2(d.getMinutes())}${sec ? ':' + p2(d.getSeconds()) : ''}`; };
  const ms = m => new Date(+m[1], m[2] - 1, +m[3], +m[5], +m[6], +(m[7] || 0)).getTime();
  // recorded times are relative to the anchor; t=0 of the recording is the moment the page opened
  let off = Date.now() - ms(TS.exec(R.anchor));
  const shift = v => { if (typeof v === 'string') { const m = TS.exec(v); return m ? at(ms(m) + off, m[4], m[7] != null) : v; }
    if (Array.isArray(v)) return v.map(shift); if (v && typeof v === 'object') { const o = {}; for (const k in v) o[k] = shift(v[k]); return o; } return v; };
  const now = () => at(Date.now()), id = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).replace(/-/g, '');
  let clock = 0, last = Date.now(), fi = 0, S = {};
  const mine = { q: {}, control: {}, inbox: [], history: [], narrative: null }; let epoch = 0;
  const KEY = { questions: 'id', analysts: 'scope' };   // a frame's upsert carries only the changed records of these lists
  const upsert = u => { for (const k in u) { const out = S[k].slice(); u[k].forEach(x => { const i = out.findIndex(y => y[KEY[k]] === x[KEY[k]]); if (i < 0) out.push(x); else out[i] = x; }); S[k] = out; } };
  function play() {   // the recording runs while the run is not paused (a paused run starts nothing new)
    const t = Date.now(); if (!mine.control.pause_ack_at) clock += (t - last) / 1000; last = t;
    let moved = false; while (fi < R.frames.length && R.frames[fi].t <= clock) { const f = R.frames[fi++]; S = Object.assign({}, S, f.state || {}, f.patch || {}); upsert(f.upsert || {}); moved = true; }
    return moved;
  }
  // the questions the recorded lead has already read (the page marks a question read with its updated_at)
  function read(reset) { if (reset) Object.keys(seen).forEach(k => delete seen[k]); const s = state(); (R.seen || []).forEach(qid => { const q = s.questions.find(x => x.id === qid); if (q) seen[qid] = q.updated_at; }); }
  play(); read(false); setInterval(() => { if (play()) changed(); }, 1000);
  const later = (sec, fn) => { const e = epoch; setTimeout(() => { if (e !== epoch) return; fn(); changed(); }, sec * 1000); };   // a jump drops what was pending
  // a jump to a milestone: the recording up to t at once, the viewer's own state dropped, recorded t now "now", playing on from there
  function jump(t) {
    epoch++; Object.assign(mine, { q: {}, control: {}, inbox: [], history: [], narrative: null });
    clock = t; fi = 0; S = {}; last = Date.now(); off = Date.now() - t * 1000 - ms(TS.exec(R.anchor)); play(); read(true); changed();
  }
  const MS = R.milestones || [], nextMs = () => MS.find(m => m.t > clock + 0.5);
  const TIP = 'Jumps the recording forward and keeps playing from there. Your own answers, keeps, hints, pauses and read marks from before the jump are discarded.';
  function mount(before) {   // the milestone control lives only in the demo marker, built here: a served page never has it in its DOM
    const el = document.createElement('div'); el.className = 'demo'; el.id = 'demoTag';
    el.innerHTML = `<span title="A recorded, fictional run played in this browser: nothing is sent, saved or started, and nothing needs to be stopped.">Demo · fictional project</span><button class="dm" id="demoNext" title="${TIP}">Next milestone ▸</button><button class="dm" id="demoMenu" aria-expanded="false" aria-haspopup="menu" title="All milestones and Restart demo">Skip to ▾</button><div class="dmenu" id="demoMenuPop" role="menu" hidden></div>`;
    before.parentNode.insertBefore(el, before);
    const pop = el.querySelector('#demoMenuPop'), btn = el.querySelector('#demoNext');
    const render = () => { const n = nextMs(); btn.disabled = !n; btn.textContent = n ? 'Next milestone ▸' : 'At the end'; btn.title = n ? `${n.label} – ${TIP}` : 'The recording has reached its end. Restart the demo from the menu.';
      pop.innerHTML = `<div class="dmh" title="${TIP}">Skip to · your own actions before a jump are discarded</div>` + MS.map((m, i) => `<button role="menuitem" data-ms="${i}" class="${m.t <= clock + 0.5 ? 'past' : ''}">${m.t <= clock + 0.5 ? '✓ ' : ''}${m.label}</button>`).join('') + '<button role="menuitem" data-ms="restart">↺ Restart demo</button>'; };
    const close = () => { pop.hidden = true; el.querySelector('#demoMenu').setAttribute('aria-expanded', 'false'); };
    btn.addEventListener('click', () => { const n = nextMs(); if (n) jump(n.t); render(); });
    el.querySelector('#demoMenu').addEventListener('click', e => { e.stopPropagation(); render(); pop.hidden = !pop.hidden; el.querySelector('#demoMenu').setAttribute('aria-expanded', String(!pop.hidden)); });
    pop.addEventListener('click', e => { const b = e.target.closest('[data-ms]'); if (!b) return; e.stopPropagation(); close(); if (b.dataset.ms === 'restart') location.reload(); else { jump(MS[+b.dataset.ms].t); render(); } });
    document.addEventListener('click', e => { if (!el.contains(e.target)) close(); });
    render(); setInterval(render, 2000);
  }
  const log = msg => mine.history.push({ t: at(Date.now(), ' ', false), msg });
  function state() {
    const s = shift(S), qs = s.questions.map(q => mine.q[q.id] ? JSON.parse(JSON.stringify(mine.q[q.id])) : q), ib = s.inbox;
    const gfb = mine.inbox.filter(e => e.kind === 'gate_question_feedback').map(e => ({ client_id: e.client_id, persona: e.persona, question_id: e.question_id, round: e.round, intent: e.intent, text: e.text, at: e.at, processed: e.processed, outcome: e.outcome || null, change: null }));
    s.gate = Object.assign({}, s.gate, { feedback: s.gate.feedback.concat(gfb) });
    return Object.assign(s, { questions: qs, control: Object.assign({}, mine.control), history: s.history.concat(mine.history).slice(-10),
      inbox: { total: ib.total + mine.inbox.length, unprocessed: ib.unprocessed + mine.inbox.filter(e => !e.processed).length, recent: ib.recent.concat(mine.inbox.map(e => ({ client_id: e.client_id, kind: e.kind, at: e.at, processed: e.processed, outcome: e.outcome || null, scope: e.scope || null, claim_id: e.claim_id || null, id: e.id || null, command: e.command || null }))).slice(-8) },
      narrative: mine.narrative ? Object.assign(s.narrative, { as_of: mine.narrative }) : s.narrative, computed_at: now(), server: Object.assign(s.server, { time: now() }),
      ...(s.panels ? { panels: s.panels.map(panelOverlay) } : {}) });
  }
  // the viewer's own cell edits over the recorded panel: applied ones change the cell (source override) and mark the work package, pending ones wait.
  // A panel whose edit actions lack "remove" keeps ONE cell per row (the architect's "Gap decisions": a gap keeps one decision) - an add on
  // another column moves the decision there, and the follow-up is the cell <row>@<column> of the receiving system.
  const single = P => !((P.edit || {}).actions || []).includes('remove');
  function panelOverlay(P) {
    const ed = mine.inbox.filter(e => e.kind === 'panel_edit' && e.panel === P.id); if (!ed.length) return P;
    const Q = JSON.parse(JSON.stringify(P)), one = single(Q);
    ed.filter(e => e.processed).forEach(e => {
      const r = Q.rows.find(x => x.id === e.row); let c = r.cells.find(x => x.column === e.column); const was = !!(c && c.on);
      if (!c) { c = { column: e.column, on: false, text: '', source: 'override', status: 'overridden', reason: '', claims: [] }; r.cells.push(c); }
      if (one) r.cells = [c];
      Object.assign(c, { on: e.action !== 'remove', text: e.action === 'remove' ? '' : e.text, source: 'override', status: 'overridden' }, e.reason ? { reason: e.reason } : {});
      Q.changes.push({ key: one ? `${e.row.split('@')[0]}@${e.column}` : `${e.row}@${e.column}`, change: e.action === 'remove' ? 'withdrawn' : was ? 're-brief' : 'new' }); Q.changes_note = Q.changes_note || (one ? 'follow-up work packages wait for the next wave' : 'work-package changes wait for the next wave');
    });
    Q.pending = Q.pending.concat(ed.filter(e => !e.processed).map(e => ({ client_id: e.client_id, row: e.row, column: e.column, action: e.action, text: e.text, reason: e.reason, at: e.at })));
    return Q;
  }
  function scope(name) {
    const list = R.scopes[name] || [], cur = list.filter(d => d.t <= clock).pop();
    const d = cur ? shift(cur.detail) : { scope: name, threshold: S.pass_threshold, analyst: null, claims_total: 0, below: [], passing: [], scope_hints: [], hints: [] };
    mine.inbox.filter(e => e.scope === name && /^(analyst_hint|critic_fact|critic_hint)$/.test(e.kind)).forEach(e => {
      const h = Object.assign({}, e, { status: e.processed ? 'applied' : 'received', note: e.outcome || '' }), c = e.claim_id && d.below.concat(d.passing).find(x => x.id === e.claim_id);
      if (c) c.hints.push(h); else if (!e.claim_id) d.scope_hints.push(h);
    });
    return d;
  }
  // ---- writes: validated like the server, applied like the orchestrator's next step
  const qOf = qid => state().questions.find(q => q.id === qid);
  const put = q => { mine.q[q.id] = q; };
  function inbox(e) { const x = Object.assign({ client_id: id(), at: now(), processed: false, by: 'lead', channel: 'dashboard' }, e); mine.inbox.push(x); return x; }
  const done = (x, outcome) => { x.processed = true; x.processed_at = now(); x.outcome = outcome; };
  function applyAnswer(qid, b, x) {
    const qs = state().questions, q = qs.find(y => y.id === qid), t = now(), w = q.kind === 'ruling' ? 'fact' : b.weight;
    const e = { option: b.option, text: b.text, weight: w, by: 'lead', at: t, channel: 'dashboard', status: 'received', type: w === 'fact' ? 'decision' : 'working-assumption' };
    for (const y of [q].concat(qs.filter(d => d.duplicate_of === q.id && !d.answers.length))) {
      const a = y === q ? e : Object.assign({}, e, { channel: 'duplicate', duplicate_of: q.id });
      y.answers = y.answers.concat([a]); y.answer = a; y.pending = null; y.updated_at = t; delete y.resolution; delete y.kept;
      if (y.kind === 'ruling') y.status = 'applied'; else Object.assign(y, { status: 'answered_draft', answered_by: 'lead', qualification: w === 'fact' ? 'client-evidence weight (lead states it as fact)' : 'proposal - weigh against client evidence' });
      put(y);
    }
    done(x, `answer registered (${w})`); log(`inbox: answer ${qid} applied as ${w}`);
  }
  function applyKeep(qid, kind, x) {
    const qs = state().questions, q0 = qs.find(y => y.id === qid), q = q0.duplicate_of ? qs.find(y => y.id === q0.duplicate_of) || q0 : q0, t = now();
    if (kind === 'keep') {
      for (const y of [q].concat(qs.filter(d => d.duplicate_of === q.id && !d.answers.length && d.status !== 'closed')))
        put(Object.assign(y, { kept: Object.assign({ at: t, by: 'lead', channel: 'dashboard', status_before: y.status || 'open' }, y === q ? {} : { via: q.id }), resolution: 'assumption_kept', status: 'closed', pending: null, updated_at: t }));
      done(x, 'closed - assumption kept, nothing to route'); log(`inbox: keep ${q.id} - closed, the assumption stays`);
    } else {
      for (const y of [q].concat(qs.filter(d => (d.kept || {}).via === q.id && d.status === 'closed'))) {
        const k = y.kept || {}; delete y.kept; delete y.resolution;
        put(Object.assign(y, { reopened: (y.reopened || []).concat([{ at: t, kept_at: k.at }]), status: k.status_before || 'open', pending: null, updated_at: t }));
      }
      done(x, 'reopened'); log(`inbox: reopen ${q.id}`);
    }
    const y = state().questions.find(z => z.id === q0.id); if (y.pending) { y.pending = null; put(y); }   // a duplicate is redirected to its primary
  }
  function answer(b) {
    const q = qOf(b.id); if (!q) return { error: 'no such question' };
    if (b.kind === 'keep' || b.kind === 'reopen') {
      if (q.kind === 'ruling') return { error: 'a ruling is answered, not kept' };
      if ((b.kind === 'keep') === (q.status === 'closed')) return { error: `${q.id} is ${q.status}` };
      const x = inbox({ kind: b.kind, id: q.id }); put(Object.assign(q, { pending: { kind: b.kind, option: null, text: null, weight: null, at: x.at } }));
      later(5, () => applyKeep(q.id, b.kind, x)); return { ok: true, entry: x };
    }
    const text = (b.text || '').trim(); if (!(b.option || text)) return { error: 'choose an option or write an answer' };
    const body = { option: b.option || '', text, weight: q.kind === 'ruling' ? 'fact' : b.weight || 'proposal' };
    const x = inbox(Object.assign({ kind: 'answer', id: q.id }, body)); put(Object.assign(q, { pending: Object.assign({ kind: 'answer', at: x.at }, body) }));
    later(6, () => applyAnswer(q.id, body, x)); return { ok: true, entry: x };
  }
  const OUT = { analyst_hint: s => `appended to analysis/briefs/lead-hints-${s}.md; the analyst gets it as a hypothesis`, critic_fact: () => 'registered as a lead fact; the critic re-scores the claim against it',
    critic_hint: () => 'handed to the critic for a re-check', knowledge: () => 'knowledge-base candidate registered; the orchestrator words it and decides where it applies' };
  function gateFeedback(b, text) {   // validated like the server: a gate persona, the question asked in that round, an intent, a text
    const r = state().gate.rounds.find(x => x.round === b.round), nd = r && r.nodes.find(x => x.id === b.persona && x.kind === 'persona');
    if (!nd) return { error: `${b.persona} is not a gate persona` };
    if (!/^(dismiss|rephrase|other)$/.test(b.intent || '')) return { error: 'intent dismiss|rephrase|other' };
    if (!nd.questions.some(q => q.id === b.question_id)) return { error: `${b.persona} is not asked ${b.question_id} in round ${b.round}` };
    const x = inbox({ kind: 'gate_question_feedback', persona: b.persona, question_id: b.question_id, round: b.round, intent: b.intent, text });
    later(8, () => { done(x, 'kept unchanged: this is a recorded demo, so the orchestrator leaves the question as it is'); log(`inbox: gate question feedback on ${b.question_id} applied`); }); return { ok: true, entry: x };
  }
  function panelEdit(b) {   // validated like the server (the method's check): the cell exists, add only an untouched one, a text to add / edit, a reason to remove
    const P = (state().panels || []).find(p => p.id === b.panel); if (!P) return { error: `unknown panel ${b.panel}` };
    const r = P.rows.find(x => x.id === b.row), col = P.columns.find(x => x.id === b.column); if (!r || !col) return { error: 'no such cell' };
    const c = r.cells.find(x => x.column === b.column), on = !!(c && c.on), text = (b.text || '').trim(), reason = (b.reason || '').trim();
    if (!/^(add|remove|edit)$/.test(b.action || '')) return { error: `action ${b.action} (add | remove | edit)` };
    if (single(P) && b.action === 'remove') return { error: 'a gap keeps a decision - click the system that should carry it, or edit the solution text' };
    if (b.action === 'add' && on) return { error: `${b.row} already touches ${b.column} - edit its impact text instead` };
    if (b.action !== 'add' && !on) return { error: `${b.row} does not touch ${b.column}` };
    if (b.action !== 'remove' && !text) return { error: 'the impact text is required (what changes in that system)' };
    if (b.action === 'remove' && !reason) return { error: 'a removal needs its reason' };
    const x = inbox({ kind: 'panel_edit', panel: b.panel, row: b.row, column: b.column, action: b.action, text: b.action === 'remove' ? '' : text, reason });
    const R0 = (S.panels || []).find(p => p.id === P.id) || P, n = mine.inbox.filter(e => e.kind === 'panel_edit' && e.panel === P.id).length + R0.rows.reduce((k, r) => k + r.cells.filter(c => c.status === 'overridden').length, 0);   // the recorded overrides count too
    const out = single(P) ? `AO-${String(1000 + n).slice(1)}: ${b.row} -> ${b.column} recorded; the follow-up work packages wait for the next wave` : `${b.row} x ${b.column} ${b.action} recorded; the work package is marked for the next wave`;
    later(6, () => { done(x, out); log(`inbox: panel edit ${b.row} x ${b.column} ${b.action} applied`); }); return { ok: true, entry: x };
  }
  function generic(b) {
    if (b.kind === 'panel_edit') return panelEdit(b);
    const text = (b.text || '').trim(); if (b.kind === 'gate_question_feedback' && text) return gateFeedback(b, text); if (!OUT[b.kind] || !text) return { error: 'kind and text required' };
    const x = inbox(b.kind === 'knowledge' ? { kind: b.kind, scopes: (b.scopes || []).filter(Boolean), text } : { kind: b.kind, scope: b.scope, claim_id: b.claim_id || null, critic: b.critic || null, text });
    later(8, () => { done(x, OUT[b.kind](b.scope)); log(`inbox: ${b.kind.replace('_', ' ')}${b.scope ? ' for ' + b.scope : ''} applied`); }); return { ok: true, entry: x };
  }
  function command(b) {
    const c = b.command, t = now(), ctl = mine.control; if (!/^(pause|resume|checkpoint)$/.test(c || '')) return { error: 'command pause|resume|checkpoint' };
    if (c === 'pause') { Object.assign(ctl, { pause_requested: true, pause_requested_at: t, pause_ack_at: null, paused_at: null }); later(4, () => { if (ctl.pause_requested) { ctl.pause_ack_at = ctl.paused_at = now(); log('pause acknowledged: no new agents start, state saved'); } }); }
    else if (c === 'resume') { Object.assign(ctl, { pause_requested: false, resumed_at: t, pause_ack_at: null, paused_at: null }); last = Date.now(); log('resumed'); }
    else { ctl.checkpoint_requested_at = t; later(8, () => { delete ctl.checkpoint_requested_at; ctl.checkpoint_done_at = mine.narrative = now(); log('checkpoint: progress report and interim workbooks written'); }); }
    const x = inbox({ kind: 'command', command: c }); later(c === 'checkpoint' ? 8 : 4, () => done(x, c + ' applied')); return { ok: true, entry: x };
  }
  const W = { '/api/answer': answer, '/api/inbox': generic, '/api/command': command };
  return {
    state, scope, mount,
    post: (path, body) => { const r = W[path] ? W[path](body || {}) : { error: 'not found' }; changed(); return r; },
  };
};
