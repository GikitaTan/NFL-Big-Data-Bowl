/* Pure attention and trajectory functions. No browser, library or network dependency. */
(function (global) {
  'use strict';
  const FIELD_WIDTH = 160 / 3;
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const finite = x => typeof x === 'number' && Number.isFinite(x);

  function candidates(play, focusId, moverId) {
    // Identical candidate sets on both sides, including a newly eligible mover.
    return [...new Set(Object.values(play.players).filter(p => p.route).map(p => p.id)
      .concat([focusId, moverId].filter(id => play.players[id]?.offense)))];
  }

  function attention(play, frame, receiverIds) {
    const config = play.config;
    if (!(config.distanceScale > 0 && config.temperature > 0)) throw new Error('Invalid softmax scale');
    const receivers = frame.players.filter(p => receiverIds.includes(p.id));
    if (receivers.length !== receiverIds.length) throw new Error('Missing route candidate');
    const defenders = frame.players.filter(p => play.players[p.id].team === play.defense);
    const matrix = {}, totals = Object.fromEntries(receiverIds.map(id => [id, 0]));
    for (const d of defenders) {
      const heading = finite(d.o) ? d.o * Math.PI / 180 : null;
      const logits = receivers.map(r => {
        const dx = r.x - d.x, dy = r.y - d.y, distance = Math.hypot(dx, dy);
        const cosine = heading === null || distance < 1e-12 ? 0 :
          clamp((Math.sin(heading) * dx + Math.cos(heading) * dy) / distance, -1, 1);
        return -distance / config.distanceScale + config.directionWeight * cosine;
      });
      const max = Math.max(...logits), weights = logits.map(z => Math.exp((z - max) / config.temperature));
      const total = weights.reduce((a, b) => a + b, 0);
      matrix[d.id] = {};
      receivers.forEach((r, i) => { const a = weights[i] / total; matrix[d.id][r.id] = a; totals[r.id] += a; });
    }
    return {matrix, totals};
  }

  function scenarioEnd(play, scenario) {
    if (!scenario) return play.frames.length - 1;
    return Math.min(play.frames.length - 1, scenario.anchor + Math.round(scenario.horizon * 10));
  }

  function simulateFrame(play, index, scenario) {
    const frame = play.frames[index];
    if (!scenario || index < scenario.anchor) return {frame, boundary: false};
    if (index > scenarioEnd(play, scenario)) throw new Error('Frame outside simulation horizon');
    const origin = play.frames[scenario.anchor].players.find(p => p.id === scenario.moverId);
    if (!origin || !play.players[scenario.moverId].offense) throw new Error('Invalid mover');
    if (!finite(scenario.angle) || !finite(scenario.speed) || scenario.speed < 0 || scenario.speed > 12) {
      throw new Error('Invalid scenario motion');
    }
    const sign = play.playDirection === 'right' ? 1 : -1;
    const angle = scenario.angle * Math.PI / 180;
    const vx = sign * Math.cos(angle) * scenario.speed, vy = Math.sin(angle) * scenario.speed;
    const elapsed = (index - scenario.anchor) / 10;
    const tx = Math.abs(vx) < 1e-12 ? Infinity : ((vx > 0 ? 120 : 0) - origin.x) / vx;
    const ty = Math.abs(vy) < 1e-12 ? Infinity : ((vy > 0 ? FIELD_WIDTH : 0) - origin.y) / vy;
    const stop = Math.max(0, Math.min(tx, ty));
    const t = Math.min(elapsed, stop);
    const x = clamp(origin.x + vx * t, 0, 120), y = clamp(origin.y + vy * t, 0, FIELD_WIDTH);
    const nflHeading = (Math.atan2(vx, vy) * 180 / Math.PI + 360) % 360;
    return {frame: {...frame, players: frame.players.map(p => p.id === scenario.moverId ?
      {...p, x, y, dir: nflHeading, s: elapsed >= stop ? 0 : scenario.speed} : p)},
      boundary: elapsed >= stop && Number.isFinite(stop)};
  }

  function analyze(play, scenario, focusId, moverId) {
    const ids = candidates(play, focusId, scenario?.moverId || moverId);
    const end = scenarioEnd(play, scenario);
    const samples = [];
    for (let i = 0; i < play.frames.length; i++) {
      const baseline = attention(play, play.frames[i], ids);
      let simulated = null, frame = null, boundary = false;
      if (scenario && i >= scenario.anchor && i <= end) {
        const result = simulateFrame(play, i, scenario);
        frame = result.frame; boundary = result.boundary;
        simulated = attention(play, frame, ids);
      }
      samples.push({t: play.frames[i].t, baseline, simulated, frame, boundary});
    }
    return {ids, end, samples};
  }

  global.AttentionCore = {FIELD_WIDTH, clamp, candidates, attention, simulateFrame, scenarioEnd, analyze};
})(typeof globalThis !== 'undefined' ? globalThis : this);
