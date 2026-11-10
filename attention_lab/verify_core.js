/* Runs in a JS VM with AttentionCore and fixture supplied by the test runner. */
(() => {
  const C = globalThis.AttentionCore, f = globalThis.fixture;
  let assertions = 0;
  const assert = (condition, message) => { assertions++; if (!condition) throw new Error(message); };
  const close = (a, b) => Math.abs(a - b) < 1e-11;
  for (const test of f.plays) {
    const p = test.play, ids = C.candidates(p, p.targetId, p.suggestedMover);
    for (const [i, frame] of p.frames.entries()) {
      const result = C.attention(p, frame, ids);
      for (const [defender, expected] of Object.entries(test.expected[i])) {
        assert(close(result.matrix[defender][p.targetId], expected), 'JS/Python attention mismatch');
        assert(close(Object.values(result.matrix[defender]).reduce((a,b)=>a+b,0),1), 'Normalization');
      }
    }
    const scenario = {moverId: p.suggestedMover, anchor: 3, angle: 90, speed: 7, horizon: 1.0};
    const baselineJSON = JSON.stringify(p);
    const timeline = C.analyze(p, scenario, p.targetId, p.suggestedMover);
    assert(timeline.samples[2].simulated === null, 'No simulation before branch');
    assert(close(timeline.samples[3].baseline.totals[p.targetId],timeline.samples[3].simulated.totals[p.targetId]),'Branch continuity');
    const current = C.simulateFrame(p, 8, scenario).frame.players.find(r=>r.id===scenario.moverId);
    const origin = p.frames[3].players.find(r=>r.id===scenario.moverId);
    assert(close(current.x, origin.x), 'Lateral route does not change x');
    assert(close(current.y, Math.min(C.FIELD_WIDTH,origin.y+3.5)), 'Lateral route distance');
    assert(timeline.end === 13, 'Horizon');
    let threw = false;try { C.simulateFrame(p,14,scenario); } catch (_) { threw=true; }
    assert(threw,'No counterfactual after horizon');
    assert(JSON.stringify(p)===baselineJSON,'Do not mutate observed data');
    const zero = C.simulateFrame(p,8,{...scenario,speed:0}).frame.players.find(r=>r.id===scenario.moverId);
    assert(close(zero.x,origin.x)&&close(zero.y,origin.y),'Stationary scenario');
    const forward = C.simulateFrame(p,8,{...scenario,angle:0,speed:4}).frame.players.find(r=>r.id===scenario.moverId);
    assert(close(forward.x,origin.x+(p.playDirection==='right'?2:-2)),'Forward respects offense direction');
    const nonRoute = Object.values(p.players).find(r=>r.offense&&!r.route).id;
    const extra = C.analyze(p,{...scenario,moverId:nonRoute},p.targetId,nonRoute);
    assert(extra.ids.includes(nonRoute),'Allow every offensive player');
    assert(close(extra.samples[3].baseline.totals[p.targetId],extra.samples[3].simulated.totals[p.targetId]),'Same extended candidate set');
    for(const j of Object.values(extra.samples[8].simulated.matrix))assert(close(Object.values(j).reduce((a,b)=>a+b,0),1),'Extended normalization');
  }
  const p = JSON.parse(JSON.stringify(f.plays[0].play));
  const id = p.suggestedMover;
  const start=p.frames[3].players.find(r=>r.id===id);start.y=C.FIELD_WIDTH-.1;
  const stopped=C.simulateFrame(p,8,{moverId:id,anchor:3,angle:45,speed:12,horizon:1});
  const q=stopped.frame.players.find(r=>r.id===id);
  assert(stopped.boundary,'Boundary reported');
  assert(close(q.y,C.FIELD_WIDTH),'Stop on sideline');
  assert(Math.abs(q.x-start.x)<.2,'Stop completely, do not slide along sideline');
  globalThis.coreTestReport={status:'passed',assertions,plays:f.plays.length};
})();
