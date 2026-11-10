'use strict';
(() => {
  const C = window.AttentionCore, $ = id => document.getElementById(id);
  const ns = 'http://www.w3.org/2000/svg';
  let play = null, analysis = null, scenario = null, index = 3, moverId = '', focusId = '';
  let timer = null, loadVersion = 0, fieldGeometry = null, drag = null;
  const pct = v => (v * 100).toFixed(1) + '%';
  const signed = (v, digits = 2) => (v > 0 ? '+' : '') + v.toFixed(digits);

  function node(tag, attrs = {}, parent) {
    const e = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    parent?.append(e); return e;
  }
  function text(value, x, y, attrs, parent) {
    const e = node('text', {x, y, ...attrs}, parent); e.textContent = value; return e;
  }
  function option(select, value, label) {
    const o = document.createElement('option'); o.value = value; o.textContent = label; select.append(o);
  }
  function error(message = '') { $('error').textContent = message; $('error').hidden = !message; }
  async function api(path) {
    const r = await fetch(path); const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Unable to load data'); return data;
  }
  function pause() {
    if (timer !== null) clearInterval(timer);
    timer = null; $('play-button').textContent = '▶'; $('play-button').setAttribute('aria-label', 'Play replay');
  }
  function controls() {
    const angle = Number($('angle').value);
    $('angle-label').textContent = `${angle}° · ${Math.abs(angle) < 1 ? 'Forward' : Math.abs(angle) === 180 ? 'Backward' : angle < 0 ? 'Left' : 'Right'}`;
    $('speed-label').textContent = `${Number($('speed').value).toFixed(1)} yd/s`;
    $('horizon-label').textContent = `${Number($('horizon').value).toFixed(1)} s`;
    $('clear-button').disabled = !scenario; $('export-button').disabled = !scenario;
    if (!play) return;
    const added = analysis.ids.filter(id => !play.players[id].route);
    $('candidate-note').hidden = added.length === 0;
    $('candidate-note').textContent = added.length ? `${added.map(id => play.players[id].name).join(', ')}: outside the original route-candidate pool. Included in both original and simulated pools for a fair comparison.` : '';
    $('anchor-info').textContent = scenario ? `Start: ${(scenario.anchor / 10).toFixed(1)} s after snap, #${play.players[scenario.moverId].jersey} ${play.players[scenario.moverId].name}; compare through ${play.frames[analysis.end].t.toFixed(1)} s.` : 'Choose a time, then set the simulation start. You can also drag an offensive player on the field.';
    $('anchor-button').disabled = index >= play.frames.length - 1;
  }
  function recompute() {
    analysis = C.analyze(play, scenario, focusId, moverId);
    index = Math.min(index, analysis.end); controls(); render();
  }
  function selectMover(id) {
    pause(); moverId = id; scenario = null; $('mover-select').value = id;
    const p = play.frames[index].players.find(r => r.id === id);
    $('speed').value = p.s > .5 ? Math.min(12, p.s).toFixed(1) : '5.5';
    recompute();
  }
  function makeScenario() {
    if (!play || index >= play.frames.length - 1) return;
    pause(); scenario = {moverId, anchor: index, angle: Number($('angle').value),
      speed: Number($('speed').value), horizon: Number($('horizon').value)};
    recompute();
  }
  function updateScenario() {
    controls();
    if (!scenario) return;
    scenario = {...scenario, angle: Number($('angle').value), speed: Number($('speed').value), horizon: Number($('horizon').value)};
    recompute();
  }

  async function loadGame(gameId, selectedPlay = null) {
    pause(); const version = ++loadVersion; error();
    $('play-select').disabled = true; $('loading').hidden = false; $('workspace').hidden = true;
    try {
      const plays = await api(`/api/plays?gameId=${encodeURIComponent(gameId)}`);
      if (version !== loadVersion) return;
      $('play-select').replaceChildren();
      plays.forEach(p => option($('play-select'), p.playId, `Q${p.quarter} ${p.clock} · ${p.offense} · ${p.receiver} · Down ${p.down} · ${p.yardsToGo} yd · #${p.playId}`));
      const id = plays.some(p => p.playId === selectedPlay) ? selectedPlay : plays[0]?.playId;
      if (!id) throw new Error('No eligible completed-pass plays are available for this game');
      $('play-select').value = id; $('play-select').disabled = false;
      await loadPlay(gameId, id);
    } catch (e) { if (version === loadVersion) { error(e.message); $('loading').hidden = true; } }
  }

  async function loadPlay(gameId, playId) {
    pause(); const version = ++loadVersion; error();
    $('loading').hidden = false; $('workspace').hidden = true;
    try {
      const data = await api(`/api/play?gameId=${encodeURIComponent(gameId)}&playId=${encodeURIComponent(playId)}`);
      if (version !== loadVersion) return;
      play = data; scenario = null; index = Math.min(3, play.frames.length - 1);
      moverId = play.suggestedMover; focusId = play.targetId;
      const offense = Object.values(play.players).filter(p => p.offense).sort((a, b) => Number(a.jersey) - Number(b.jersey));
      for (const select of [$('focus-select'), $('mover-select')]) {
        select.replaceChildren(); offense.forEach(p => option(select, p.id, `#${p.jersey} ${p.name} · ${p.position}${p.id === play.targetId ? ' (target)' : ''}`));
      }
      $('focus-select').value = focusId; $('mover-select').value = moverId;
      $('field-title').textContent = `#${play.players[focusId].jersey} ${play.players[focusId].name}`;
      $('matchup').textContent = `${play.offense} OFFENSE  /  ${play.defense} DEFENSE`;
      $('play-id').textContent = `${gameId} / ${playId}`;
      $('play-description').textContent = play.description;
      $('angle').value = '0'; $('speed').value = '5.5'; $('horizon').value = '1.5';
      $('loading').hidden = true; $('workspace').hidden = false;
      history.replaceState(null, '', `/?game=${gameId}&play=${playId}`);
      recompute();
    } catch (e) { if (version === loadVersion) { error(e.message); $('loading').hidden = true; } }
  }

  function drawField(sample, baselineFrame, currentFrame) {
    const host = $('field'), width = Math.max(260, Math.floor(host.getBoundingClientRect().width));
    host.replaceChildren();
    const points = play.frames.flatMap(f => f.players).concat(analysis.samples.filter(s => s.frame).flatMap(s => s.frame.players));
    const xs = points.map(p => p.x);
    const lo = Math.max(0, Math.floor((Math.min(...xs) - 4) / 5) * 5), hi = Math.min(120, Math.ceil((Math.max(...xs) + 4) / 5) * 5);
    const left = 35, top = 25, desiredH = Math.min(650, Math.max(270, (width - 50) * (hi - lo) / C.FIELD_WIDTH));
    const scale = Math.min((width - 50) / C.FIELD_WIDTH, (desiredH - 12) / (hi - lo));
    const fieldW = C.FIELD_WIDTH * scale, fieldH = (hi - lo) * scale;
    const offset = left + Math.max(0, (width - 50 - fieldW) / 2);
    const height = top + fieldH + 25;
    const sx = y => offset + y * scale;
    const sy = x => top + (play.playDirection === 'right' ? hi - x : x - lo) * scale;
    const invert = (px, py) => ({y: (px - offset) / scale,
      x: play.playDirection === 'right' ? hi - (py - top) / scale : lo + (py - top) / scale});
    const svg = node('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': 'Observed player positions and simulated routes. Drag any offensive player to change their running direction.'}, host);
    fieldGeometry = {svg, sx, sy, invert};
    const defs = node('defs', {}, svg);
    const clip = node('clipPath', {id: 'field-clip'}, defs);
    node('rect', {x: sx(0), y: top, width: fieldW, height: fieldH}, clip);
    const marker = node('marker', {id: 'route-arrow', viewBox: '0 0 8 8', refX: 7, refY: 4, markerWidth: 5, markerHeight: 5, orient: 'auto'}, defs);
    node('path', {d: 'M0 0L8 4L0 8Z', fill: '#ce7542'}, marker);
    node('rect', {x: sx(0), y: top, width: fieldW, height: fieldH, fill: '#f0f6ee', stroke: '#b6cbb9', rx: 2}, svg);
    for (let x = lo; x <= hi; x++) {
      if (x % 5 === 0) {
        node('line', {x1: sx(0), x2: sx(C.FIELD_WIDTH), y1: sy(x), y2: sy(x), stroke: '#c9d9ca', 'stroke-width': x % 10 === 0 ? 1 : .6}, svg);
        if (x % 10 === 0 && x >= 10 && x <= 110) text(50 - Math.abs(x - 60), sx(0) - 8, sy(x) + 4, {'text-anchor': 'end', fill: '#91a996'}, svg);
      } else {
        for (const y of [0, 23.58, 29.75, C.FIELD_WIDTH]) node('line', {x1: sx(y) - (y === 0 ? 0 : 2.5), x2: sx(y) + (y === C.FIELD_WIDTH ? 0 : 2.5), y1: sy(x), y2: sy(x), stroke: '#c6d6c7'}, svg);
      }
    }
    text('Offense ↑', sx(0) + 4, 14, {}, svg);
    text('Yards · partial field', sx(C.FIELD_WIDTH), height - 6, {'text-anchor': 'end'}, svg);
    const los = sy(play.lineOfScrimmage);
    node('line', {x1: sx(0), x2: sx(C.FIELD_WIDTH), y1: los, y2: los, stroke: '#8da497', 'stroke-dasharray': '5 4'}, svg);
    text('Line of scrimmage', sx(C.FIELD_WIDTH) - 5, los - 6, {'text-anchor': 'end'}, svg);
    const content = node('g', {'clip-path': 'url(#field-clip)'}, svg);
    const target = currentFrame.players.find(p => p.id === focusId);
    const targetOld = baselineFrame.players.find(p => p.id === focusId);
    const weights = (sample.simulated || sample.baseline).matrix;
    const defenders = currentFrame.players.filter(p => play.players[p.id].team === play.defense);
    for (const p of defenders) {
      if (sample.simulated) node('line', {x1: sx(p.y), y1: sy(p.x), x2: sx(targetOld.y), y2: sy(targetOld.x), stroke: '#a9b6b6', 'stroke-width': .4 + 3 * sample.baseline.matrix[p.id][focusId], 'stroke-opacity': .35, 'stroke-dasharray': '3 3'}, content);
      const a = weights[p.id][focusId];
      node('line', {x1: sx(p.y), y1: sy(p.x), x2: sx(target.y), y2: sy(target.x), stroke: '#5866c9', 'stroke-width': .4 + 6 * a, 'stroke-opacity': .1 + .72 * a}, content);
      if (p.o !== null) {
        const rad = p.o * Math.PI / 180;
        node('line', {x1: sx(p.y), y1: sy(p.x), x2: sx(p.y + Math.cos(rad) * 1.7), y2: sy(p.x + Math.sin(rad) * 1.7), stroke: '#677b6e', 'stroke-width': 1, 'stroke-opacity': .7}, content);
      }
    }
    if (scenario) {
      const origin = play.frames[scenario.anchor].players.find(p => p.id === scenario.moverId);
      const terminal = analysis.samples[analysis.end].frame.players.find(p => p.id === scenario.moverId);
      node('line', {x1: sx(origin.y), y1: sy(origin.x), x2: sx(terminal.y), y2: sy(terminal.x), stroke: '#ce7542', 'stroke-width': 2, 'stroke-dasharray': '6 4', 'marker-end': 'url(#route-arrow)'}, content);
      if (sample.simulated) {
        const original = baselineFrame.players.find(p => p.id === scenario.moverId);
        node('circle', {cx: sx(original.y), cy: sy(original.x), r: 11, fill: 'none', stroke: '#9aa8aa', 'stroke-width': 1.5, 'stroke-dasharray': '3 2'}, content);
        text('O', sx(original.y), sy(original.x), {class: 'jersey', fill: '#809090'}, content);
      }
    }
    const ordered = [...currentFrame.players].sort((a, b) => (a.id === focusId) - (b.id === focusId));
    for (const p of ordered) {
      const meta = play.players[p.id], x = sx(p.y), y = sy(p.x);
      const g = node('g', {'data-player': p.id, class: meta.offense ? 'player' : ''}, content);
      const title = node('title', {}, g);
      title.textContent = `${meta.name}${meta.jersey ? ' #' + meta.jersey : ''}${weights[p.id] ? ' · attention ' + pct(weights[p.id][focusId]) : ''}`;
      if (p.id === 'football') { node('ellipse', {cx: x, cy: y, rx: 4, ry: 2.5, fill: '#465b4c', transform: `rotate(-30 ${x} ${y})`}, g); continue; }
      if (p.id === moverId) node('circle', {cx: x, cy: y, r: 15, fill: 'none', stroke: '#ce7542', 'stroke-width': 1.5, 'stroke-dasharray': '3 2'}, g);
      if (p.id === focusId) node('circle', {cx: x, cy: y, r: 13, fill: 'none', stroke: '#5866c9', 'stroke-width': 2}, g);
      const fill = p.id === focusId ? '#e4e6fa' : meta.offense ? '#e1eee5' : '#f5e3d5';
      if (meta.offense) node('circle', {cx: x, cy: y, r: 9.5, fill, stroke: '#557b68', 'stroke-width': 1}, g);
      else node('rect', {x: x - 8.5, y: y - 8.5, width: 17, height: 17, rx: 3, fill, stroke: '#ad7851', 'stroke-width': 1}, g);
      text(meta.jersey, x, y, {class: 'jersey'}, g);
      node('circle', {cx: x, cy: y, r: 13, fill: 'transparent'}, g);
    }
    // Keep numeric labels for the five largest weights; the table retains all eleven.
    const labels = [...defenders].sort((a, b) => weights[b.id][focusId] - weights[a.id][focusId]).slice(0, 5)
      .map(p => ({p, x: C.clamp(sx(p.y) + 14, sx(0) + 4, sx(C.FIELD_WIDTH) - 37), y: C.clamp(sy(p.x) - 15, top + 16, top + fieldH - 10)}));
    for (let step = 0; step < 35; step++) for (let i = 0; i < labels.length; i++) {
      const a = labels[i];
      for (let j = i + 1; j < labels.length; j++) {
        const b = labels[j];
        if (Math.abs(a.x - b.x) < 42 && Math.abs(a.y - b.y) < 17) { a.y -= 1.5; b.y += 1.5; }
      }
      a.y = C.clamp(a.y, top + 17, top + fieldH - 12);
    }
    for (const a of labels) {
      node('line', {x1: sx(a.p.y), y1: sy(a.p.x), x2: a.x, y2: a.y - 4, stroke: '#8a9d91', 'stroke-width': .6}, content);
      text(pct(weights[a.p.id][focusId]), a.x, a.y, {'paint-order': 'stroke', stroke: '#f0f6ee', 'stroke-width': 3, 'stroke-linejoin': 'round'}, content);
    }
  }

  function drawChart() {
    const host = $('chart'), width = Math.max(280, Math.floor(host.getBoundingClientRect().width)), height = 205;
    host.replaceChildren(); const svg = node('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': 'Original and simulated total attention over time. Click the chart to select a time.'}, host);
    const left = 43, right = width - 16, top = 22, bottom = height - 36;
    const maxTime = play.frames[play.frames.length - 1].t || .1;
    const maxY = Math.max(.5, ...analysis.samples.map(s => s.baseline.totals[focusId]), ...analysis.samples.filter(s => s.simulated).map(s => s.simulated.totals[focusId])) * 1.1;
    const sx = t => left + t / maxTime * (right - left), sy = a => bottom - a / maxY * (bottom - top);
    for (let i = 0; i <= 3; i++) {
      const value = maxY * i / 3, y = sy(value);
      node('line', {x1: left, x2: right, y1: y, y2: y, stroke: '#e7edec'}, svg);
      text(value.toFixed(1), left - 8, y + 4, {'text-anchor': 'end'}, svg);
    }
    const ticks = width < 450 ? 3 : 5;
    for (let i = 0; i <= ticks; i++) {
      const t = maxTime * i / ticks; text(t.toFixed(1), sx(t), bottom + 19, {'text-anchor': i === 0 ? 'start' : i === ticks ? 'end' : 'middle'}, svg);
    }
    text('Total weight', left, 12, {}, svg); text('Time after snap (s)', (left + right) / 2, height - 3, {'text-anchor': 'middle'}, svg);
    const path = (samples, key) => samples.map((s, i) => `${i ? 'L' : 'M'}${sx(s.t)},${sy(s[key].totals[focusId])}`).join(' ');
    node('path', {d: path(analysis.samples, 'baseline'), fill: 'none', stroke: '#9daeb3', 'stroke-width': 2}, svg);
    if (scenario) {
      const samples = analysis.samples.filter(s => s.simulated);
      node('path', {d: path(samples, 'simulated'), fill: 'none', stroke: '#187b72', 'stroke-width': 2.5}, svg);
      const x = sx(play.frames[scenario.anchor].t);
      node('line', {x1: x, x2: x, y1: top, y2: bottom, stroke: '#ce7542', 'stroke-dasharray': '3 3'}, svg);
      text('Branch', x + (x > right - 30 ? -4 : 4), top + 10, {'text-anchor': x > right - 30 ? 'end' : 'start'}, svg);
    }
    const x = sx(play.frames[index].t);
    node('line', {x1: x, x2: x, y1: top, y2: bottom, stroke: '#4b645c', 'stroke-width': 1}, svg);
    const sample = analysis.samples[index];
    for (const [key, color] of [['baseline', '#9daeb3'], ['simulated', '#187b72']]) if (sample[key]) node('circle', {cx: x, cy: sy(sample[key].totals[focusId]), r: 3.5, fill: color}, svg);
    svg.addEventListener('click', event => {
      const pt = svg.createSVGPoint(); pt.x = event.clientX; pt.y = event.clientY;
      const local = pt.matrixTransform(svg.getScreenCTM().inverse());
      pause(); index = C.clamp(Math.round((local.x - left) / (right - left) * maxTime * 10), 0, analysis.end); render();
    });
  }

  function render() {
    if (!play || !analysis) return;
    const sample = analysis.samples[index], baselineFrame = play.frames[index];
    const currentFrame = sample.frame || baselineFrame;
    const b = sample.baseline.totals[focusId], s = sample.simulated?.totals[focusId];
    $('timeline').max = analysis.end; $('timeline').value = index;
    $('timeline').setAttribute('aria-valuetext', `${baselineFrame.t.toFixed(1)} s, frame ${baselineFrame.frameId}`);
    $('time-label').textContent = `After snap: ${baselineFrame.t.toFixed(1)} s · Frame ${baselineFrame.frameId}`;
    $('end-label').textContent = `${play.frames[analysis.end].t.toFixed(1)} s · ${scenario && analysis.end < play.frames.length - 1 ? 'Simulation end' : 'Before release'}`;
    $('step-back').disabled = index === 0; $('step-forward').disabled = index === analysis.end;
    $('anchor-button').disabled = index >= play.frames.length - 1;
    $('field-title').textContent = `#${play.players[focusId].jersey} ${play.players[focusId].name}`;
    $('comparison-name').textContent = `Focus: ${play.players[focusId].name}`;
    $('baseline-total').textContent = b.toFixed(2);
    $('simulated-total').textContent = s === undefined ? '—' : s.toFixed(2);
    $('delta-total').textContent = s === undefined ? '—' : signed(s - b);
    $('delta-total').className = s === undefined ? '' : s - b >= 0 ? 'positive' : 'negative';
    $('mode-tag').textContent = sample.simulated ? 'Simulation active' : scenario ? 'Before branch' : 'Observed replay';
    $('mode-tag').classList.toggle('active', !!sample.simulated);
    $('field-status').textContent = sample.boundary ? 'The simulated player has reached the field boundary and stopped. All other players and the ball follow observed trajectories.' :
      scenario ? 'The dashed outline marks the original position; the orange dashed line is the simulated route. Defenders and the ball follow observed trajectories.' :
        'Click or drag an offensive player to change their route. The field labels the five highest weights; the table includes all 11 defenders.';
    const body = $('defender-body'); body.replaceChildren();
    Object.keys(sample.baseline.matrix).sort((a, z) => sample.baseline.matrix[z][focusId] - sample.baseline.matrix[a][focusId]).forEach(id => {
      const old = sample.baseline.matrix[id][focusId], now = sample.simulated?.matrix[id][focusId];
      const tr = document.createElement('tr');
      [play.players[id].name, pct(old), now === undefined ? '—' : pct(now), now === undefined ? '—' : signed((now - old) * 100, 1) + 'pp'].forEach((value, i) => {
        const td = document.createElement('td'); td.textContent = value;
        if (i === 3 && now !== undefined) td.className = now - old >= 0 ? 'positive' : 'negative'; tr.append(td);
      }); body.append(tr);
    });
    drawField(sample, baselineFrame, currentFrame); drawChart();
  }

  $('game-select').addEventListener('change', () => loadGame($('game-select').value));
  $('play-select').addEventListener('change', () => loadPlay($('game-select').value, $('play-select').value));
  $('mover-select').addEventListener('change', () => { if (play) selectMover($('mover-select').value); });
  $('focus-select').addEventListener('change', () => { if (play) { focusId = $('focus-select').value; recompute(); } });
  $('anchor-button').addEventListener('click', makeScenario);
  for (const id of ['angle', 'speed', 'horizon']) $(id).addEventListener('input', updateScenario);
  document.querySelectorAll('[data-angle]').forEach(b => b.addEventListener('click', () => { $('angle').value = b.dataset.angle; updateScenario(); }));
  $('clear-button').addEventListener('click', () => { pause(); scenario = null; recompute(); });
  $('timeline').addEventListener('input', () => { pause(); index = Number($('timeline').value); render(); });
  $('step-back').addEventListener('click', () => { pause(); index = Math.max(0, index - 1); render(); });
  $('step-forward').addEventListener('click', () => { pause(); index = Math.min(analysis.end, index + 1); render(); });
  $('play-button').addEventListener('click', () => {
    if (!play) return;
    if (timer !== null) return pause();
    if (index >= analysis.end) index = 0;
    $('play-button').textContent = 'Ⅱ'; $('play-button').setAttribute('aria-label', 'Pause replay');
    render(); timer = setInterval(() => { if (document.hidden) return pause(); index = Math.min(index + 1, analysis.end); render(); if (index === analysis.end) pause(); }, 100);
  });
  $('export-button').addEventListener('click', () => {
    if (!scenario) return;
    const report = {gameId: play.gameId, playId: play.playId, focusId, focusName: play.players[focusId].name,
      scenario: {...scenario, moverName: play.players[scenario.moverId].name, anchorTime: play.frames[scenario.anchor].t},
      config: play.config, candidateIds: analysis.ids, assumption: 'Only the mover changes; defenders and ball follow observed trajectories.',
      comparison: analysis.samples.filter(s => s.simulated).map(s => ({t: s.t, baseline: s.baseline.totals[focusId], simulated: s.simulated.totals[focusId], delta: s.simulated.totals[focusId] - s.baseline.totals[focusId]}))};
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = `scenario-${play.gameId}-${play.playId}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  function fieldPoint(event) {
    const pt = fieldGeometry.svg.createSVGPoint(); pt.x = event.clientX; pt.y = event.clientY;
    return pt.matrixTransform(fieldGeometry.svg.getScreenCTM().inverse());
  }
  $('field').addEventListener('pointerdown', event => {
    if (!play || event.button !== 0) return;
    const id = event.target.closest('[data-player]')?.getAttribute('data-player');
    if (!id || !play.players[id].offense || index >= play.frames.length - 1) return;
    event.preventDefault(); pause(); selectMover(id);
    const origin = play.frames[index].players.find(p => p.id === id);
    const start = {x: fieldGeometry.sx(origin.y), y: fieldGeometry.sy(origin.x)};
    const preview = node('line', {x1: start.x, y1: start.y, x2: start.x, y2: start.y, stroke: '#ce7542', 'stroke-width': 2, 'stroke-dasharray': '5 3'}, fieldGeometry.svg);
    drag = {id, origin, start, preview, moved: false}; $('field').setPointerCapture(event.pointerId);
  });
  $('field').addEventListener('pointermove', event => {
    if (!drag) return;
    const point = fieldPoint(event);
    drag.preview.setAttribute('x2', point.x); drag.preview.setAttribute('y2', point.y);
    drag.moved = Math.hypot(point.x - drag.start.x, point.y - drag.start.y) > 8;
  });
  $('field').addEventListener('pointerup', event => {
    if (!drag) return;
    const currentDrag = drag; drag = null;
    if (!currentDrag.moved) { currentDrag.preview.remove(); return; }
    const point = fieldPoint(event), destination = fieldGeometry.invert(point.x, point.y);
    const sign = play.playDirection === 'right' ? 1 : -1;
    const angle = Math.atan2(destination.y - currentDrag.origin.y, sign * (destination.x - currentDrag.origin.x)) * 180 / Math.PI;
    $('angle').value = Math.round(angle); makeScenario();
  });
  $('field').addEventListener('pointercancel', () => { if (drag) { drag.preview.remove(); drag = null; } });
  let resizePending = null;
  window.addEventListener('resize', () => { clearTimeout(resizePending); resizePending = setTimeout(() => { if (play && !drag) render(); }, 100); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });

  async function init() {
    try {
      const catalog = await api('/api/catalog');
      catalog.games.forEach(g => option($('game-select'), g.gameId, `${g.gameDate} · ${g.visitorTeamAbbr} @ ${g.homeTeamAbbr} · ${g.playCount} plays`));
      $('cohort-label').textContent = `${catalog.games.length} games / ${catalog.playCount.toLocaleString()} plays`;
      $('game-select').disabled = false;
      const query = new URLSearchParams(location.search);
      const game = catalog.games.some(g => g.gameId === query.get('game')) ? query.get('game') : catalog.defaultGame;
      $('game-select').value = game;
      await loadGame(game, query.get('play') || catalog.defaultPlay);
    } catch (e) { error(e.message); $('loading').hidden = true; }
  }
  init();
})();
