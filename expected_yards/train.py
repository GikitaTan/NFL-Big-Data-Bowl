"""Train an honest, release-time expected net-yardage model from the supplied ZIP.

One row per pass attempt. No post-release tracking or outcome columns as inputs.
Run: python train.py --data /path/to/dataset.zip --out results
"""
import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits

CONTEXT_NUM = ['down', 'yardsToGo', 'quarter', 'los', 'score_diff', 'clock_seconds']
CONTEXT_CAT = ['offenseFormation', 'personnelO', 'personnelD']
FORBIDDEN = {'playResult', 'prePenaltyPlayResult', 'passResult', 'playDescription',
             'penaltyYards', 'pff_hit', 'pff_sack', 'pff_hurry', 'gameId', 'playId', 'week'}


def feature_row(play, frame, snap, positions, elapsed):
    """Inputs must contain only snap and pass_forward frames, never later frames."""
    left = frame.playDirection.iloc[0] == 'left'
    sign = -1 if left else 1
    los = 120-float(play.absoluteYardlineNumber) if left else float(play.absoluteYardlineNumber)
    f = frame.copy()
    f['nx'] = 120-f.x if left else f.x
    f['ny'] = 160/3-f.y if left else f.y
    f['vx'] = sign * f.s * np.sin(np.deg2rad(f.dir))
    f['vy'] = sign * f.s * np.cos(np.deg2rad(f.dir))
    f['position'] = f.nflId.map(positions)
    offense = f[f.team.eq(play.possessionTeam)]
    defense = f[f.team.eq(play.defensiveTeam)]
    qb = offense[offense.position.eq('QB')]
    if len(qb) != 1 or len(defense) != 11 or len(offense) != 11:
        return None
    qb = qb.iloc[0]
    # All WR/TE/RB on offense; no future target identity or retrospective route label.
    rec = offense[offense.position.isin(['WR', 'TE', 'RB'])].copy()
    if rec.empty or len(rec)>6:
        return None
    mm, ss = str(play.gameClock).split(':')
    home_offense = play.possessionTeam == play.homeTeamAbbr
    sd = play.preSnapHomeScore-play.preSnapVisitorScore
    result = dict(down=float(play.down), yardsToGo=float(play.yardsToGo),
                  quarter=float(play.quarter), los=los, score_diff=float(sd if home_offense else -sd),
                  clock_seconds=float(mm)*60+float(ss),
                  offenseFormation=str(play.offenseFormation), personnelO=str(play.personnelO),
                  personnelD=str(play.personnelD), release_seconds=elapsed,
                  qb_depth=float(qb.nx-los), qb_y=float(qb.ny), qb_speed=float(qb.s),
                  qb_vx=float(qb.vx), qb_vy=float(qb.vy), skill_count=len(rec))
    qdist = np.hypot(defense.nx-qb.nx, defense.ny-qb.ny)
    result['qb_nearest_defender'] = float(qdist.min())
    result['qb_defenders_within_3'] = int((qdist<3).sum())
    rec['depth'] = rec.nx-los
    rec = rec.sort_values(['depth', 'ny'], ascending=[False, True])
    distances = []
    for i, (_, r) in enumerate(rec.iterrows(), 1):
        d = np.hypot(defense.nx-r.nx, defense.ny-r.ny)
        nearest = defense.loc[d.idxmin()]
        distances.append(float(d.min()))
        prev = snap[snap.nflId.eq(r.nflId)]
        sx = (120-prev.x.iloc[0] if left else prev.x.iloc[0]) if len(prev)==1 else np.nan
        vals = dict(depth=r.depth, y=r.ny, speed=r.s, vx=r.vx, vy=r.vy,
                    acceleration=r.a, separation=d.min(), second_separation=np.sort(d)[1],
                    nearest_def_vx=nearest.vx, nearest_def_vy=nearest.vy,
                    defenders_3=(d<3).sum(), defenders_5=(d<5).sum(),
                    qb_distance=np.hypot(r.nx-qb.nx,r.ny-qb.ny),
                    depth_from_first_down=r.depth-play.yardsToGo,
                    depth_change=r.nx-sx, is_WR=int(r.position=='WR'),
                    is_TE=int(r.position=='TE'), is_RB=int(r.position=='RB'))
        result.update({f'skill_{i}_{k}':float(v) for k,v in vals.items()})
    result.update(separation_max=max(distances), separation_mean=float(np.mean(distances)),
                  skill_width=float(rec.ny.max()-rec.ny.min()),
                  deepest_skill=float(rec.depth.max()))
    return result


def build_features(path):
    audit=Counter(); rows=[]
    with zipfile.ZipFile(path) as z:
        root=next(n[:-len('games.csv')] for n in z.namelist() if n.endswith('/data/games.csv'))
        games=pd.read_csv(z.open(root+'games.csv'))
        players=pd.read_csv(z.open(root+'players.csv'))
        plays=pd.read_csv(z.open(root+'plays.csv')).merge(games, on='gameId', validate='many_to_one')
        assert not plays.duplicated(['gameId','playId']).any()
        positions=players.set_index('nflId').officialPosition.to_dict()
        lookup=plays.set_index(['gameId','playId'])
        files=sorted(n for n in z.namelist() if '/tracking/' in n and n.endswith('.csv'))
        for ix,name in enumerate(files):
            t=pd.read_csv(z.open(name))
            gid=int(t.gameId.iloc[0])
            for pid,p in t.groupby('playId', sort=False):
                audit['tracking_plays']+=1
                play=lookup.loc[(gid,pid)]
                if play.passResult not in ['C','I','IN']:
                    audit['excluded_not_pass_attempt']+=1; continue
                if pd.isna(play.prePenaltyPlayResult):
                    audit['excluded_missing_label']+=1; continue
                if any(pd.notna(play.get(f'foulName{i}')) for i in [1,2,3]):
                    audit['excluded_penalty_play']+=1; continue
                release=p.loc[p.event.eq('pass_forward'),'frameId']
                snaps=p.loc[p.event.eq('ball_snap'),'frameId']
                if release.empty or snaps.empty or release.min()<snaps.min():
                    audit['excluded_missing_event']+=1; continue
                rf,sf=int(release.min()),int(snaps.min())
                frame=p[p.frameId.eq(rf)]
                snap=p[p.frameId.eq(sf)]
                if frame.nflId.dropna().duplicated().any():
                    audit['excluded_duplicate_players']+=1; continue
                feat=feature_row(play,frame,snap,positions,(rf-sf)/10)
                if feat is None:
                    audit['excluded_incomplete_or_unusual_personnel']+=1; continue
                rows.append(dict(gameId=gid,playId=int(pid),week=int(play.week),
                                 target_yards=float(play.prePenaltyPlayResult),**feat))
            if (ix+1)%20==0: print(f'Features: {ix+1}/{len(files)} games',flush=True)
    df=pd.DataFrame(rows)
    assert not df.duplicated(['gameId','playId']).any()
    audit['included']=len(df)
    return df,dict(audit)


def pipeline(columns, config):
    cats=[c for c in CONTEXT_CAT if c in columns]
    nums=[c for c in columns if c not in cats]
    preprocess=ColumnTransformer([
        ('numeric', SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),nums),
        ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats)])
    return make_pipeline(preprocess,HistGradientBoostingRegressor(
        loss='squared_error',early_stopping=False,learning_rate=.05,random_state=42,**config))


def metrics(y,p):
    return dict(MAE=float(mean_absolute_error(y,p)),RMSE=float(mean_squared_error(y,p)**.5),
                R2=float(r2_score(y,p)),bias=float(np.mean(p-y)))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',required=True); parser.add_argument('--out',default='results')
    args=parser.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    df,audit=build_features(args.data)
    df.to_csv(out/'features.csv',index=False)
    columns=[c for c in df if c not in ['gameId','playId','week','target_yards']]
    assert not (set(columns)&FORBIDDEN)
    train=df[df.week<=6]; val=df[df.week.eq(7)]; test=df[df.week.eq(8)]
    for a,b in [(train,val),(train,test),(val,test)]:
        assert set(a.gameId).isdisjoint(set(b.gameId))
    configs=[dict(max_iter=150,max_leaf_nodes=7,min_samples_leaf=40,l2_regularization=10),
             dict(max_iter=250,max_leaf_nodes=15,min_samples_leaf=40,l2_regularization=20),
             dict(max_iter=150,max_leaf_nodes=15,min_samples_leaf=60,l2_regularization=40)]
    report={'audit':audit,'split':{n:{'plays':len(d),'games':d.gameId.nunique()} for n,d in
                                [('train_weeks_1_6',train),('validation_week_7',val),('test_week_8',test)]},
            'validation':{},'test':{},'selection_metric':'validation RMSE','target':'prePenaltyPlayResult',
            'prediction_time':'pass_forward frame; no later tracking', 'feature_count':len(columns)}
    final_train=df[df.week<=7]
    pred=test[['gameId','playId','week','target_yards']].copy()
    pred['mean_baseline']=float(final_train.target_yards.mean())
    report['test']['mean_baseline']=metrics(test.target_yards,pred.mean_baseline)
    with threadpool_limits(limits=2):
        for name,cols in [('context_baseline',CONTEXT_NUM+CONTEXT_CAT),('tracking_model',columns)]:
            scores=[]
            for cfg in configs:
                m=pipeline(cols,cfg).fit(train,train.target_yards)
                s=metrics(val.target_yards,m.predict(val)); scores.append((s['RMSE'],cfg,s))
                print(name,cfg,s,flush=True)
            _,cfg,_=min(scores,key=lambda x:x[0])
            report['validation'][name]=[dict(config=c,metrics=s) for _,c,s in scores]
            model=pipeline(cols,cfg).fit(final_train,final_train.target_yards)
            pred[name]=model.predict(test)
            report['test'][name]=metrics(test.target_yards,pred[name])
            bundle={'pipeline':model,'features':cols,'selected_config':cfg,'train_weeks':list(range(1,8)),
                    'prediction_time':'pass_forward','target':'prePenaltyPlayResult',
                    'population':'penalty-free C/I/IN pass attempts with full tracking and one QB'}
            joblib.dump(bundle,out/(name+'.joblib'),compress=3)
    # Cluster bootstrap by game: paired uncertainty in test improvement, no tuning on test.
    rng=np.random.default_rng(42); groups=[g for _,g in pred.groupby('gameId')]; deltas=[]
    for _ in range(1000):
        sample=pd.concat([groups[i] for i in rng.integers(0,len(groups),len(groups))])
        deltas.append(mean_squared_error(sample.target_yards,sample.context_baseline)**.5-
                      mean_squared_error(sample.target_yards,sample.tracking_model)**.5)
    report['test_rmse_gain_over_context_95pct_game_bootstrap']=np.quantile(deltas,[.025,.975]).tolist()
    pred.to_csv(out/'test_predictions.csv',index=False)
    (out/'metrics.json').write_text(json.dumps(report,indent=2))
    (out/'feature_columns.json').write_text(json.dumps(columns,indent=2))
    print(json.dumps(report['test'],indent=2),flush=True)
    print('AUDIT',audit,flush=True)


if __name__=='__main__':
    main()
