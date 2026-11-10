"""Prepare reproducible, frame-by-frame attention to one completed-pass target."""

import csv
import json
from pathlib import Path

from attention_transfer import analyze_play
from defensive_attention import frame_attention, iter_plays, read_csv, valid_position, number


def build_data(game_id='2021101700', play_id=1621):
    root = Path(__file__).parent
    data = root / 'nfl-big-data-bowl-regional-event-data-main/data'
    play = next(r for r in read_csv(data / 'plays.csv')
                if r['gameId'] == game_id and int(r['playId']) == play_id)
    roles = {r['nflId']: r['pff_role'] for r in read_csv(data / 'pffScoutingData.csv')
             if r['gameId'] == game_id and int(r['playId']) == play_id}
    players = {r['nflId']: r for r in read_csv(data / 'players.csv')}
    _, rows = next(iter_plays(data / 'tracking' / f'tracking_{game_id}.csv', play_id))
    summary, _, _ = analyze_play(rows, play, roles, players)
    candidates = {pid for pid, role in roles.items() if role.lower() == 'pass route'}
    target = summary['targetId']
    output = []
    for frame in range(summary['snapFrame'], summary['releaseFrame']):
        current = [r for r in rows if int(r['frameId']) == frame]
        receivers = [r for r in current if r['team'] == play['possessionTeam'] and r['nflId'] in candidates]
        defenders = [r for r in current if r['team'] == play['defensiveTeam'] and r['nflId']]
        assert len(receivers) == len(candidates) and len(defenders) == 11
        assert all(valid_position(r) for r in receivers + defenders)
        pairs = frame_attention(defenders, receivers)
        selected = {r['defenderId']: r['attention'] for r in pairs if r['receiverId'] == target}
        assert len(selected) == 11
        tracked = []
        for r in current:
            if not valid_position(r):
                continue
            football = r['team'].lower() == 'football'
            info = players.get(r['nflId'], {})
            tracked.append(dict(id='football' if football else r['nflId'],
                                team=r['team'], name='Football' if football else info.get('displayName', ''),
                                jersey='' if football else r['jerseyNumber'],
                                position=info.get('officialPosition', ''),
                                x=float(r['x']), y=float(r['y']), o=number(r.get('o')),
                                route=r['nflId'] in candidates))
        output.append(dict(frame=frame, t=round((frame - summary['snapFrame']) / 10, 2),
                           total=sum(selected.values()), attention=selected, players=tracked))
    order = sorted(output[0]['attention'], key=lambda pid: -max(r['attention'][pid] for r in output))
    result = dict(gameId=game_id, playId=play_id, target=summary['targetName'], targetId=target,
                  offense=play['possessionTeam'], defense=play['defensiveTeam'],
                  description=play['playDescription'], t0=(summary['t0Frame']-summary['snapFrame'])/10,
                  t1=(summary['t1Frame']-summary['snapFrame'])/10,
                  release=(summary['releaseFrame']-summary['snapFrame'])/10,
                  defenders=[dict(id=pid, name=players[pid]['displayName'],
                                  position=players[pid]['officialPosition']) for pid in order],
                  playDirection=rows[0]['playDirection'], lineOfScrimmage=float(play['absoluteYardlineNumber']),
                  yardsToGo=float(play['yardsToGo']), samples=output)
    dest = root / 'outputs/receiver_attention'
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'data.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    with (dest / 'attention.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['gameId', 'playId', 'targetId', 'frameId',
                                                   'secondsAfterSnap', 'defenderId', 'defenderName', 'attention'])
        writer.writeheader()
        for r in output:
            for d in result['defenders']:
                writer.writerow(dict(gameId=game_id, playId=play_id, targetId=target, frameId=r['frame'],
                                     secondsAfterSnap=r['t'], defenderId=d['id'], defenderName=d['name'],
                                     attention=r['attention'][d['id']]))
    print(json.dumps(dict(target=result['target'], samples=len(output),
                          t0Total=output[3]['total'], t1Total=output[-1]['total'],
                          firstTotal=output[0]['total'],
                          leadingDefender=result['defenders'][0]), ensure_ascii=False))
    return result


if __name__ == '__main__':
    build_data()
