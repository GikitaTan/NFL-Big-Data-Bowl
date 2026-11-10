"""Attribute synchronous attention changes for the previously visualized play.

Baseline: snap + 3 frames. End: catch event - 1 frame. A baseline coverer
is a defender whose highest softmax weight is on the actual receiver at t0.
"""

from collections import defaultdict
import json
from pathlib import Path

from attention_transfer import event_frame, write_csv
from defensive_attention import frame_attention, iter_plays, read_csv, valid_position


def main():
    root = Path(__file__).parent
    data = root / 'nfl-big-data-bowl-regional-event-data-main/data'
    game, play_id, target = '2021101700', 1621, '52450'
    rows = next(iter_plays(data / 'tracking' / f'tracking_{game}.csv', play_id))[1]
    roles = {r['nflId']: r['pff_role'] for r in read_csv(data / 'pffScoutingData.csv')
             if r['gameId'] == game and int(r['playId']) == play_id}
    players = {r['nflId']: r for r in read_csv(data / 'players.csv')}
    routes = {pid for pid, role in roles.items() if role.lower() == 'pass route'}
    snap, _ = event_frame(rows, 'ball_snap', 'autoevent_ballsnap')
    caught, _ = event_frame(rows, 'pass_outcome_caught')
    start, end = snap + 3, caught - 1
    matrices = []
    for frame in (start, end):
        current = [r for r in rows if int(r['frameId']) == frame]
        ds = [r for r in current if r['team'] == 'MIA']
        rs = [r for r in current if r['team'] == 'JAX' and r['nflId'] in routes]
        assert len(ds) == 11 and {r['nflId'] for r in rs} == routes
        assert all(valid_position(r) for r in ds + rs)
        matrix = defaultdict(dict)
        for r in frame_attention(ds, rs):
            matrix[r['defenderId']][r['receiverId']] = r['attention']
        matrices.append(matrix)
    m0, m1 = matrices
    assert set(m0) == set(m1)
    pair_rows, defender_rows = [], []
    for defender in m0:
        a, b = m0[defender], m1[defender]
        coverer = a[target] == max(a.values())
        loss = max(0, a[target] - b[target])
        local = []
        for teammate in sorted(routes - {target}, key=int):
            gain = max(0, b[teammate] - a[teammate])
            row = dict(gameId=game, playId=play_id, defenderId=defender,
                       defenderName=players[defender]['displayName'], baselineCoverer=int(coverer),
                       targetId=target, startFrame=start, endFrame=end,
                       targetStart=a[target], targetEnd=b[target], targetLoss=loss,
                       attractorId=teammate, attractorName=players[teammate]['displayName'],
                       attractorStart=a[teammate], attractorEnd=b[teammate], gain=gain,
                       Transfer=loss * gain)
            local.append(row)
        best = max(local, key=lambda r: r['Transfer'])
        defender_rows.append({k: best[k] for k in best if k not in ('attractorStart', 'attractorEnd', 'gain')})
        pair_rows.extend(local)
    totals = []
    for teammate in sorted(routes - {target}, key=int):
        selected = [r for r in pair_rows if r['attractorId'] == teammate]
        totals.append(dict(attractorId=teammate, attractorName=players[teammate]['displayName'],
                           baselineCovererTransfer=sum(r['Transfer'] for r in selected if r['baselineCoverer']),
                           allDefenderTransfer=sum(r['Transfer'] for r in selected)))
    totals.sort(key=lambda r: -r['baselineCovererTransfer'])
    dest = root / 'outputs/receiver_attention_attribution'
    dest.mkdir(parents=True, exist_ok=True)
    write_csv(dest / 'pairs.csv', pair_rows)
    write_csv(dest / 'defenders.csv', defender_rows)
    write_csv(dest / 'attractors.csv', totals)
    report = dict(gameId=game, playId=play_id, receiver=players[target]['displayName'],
                  targetId=target, startFrame=start, endFrame=end, catchFrame=caught,
                  startSeconds=(start-snap)/10, endSeconds=(end-snap)/10,
                  covererRule='target has the highest attention among all route runners at baseline',
                  baselineCoverers=[r for r in defender_rows if r['baselineCoverer']],
                  attractors=totals,
                  interpretation='Synchronous geometric attention changes; not causal attribution')
    (dest / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    # Verify no cross-defender multiplication, and exact attention conservation.
    for j in m0:
        assert abs(sum(m1[j][k]-m0[j][k] for k in routes)) < 1e-12
    assert all(r['Transfer'] >= 0 for r in pair_rows)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
