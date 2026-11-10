"""Actual completed-pass receiver attention trends, snap through pre-release.

Target identity is read from playDescription and uniquely matched to the
offensive on-play roster. Attention is the sum over all eleven defenders.
Core calculation requires only the Python standard library.
"""

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re

from attention_transfer import ExcludedPlay, event_frame, write_csv
from defensive_attention import frame_attention, iter_plays, read_csv, valid_position
from project_paths import data_directory, result_file


# Official Saints confirmation of the historical surname used in 2021 play-by-play:
# https://www.neworleanssaints.com/news/deonte-harris-harty-wide-receiver-new-orleans-saints-season-recap-2021
NAME_ALIASES = {'48415': ['Deonte Harris']}


def letters(value):
    return ''.join(c for c in value.casefold() if c.isalpha())


def matches_name(abbreviation, full_name):
    bits = abbreviation.rstrip('.,;').split('.', 1)
    if len(bits) != 2:
        return False
    initial, surname = map(letters, bits)
    tokens = full_name.split()
    while tokens and letters(tokens[-1]) in {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}:
        tokens.pop()
    return (len(tokens) >= 2 and letters(''.join(tokens[1:])) == surname
            and letters(tokens[0]).startswith(initial))


def identify_target(description, roster, players):
    description = re.sub(r'\bSt\.\s+Brown\b', 'St.Brown', description)
    matches = list(re.finditer(r'\bpass\b.*?\bto\s+([^\s]+)', description, re.IGNORECASE))
    if not matches:
        raise ExcludedPlay('no_receiver_name_in_description')
    # Replay reversals repeat the corrected play after the original description.
    abbreviation = matches[-1].group(1)
    hits = [pid for pid in roster if any(matches_name(abbreviation, name) for name in
            [players.get(pid, {}).get('displayName', ''), *NAME_ALIASES.get(pid, [])])]
    if len(hits) != 1:
        raise ExcludedPlay('receiver_name_not_unique' if hits else 'receiver_name_unmatched')
    return hits[0], abbreviation


def smooth(values, width=5):
    half = width // 2
    return [sum(values[max(0, i-half):min(len(values), i+half+1)]) /
            len(values[max(0, i-half):min(len(values), i+half+1)]) for i in range(len(values))]


def classify(values, absolute=.1, relative=.1, width=5, min_frames=3):
    """Directional-change / zigzag classification with amplitude and duration gates.

    Reversal must differ from a running extremum by epsilon and occur at
    least min_frames later. Unconfirmed final reversals are ignored.
    """
    ys = smooth(values, width)
    epsilon = max(absolute, relative * (max(ys) - min(ys)))
    low = high = 0
    state = 0
    anchors = []
    for i, value in enumerate(ys):
        if state == 0:
            if value < ys[low]:
                low = i
            if value > ys[high]:
                high = i
            if value - ys[low] >= epsilon and i-low >= min_frames:
                anchors = [low]
                high = i
                state = 1
            elif ys[high] - value >= epsilon and i-high >= min_frames:
                anchors = [high]
                low = i
                state = -1
        elif state == 1:
            if value > ys[high]:
                high = i
            if ys[high] - value >= epsilon and i-high >= min_frames:
                anchors.append(high)
                state, low = -1, i
        else:
            if value < ys[low]:
                low = i
            if value - ys[low] >= epsilon and i-low >= min_frames:
                anchors.append(low)
                state, high = 1, i
    if state:
        anchors.append(high if state == 1 else low)
    signs = ''.join('U' if ys[b] > ys[a] else 'D' for a, b in zip(anchors, anchors[1:]))
    return signs or 'flat', epsilon, anchors


def extract(data_dir, dest, existing=None):
    plays = {(r['gameId'], r['playId']): r for r in read_csv(data_dir/'plays.csv') if r['passResult'] == 'C'}
    players = {r['nflId']: r for r in read_csv(data_dir/'players.csv')}
    roles = defaultdict(dict)
    for r in read_csv(data_dir/'pffScoutingData.csv'):
        key = r['gameId'], r['playId']
        if key in plays:
            roles[key][r['nflId']] = r['pff_role']
    validated = {(r['gameId'], r['playId']): r['targetId']
                 for r in read_csv(result_file('outputs/attention_transfer/plays.csv','catch_validation.csv'))}
    records = list(existing or [])
    retained = {(r['gameId'],r['playId']) for r in records}
    seen, excluded = set(), []
    for path in sorted((data_dir/'tracking').glob('tracking_*.csv')):
        for key, rows in iter_plays(path):
            if key not in plays:
                continue
            seen.add(key)
            if key in retained:
                continue
            play = plays[key]
            try:
                if re.search(r'\bNo Play\b', play['playDescription'], re.IGNORECASE):
                    raise ExcludedPlay('penalty_no_play')
                snap, _ = event_frame(rows, 'ball_snap', 'autoevent_ballsnap')
                release, _ = event_frame(rows, 'pass_forward', 'autoevent_passforward')
                if release-snap < 10:
                    raise ExcludedPlay('fewer_than_10_pre_release_frames')
                roster = {r['nflId'] for r in rows if r['team'] == play['possessionTeam']}
                target, abbreviation = identify_target(play['playDescription'], roster, players)
                if key in validated and validated[key] != target:
                    raise ExcludedPlay('description_catch_target_disagree')
                candidates = {pid for pid, role in roles[key].items() if role.lower() == 'pass route'}
                if target not in candidates:
                    raise ExcludedPlay('target_not_route_runner')
                if len(candidates) < 2:
                    raise ExcludedPlay('fewer_than_two_route_runners')
                frames = defaultdict(list)
                for r in rows:
                    frame = int(r['frameId'])
                    if snap <= frame < release:
                        frames[frame].append(r)
                values, defender_set, missing = [], None, 0
                for frame in range(snap, release):
                    current = frames[frame]
                    ds = [r for r in current if r['team'] == play['defensiveTeam']]
                    rs = [r for r in current if r['team'] == play['possessionTeam'] and r['nflId'] in candidates]
                    if len(ds) != 11 or len(rs) != len(candidates) or {r['nflId'] for r in rs} != candidates:
                        raise ExcludedPlay('incomplete_frame_or_candidate_set')
                    ids = {r['nflId'] for r in ds}
                    if len(ids) != 11 or defender_set is not None and ids != defender_set:
                        raise ExcludedPlay('inconsistent_defenders')
                    defender_set = ids
                    if not all(valid_position(r) for r in ds+rs):
                        raise ExcludedPlay('invalid_coordinates')
                    pairs = frame_attention(ds, rs)
                    selected = [r for r in pairs if r['receiverId'] == target]
                    missing += sum(r['headingMissing'] for r in selected)
                    values.append(sum(r['attention'] for r in selected))
                records.append(dict(gameId=key[0], playId=key[1], receiverId=target,
                                    receiverName=players[target]['displayName'], descriptionName=abbreviation,
                                    catchValidated=key in validated, snapFrame=snap, releaseFrame=release,
                                    candidateCount=len(candidates), missingHeadingCount=missing,
                                    seconds=(len(values)-1)/10, values=values))
            except ExcludedPlay as error:
                excluded.append(dict(gameId=key[0], playId=key[1], reason=str(error)))
    for key in set(plays)-seen:
        excluded.append(dict(gameId=key[0], playId=key[1], reason='missing_tracking_play'))
    with (dest/'series.jsonl').open('w') as handle:
        for record in records:
            handle.write(json.dumps(record)+'\n')
    write_csv(dest/'excluded.csv', excluded, ['gameId','playId','reason'])
    return records, dict(completedPlays=len(plays), included=len(records), excluded=len(excluded),
                         exclusions=dict(Counter(r['reason'] for r in excluded)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=data_directory())
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/receiver_trends'))
    parser.add_argument('--reuse-series', action='store_true')
    parser.add_argument('--resume-extraction', action='store_true', help='Keep valid cached series and retry exclusions')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.reuse_series:
        records = [json.loads(line) for line in (args.output_dir/'series.jsonl').read_text().splitlines()]
        coverage = json.loads((args.output_dir/'report.json').read_text())['coverage']
    else:
        existing = ([json.loads(line) for line in (args.output_dir/'series.jsonl').read_text().splitlines()]
                    if args.resume_extraction else None)
        records, coverage = extract(args.data_dir, args.output_dir, existing)
    classified = []
    for r in records:
        trend, epsilon, anchors = classify(r['values'])
        classified.append({**{k:v for k,v in r.items() if k != 'values'}, 'trend':trend,
                           'threshold':epsilon, 'turningFrames':','.join(str(r['snapFrame']+i) for i in anchors),
                           'startAttention':r['values'][0], 'endAttention':r['values'][-1]})
    write_csv(args.output_dir/'classified.csv',classified)
    counts = Counter(r['trend'] if len(r['trend'])<=3 or r['trend']=='flat' else '4+ segments' for r in classified)
    counts = dict(counts.most_common())
    exact_counts = dict(Counter(r['trend'] for r in classified).most_common())
    checks = []
    for width in (3,5,7):
        for absolute,relative in ((.05,.05),(.1,.1),(.2,.2)):
            c=Counter()
            exact=Counter()
            for r in records:
                trend,_,_=classify(r['values'],absolute,relative,width)
                exact[trend] += 1
                c[trend if len(trend)<=3 or trend=='flat' else '4+ segments']+=1
            ranked=c.most_common()
            checks.append(dict(smoothingFrames=width,absoluteThreshold=absolute,relativeThreshold=relative,
                               mostCommon=exact.most_common(1)[0][0],mostCommonCount=exact.most_common(1)[0][1],
                               UDU=c['UDU'],UDUPercent=100*c['UDU']/len(records),
                               UDURank=1+sum(n>exact['UDU'] for n in exact.values()),counts=dict(ranked)))
    actual = Counter(r['trend'] if len(r['trend'])<=3 or r['trend']=='flat' else '4+ segments'
                     for r in classified if r['catchValidated'])
    strata = {}
    for name,lo,hi in [('0.9–2s',0,2),('2–3s',2,3),('3–4s',3,4),('4s+',4,math.inf)]:
        selected=[r for r in classified if lo<=r['seconds']<hi]
        c=Counter(r['trend'] for r in selected)
        strata[name]=dict(n=len(selected),UDU=c['UDU'],UDUPercent=100*c['UDU']/len(selected) if selected else None,
                          mostCommon=c.most_common(1))
    report = dict(coverage=coverage,window='snap through frame before pass_forward; not through catch',
                  measure='sum of all 11 defenders softmax attention on the actual receiver',
                  targetMethod='unique playDescription abbreviation matched to on-play offensive roster',
                  historicalNameAliases=NAME_ALIASES,
                  primary=dict(smoothingFrames=5,absoluteThreshold=.1,relativeThreshold=.1,minLegFrames=3),
                  trendCounts=counts,exactTrendCounts=exact_counts,UDUCount=counts.get('UDU',0),UDUPercent=100*counts.get('UDU',0)/len(records),
                  UDURank=1+sum(n>counts.get('UDU',0) for n in exact_counts.values()),
                  catchValidatedCounts=dict(actual.most_common()),durationStrata=strata,sensitivity=checks)
    (args.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
