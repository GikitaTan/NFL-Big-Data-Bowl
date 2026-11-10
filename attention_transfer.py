"""Identify completed-pass targets and compute attention diversion toward teammates."""

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path

from defensive_attention import AttentionConfig, frame_attention, iter_plays, number, read_csv, valid_position
from project_paths import data_directory


class ExcludedPlay(ValueError):
    pass


def event_frame(rows, primary, fallback=None):
    for event in (primary, fallback):
        hits = {int(r['frameId']) for r in rows if event and r['event'] == event}
        if hits:
            if len(hits) != 1:
                raise ExcludedPlay('ambiguous_' + primary)
            return hits.pop(), event
    raise ExcludedPlay('missing_' + primary)


def transfer_score(att_start, att_end, attractor, target):
    """Inputs: {defenderId: {receiverId: attention}} on identical identities.

    Implements the supplied formula: target loses attention, attractor gains.
    Returns total and per-defender evidence; it does not establish causality.
    """
    if set(att_start) != set(att_end):
        raise ValueError('Defender sets differ')
    evidence = []
    for defender in sorted(att_start):
        a, b = att_start[defender], att_end[defender]
        if set(a) != set(b):
            raise ValueError('Receiver sets differ')
        da, db = b[attractor] - a[attractor], b[target] - a[target]
        evidence.append(dict(defenderId=defender, attractorStart=a[attractor],
                             attractorEnd=b[attractor], targetStart=a[target], targetEnd=b[target],
                             deltaAttractor=da, deltaTarget=db,
                             contribution=max(da, 0) * max(-db, 0)))
    return sum(r['contribution'] for r in evidence), evidence


def analyze_play(rows, play, roles, players, config=None, max_catch_distance=2.0,
                 ambiguity_margin=0.1, snap_offset_frames=3):
    if play['passResult'] != 'C':
        raise ExcludedPlay('not_completed')
    config = config or AttentionConfig()
    frames = defaultdict(list)
    for row in rows:
        frames[int(row['frameId'])].append(row)
    snap, snap_event = event_frame(rows, 'ball_snap', 'autoevent_ballsnap')
    release, release_event = event_frame(rows, 'pass_forward', 'autoevent_passforward')
    caught, _ = event_frame(rows, 'pass_outcome_caught', 'autoevent_passcaught')
    t0, t1 = snap + snap_offset_frames, release - 1
    if not snap <= t0 < t1 < release <= caught:
        raise ExcludedPlay('invalid_event_order_or_short_pass')
    if t0 not in frames or t1 not in frames:
        raise ExcludedPlay('missing_endpoint_frame')
    offense, defense = play['possessionTeam'], play['defensiveTeam']
    catch_rows = frames[caught]
    balls = [r for r in catch_rows if r['team'].lower() == 'football' and valid_position(r)]
    if len(balls) != 1:
        raise ExcludedPlay('missing_or_ambiguous_catch_ball')
    ball = balls[0]
    # Find nearest among ALL offensive players first, then validate route role.
    offensive = [r for r in catch_rows if r['team'] == offense and r['nflId']]
    if not offensive or any(not valid_position(r) for r in offensive):
        raise ExcludedPlay('invalid_catch_offense_coordinates')
    distances = sorted((math.hypot(float(r['x']) - float(ball['x']),
                                  float(r['y']) - float(ball['y'])), r['nflId']) for r in offensive)
    distance, target = distances[0]
    if distance > max_catch_distance:
        raise ExcludedPlay('catch_distance_too_large')
    gap = distances[1][0] - distance if len(distances) > 1 else math.inf
    if gap <= ambiguity_margin:
        raise ExcludedPlay('ambiguous_nearest_receiver')
    candidates = {pid for pid, role in roles.items() if role.lower() == 'pass route'}
    if target not in candidates:
        raise ExcludedPlay('nearest_offensive_player_not_route_runner')
    if len(candidates) < 2:
        raise ExcludedPlay('no_non_target_route_runner')
    matrices, heading_missing = [], 0
    defender_sets = []
    for endpoint in (t0, t1):
        rs = [r for r in frames[endpoint] if r['team'] == offense and r['nflId'] in candidates]
        ds = [r for r in frames[endpoint] if r['team'] == defense and r['nflId']]
        if len(rs) != len(candidates) or {r['nflId'] for r in rs} != candidates:
            raise ExcludedPlay('inconsistent_route_candidates')
        if len(ds) != 11 or len({r['nflId'] for r in ds}) != 11:
            raise ExcludedPlay('incomplete_defense')
        if any(not valid_position(r) for r in rs + ds):
            raise ExcludedPlay('invalid_endpoint_coordinates')
        heading_missing += sum(number(r.get(config.direction_source)) is None for r in ds)
        defender_sets.append({r['nflId'] for r in ds})
        matrix = defaultdict(dict)
        for pair in frame_attention(ds, rs, config):
            matrix[pair['defenderId']][pair['receiverId']] = pair['attention']
        matrices.append(dict(matrix))
    if defender_sets[0] != defender_sets[1]:
        raise ExcludedPlay('inconsistent_defenders')
    key = dict(gameId=play['gameId'], playId=play['playId'])
    target_info = players.get(target, {})
    common = dict(**key, Target=target_info.get('officialPosition', ''), targetId=target,
                  targetName=target_info.get('displayName', ''), snapFrame=snap,
                  t0Frame=t0, t1Frame=t1, releaseFrame=release, catchFrame=caught,
                  snapEvent=snap_event, releaseEvent=release_event, catchDistanceYards=distance,
                  nearestGapYards=gap, candidateCount=len(candidates), defenderCount=11,
                  missingHeadingEndpoints=heading_missing)
    pairs, details = [], []
    for attractor in sorted(candidates - {target}, key=int):
        score, evidence = transfer_score(*matrices, attractor, target)
        info = players.get(attractor, {})
        identity = dict(attractorId=attractor, attractorName=info.get('displayName', ''),
                        Attractor=info.get('officialPosition', ''))
        pairs.append({**common, **identity, 'Transfer': score})
        details.extend({**key, 'targetId': target, **identity, **r} for r in evidence)
    best = max(pairs, key=lambda r: r['Transfer'])
    total = sum(r['Transfer'] for r in pairs)
    tied = sum(math.isclose(r['Transfer'], best['Transfer'], abs_tol=1e-12) for r in pairs)
    summary = {**common, 'Attractor': best['Attractor'] if best['Transfer'] > 0 else '',
               'attractorId': best['attractorId'] if best['Transfer'] > 0 else '',
               'attractorName': best['attractorName'] if best['Transfer'] > 0 else '',
               'Transfer': total, 'maxAttractorTransfer': best['Transfer'],
               'topScoreTieCount': tied, 'positiveTransfer': int(total > 0)}
    return summary, pairs, details


def write_csv(path, rows, fields=None):
    with path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_dataframe(path='outputs/attention_transfer/plays.csv'):
    """Optional pandas interface; core computation needs no dependencies."""
    import pandas as pd
    return pd.read_csv(path, dtype={'gameId': 'string', 'playId': 'string',
                                   'targetId': 'string', 'attractorId': 'string'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=data_directory())
    parser.add_argument('--game-id')
    parser.add_argument('--play-id', type=int)
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/attention_transfer'))
    parser.add_argument('--max-catch-distance', type=float, default=2.0)
    parser.add_argument('--ambiguity-margin', type=float, default=0.1)
    parser.add_argument('--snap-offset-frames', type=int, default=3)
    parser.add_argument('--distance-scale', type=float, default=5.0)
    parser.add_argument('--direction-weight', type=float, default=2.0)
    parser.add_argument('--temperature', type=float, default=1.0)
    args = parser.parse_args()
    if args.play_id is not None and args.game_id is None:
        parser.error('--play-id requires --game-id')
    if (not math.isfinite(args.max_catch_distance) or args.max_catch_distance <= 0 or
        not math.isfinite(args.ambiguity_margin) or args.ambiguity_margin < 0 or args.snap_offset_frames < 0):
        parser.error('Invalid catch threshold, ambiguity margin, or snap offset')
    config = AttentionConfig(args.distance_scale, args.direction_weight, args.temperature)
    plays = {(r['gameId'], r['playId']): r for r in read_csv(args.data_dir / 'plays.csv')
             if r['passResult'] == 'C' and (args.game_id is None or r['gameId'] == args.game_id)
             and (args.play_id is None or int(r['playId']) == args.play_id)}
    players = {r['nflId']: r for r in read_csv(args.data_dir / 'players.csv')}
    scouting = defaultdict(dict)
    for r in read_csv(args.data_dir / 'pffScoutingData.csv'):
        key = r['gameId'], r['playId']
        if key in plays:
            scouting[key][r['nflId']] = r['pff_role']
    summaries, pairs, details, excluded, seen = [], [], [], [], set()
    paths = sorted((args.data_dir / 'tracking').glob('tracking_*.csv'))
    if args.game_id:
        paths = [p for p in paths if p.stem == 'tracking_' + args.game_id]
    for path in paths:
        for key, rows in iter_plays(path, args.play_id):
            if key not in plays:
                continue
            if key in seen:
                raise ValueError(f'Duplicate play {key}')
            seen.add(key)
            try:
                summary, play_pairs, play_details = analyze_play(
                    rows, plays[key], scouting[key], players, config,
                    args.max_catch_distance, args.ambiguity_margin, args.snap_offset_frames)
            except ExcludedPlay as error:
                excluded.append(dict(gameId=key[0], playId=key[1], reason=str(error)))
                continue
            summaries.append(summary)
            pairs.extend(play_pairs)
            details.extend(play_details)
    for key in sorted(set(plays) - seen):
        excluded.append(dict(gameId=key[0], playId=key[1], reason='missing_tracking_play'))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, result in [('plays', summaries), ('attractors', pairs), ('defenders', details)]:
        write_csv(args.output_dir / (name + '.csv'), result,
                  fields=None if result else ['gameId', 'playId', 'Transfer'])
    write_csv(args.output_dir / 'excluded.csv', excluded, ['gameId', 'playId', 'reason'])
    report = dict(completedPlays=len(plays), acceptedPlays=len(summaries), excludedPlays=len(excluded),
                  exclusionReasons=dict(Counter(r['reason'] for r in excluded)),
                  attentionConfig=config.__dict__, maxCatchDistanceYards=args.max_catch_distance,
                  ambiguityMarginYards=args.ambiguity_margin, snapOffsetFrames=args.snap_offset_frames,
                  assumedTrackingHz=10, scoreDirection='target B loses, attractor A gains',
                  summaryTransfer='sum of all non-target attractor scores',
                  eventPolicy='prefer annotated events; use autoevent only if annotated event absent')
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if summaries:
        example = max(summaries, key=lambda r: r['maxAttractorTransfer'])
        (args.output_dir / 'example.json').write_text(json.dumps(example, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
