"""Attribute every actual receiver's last significant pre-release decline.

Uses exactly the cached cohort and trend definition from receiver_trends.
Pair-level weights are averaged with the same 5-frame filter as total
attention before taking endpoint deltas; no future post-release data used.
"""

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path

from attention_transfer import transfer_score, write_csv
from defensive_attention import frame_attention, iter_plays, read_csv
from receiver_trend_distribution import classify, smooth
from project_paths import data_directory


def last_decline(values):
    trend, epsilon, anchors = classify(values)
    filtered = smooth(values)
    declines = [(a, b) for a, b in zip(anchors, anchors[1:]) if filtered[b] < filtered[a]]
    return trend, epsilon, declines[-1] if declines else None


def endpoint_matrix(frames, index, snap, n_frames, offense, defense, candidates):
    indices = range(max(0, index-2), min(n_frames, index+3))
    result = defaultdict(lambda: defaultdict(float))
    for i in indices:
        current = frames[snap+i]
        ds = [r for r in current if r['team'] == defense]
        rs = [r for r in current if r['team'] == offense and r['nflId'] in candidates]
        assert len(ds) == 11 and {r['nflId'] for r in rs} == candidates
        for r in frame_attention(ds, rs):
            result[r['defenderId']][r['receiverId']] += r['attention']/len(indices)
    assert len(result) == 11
    for weights in result.values():
        assert set(weights) == candidates and abs(sum(weights.values())-1) < 1e-12
    return {j:dict(weights) for j,weights in result.items()}


def attribution(start, end, target, major_share=.8):
    """Rank teammates; shares are fractions of transfer scores, not causal shares."""
    candidates = set(next(iter(start.values())))
    pairs, evidence = [], []
    for teammate in sorted(candidates-{target}, key=int):
        score, details = transfer_score(start, end, teammate, target)
        pairs.append(dict(attractorId=teammate, Transfer=score))
        evidence.extend(dict(attractorId=teammate, **r) for r in details)
    pairs.sort(key=lambda r:(-r['Transfer'], int(r['attractorId'])))
    total = sum(r['Transfer'] for r in pairs)
    major, cumulative = [], 0.0
    cutoff = None
    for rank, r in enumerate(pairs, 1):
        r['rank'] = rank
        r['scoreShare'] = r['Transfer']/total if total else 0
        if r['Transfer'] > 0 and (cumulative < major_share or
                cutoff is not None and math.isclose(r['Transfer'],cutoff,abs_tol=1e-12)):
            major.append(r['attractorId'])
            cumulative += r['scoreShare']
            cutoff = r['Transfer']
    top = [r['attractorId'] for r in pairs if r['Transfer'] > 0 and
           math.isclose(r['Transfer'],pairs[0]['Transfer'],rel_tol=1e-9,abs_tol=1e-12)]
    return pairs, evidence, top, major, total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=data_directory())
    parser.add_argument('--series',type=Path,default=Path('outputs/receiver_trends/series.jsonl'))
    parser.add_argument('--output-dir',type=Path,default=Path('outputs/last_decline'))
    parser.add_argument('--major-share',type=float,default=.8)
    args=parser.parse_args()
    if not 0 < args.major_share <= 1:
        parser.error('--major-share must be in (0, 1]')
    records=[json.loads(line) for line in args.series.read_text().splitlines()]
    players={r['nflId']:r for r in read_csv(args.data_dir/'players.csv')}
    plays={(r['gameId'],r['playId']):r for r in read_csv(args.data_dir/'plays.csv')}
    roles=defaultdict(dict)
    for r in read_csv(args.data_dir/'pffScoutingData.csv'):
        roles[(r['gameId'],r['playId'])][r['nflId']]=r['pff_role']
    pending, summaries = {}, []
    for record in records:
        trend,epsilon,interval=last_decline(record['values'])
        key=record['gameId'],record['playId']
        summary={k:record[k] for k in ['gameId','playId','receiverId','receiverName']}
        summary.update(trend=trend,status='no_significant_decline',startFrame='',endFrame='',
                       startSeconds='',endSeconds='',targetStart='',targetEnd='',netAttentionDrop='',
                       losingDefenderCount='',grossDefenderLoss='',Transfer='',
                       topAttractorIds='',topAttractorNames='',topTransfer='',topScoreShare='',
                       majorAttractorIds='',majorAttractorNames='',positiveAttractorCount='')
        if interval:
            pending[key]=(record,summary,interval)
        else:
            summaries.append(summary)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    pair_fields=['gameId','playId','receiverId','receiverName','startFrame','endFrame',
                 'attractorId','attractorName','attractorPosition','rank','Transfer','scoreShare',
                 'isTop','isMajor']
    detail_fields=['gameId','playId','receiverId','startFrame','endFrame','attractorId','attractorName',
                   'defenderId','defenderName','attractorStart','attractorEnd','targetStart','targetEnd',
                   'deltaAttractor','deltaTarget','contribution']
    all_pairs, examples, seen = [], {}, set()
    with (args.output_dir/'defenders.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=detail_fields)
        writer.writeheader()
        for path in sorted((args.data_dir/'tracking').glob('tracking_*.csv')):
            if not any(key[0]==path.stem.removeprefix('tracking_') for key in pending):
                continue
            for key,rows in iter_plays(path):
                if key not in pending:
                    continue
                assert key not in seen
                seen.add(key)
                record,summary,(a,b)=pending[key]
                snap=record['snapFrame']
                n_frames=len(record['values'])
                candidates={pid for pid,role in roles[key].items() if role.lower()=='pass route'}
                frames=defaultdict(list)
                wanted={snap+i for idx in (a,b) for i in range(max(0,idx-2),min(n_frames,idx+3))}
                for r in rows:
                    if int(r['frameId']) in wanted:
                        frames[int(r['frameId'])].append(r)
                play=plays[key]
                m0,m1=[endpoint_matrix(frames,idx,snap,n_frames,play['possessionTeam'],
                                      play['defensiveTeam'],candidates) for idx in (a,b)]
                target=record['receiverId']
                target0=sum(m0[j][target] for j in m0)
                target1=sum(m1[j][target] for j in m1)
                ys=smooth(record['values'])
                assert math.isclose(target0,ys[a],abs_tol=1e-12)
                assert math.isclose(target1,ys[b],abs_tol=1e-12)
                assert target0>target1
                pairs,evidence,top,major,total=attribution(m0,m1,target,args.major_share)
                losses=[max(0,m0[j][target]-m1[j][target]) for j in m0]
                summary.update(status='attributed' if total>0 else 'no_positive_transfer',
                               startFrame=snap+a,endFrame=snap+b,startSeconds=a/10,endSeconds=b/10,
                               targetStart=target0,targetEnd=target1,netAttentionDrop=target0-target1,
                               losingDefenderCount=sum(loss>0 for loss in losses),grossDefenderLoss=sum(losses),
                               Transfer=total,topAttractorIds=';'.join(top),
                               topAttractorNames=';'.join(players[i]['displayName'] for i in top),
                               topTransfer=pairs[0]['Transfer'],topScoreShare=pairs[0]['scoreShare'],
                               majorAttractorIds=';'.join(major),
                               majorAttractorNames=';'.join(players[i]['displayName'] for i in major),
                               positiveAttractorCount=sum(r['Transfer']>0 for r in pairs))
                common={k:summary[k] for k in ['gameId','playId','receiverId','receiverName','startFrame','endFrame']}
                for r in pairs:
                    info=players[r['attractorId']]
                    all_pairs.append({**common,**r,'attractorName':info['displayName'],
                                      'attractorPosition':info['officialPosition'],
                                      'isTop':int(r['attractorId'] in top),'isMajor':int(r['attractorId'] in major)})
                for r in evidence:
                    writer.writerow({**{k:v for k,v in common.items() if k!='receiverName'},**r,
                                     'attractorName':players[r['attractorId']]['displayName'],
                                     'defenderName':players[r['defenderId']]['displayName']})
                summaries.append(summary)
                if key==('2021101700','1621'):
                    examples=dict(summary=summary,attractors=all_pairs[-len(pairs):],
                                  defenders=[r for r in evidence if r['contribution']>0])
    if set(pending)!=seen:
        raise ValueError('Missing tracking for cached decline intervals')
    summaries.sort(key=lambda r:(int(r['gameId']),int(r['playId'])))
    write_csv(args.output_dir/'plays.csv',summaries)
    write_csv(args.output_dir/'attractors.csv',all_pairs,pair_fields)
    (args.output_dir/'example.json').write_text(json.dumps(examples,indent=2)+'\n')
    report=dict(cohort=len(records),withDecline=len(pending),withoutDecline=len(records)-len(pending),
                statuses=dict(Counter(r['status'] for r in summaries)),
                mainAttractorCountDistribution=dict(Counter(len(r['majorAttractorIds'].split(';'))
                        for r in summaries if r['status']=='attributed')),
                topAttractorPositions=dict(Counter(r['attractorPosition'] for r in all_pairs if r['isTop'])),
                window='last significant declining leg before pass release, including an earlier decline followed by a rise',
                endpointSmoothingFrames=5,majorCumulativeScoreShare=args.major_share,
                score='sum_j max(0, gain_on_teammate_j) * max(0, loss_on_receiver_j)',
                scoreShareMeaning='fraction of total transfer score, not fraction of attention caused by a teammate',
                topAttractorTies='all tied maxima retained',
                sharedScoreCaution='multiple receivers can gain from other candidates too; no conserved flow or causality')
    (args.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
