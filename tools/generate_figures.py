"""Regenerate README figures from the small, committed example artifacts.

Optional dependency: python -m pip install -r requirements-figures.txt
Run from any directory: python tools/generate_figures.py
"""

import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from defensive_attention import frame_attention

OUT = ROOT/'docs/images'
INK, TEAL, ORANGE, MUTED = '#20354a', '#188579', '#cc7a44', '#71808c'


def save(fig, name):
    fig.savefig(OUT/name, dpi=170, facecolor='white', bbox_inches='tight')
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.labelcolor':INK,'text.color':INK,'axes.titlecolor':INK,
                         'xtick.color':MUTED,'ytick.color':MUTED,'axes.edgecolor':'#c9d3da'})
    fixture=json.loads((ROOT/'examples/core_fixture.json').read_text())['plays'][0]
    play, expected=fixture['play'],fixture['expected']
    target=play['targetId']
    ids=sorted(expected[0],key=lambda pid:-max(frame[pid] for frame in expected))
    times=[f['t'] for f in play['frames']]
    totals=[sum(f.values()) for f in expected]
    decline=json.loads((ROOT/'examples/results/play_1621_last_decline.json').read_text())['summary']

    fig,(ax,heat)=plt.subplots(2,1,figsize=(12,7.5),gridspec_kw={'height_ratios':[1,1.45]},layout='constrained')
    ax.plot(times,totals,color=TEAL,lw=2.5)
    ax.axvspan(decline['startSeconds'],decline['endSeconds'],color=ORANGE,alpha=.13,label='Last significant decline (smoothed endpoints)')
    for t,label in [(.3,'t0: 0.3 s'),(2.9,'Pre-release: 2.9 s')]:
        i=round(t*10); ax.plot(t,totals[i],'o',color=TEAL)
        ax.annotate(f'{label}\n{totals[i]:.2f}',(t,totals[i]),xytext=(8,10),textcoords='offset points',
                    ha='right' if t>2 else 'left',fontsize=9)
    ax.set(xlim=(0,3.04),ylim=(0,max(totals)*1.2),ylabel='Total attention weight\n(sum over 11 defenders)',
           title='Laviska Shenault | game 2021101700 / play 1621 | observed pre-release attention')
    ax.grid(axis='y',alpha=.16);ax.legend(loc='lower left',frameon=False,fontsize=9)
    image=heat.imshow([[f[pid] for f in expected] for pid in ids],aspect='auto',cmap='viridis',vmin=0,vmax=1,
                      extent=(-.05,2.95,len(ids)-.5,-.5),interpolation='nearest')
    heat.set(yticks=list(range(len(ids))),yticklabels=[play['players'][pid]['name'] for pid in ids],
             xlabel='Time after snap (s)',ylabel='Defender')
    fig.colorbar(image,ax=heat,label='Attention allocated to Shenault (0–1)',shrink=.9,pad=.02)
    save(fig,'play-1621-attention.png')

    # One real frame; the right panel makes every defensive weight readable.
    frame=play['frames'][18]
    ds=[dict(nflId=p['id'],**p) for p in frame['players'] if play['players'][p['id']]['team']==play['defense']]
    rs=[dict(nflId=p['id'],**p) for p in frame['players'] if play['players'][p['id']]['route']]
    weights={r['defenderId']:r['attention'] for r in frame_attention(ds,rs) if r['receiverId']==target}
    receiver=next(p for p in frame['players'] if p['id']==target)
    fig,(ax,bars)=plt.subplots(1,2,figsize=(13,7.5),gridspec_kw={'width_ratios':[1.2,1]},layout='constrained')
    ax.set_facecolor('#f1f6ef');ax.set(xlim=(0,160/3),ylim=(35,75),aspect='equal')
    for x in range(35,76,5):ax.axhline(x,color='#cbd9ca',lw=.7)
    ax.axhline(play['lineOfScrimmage'],color=MUTED,ls='--',lw=1)
    ax.text(52.5,play['lineOfScrimmage']+.4,'Line of scrimmage',ha='right',color=MUTED,fontsize=8)
    for p in ds:
        ax.plot([p['y'],receiver['y']],[p['x'],receiver['x']],color='#6777c1',lw=.5+5*weights[p['id']],alpha=.15+.7*weights[p['id']],zorder=1)
    for p in frame['players']:
        info=play['players'][p['id']]
        if p['id']=='football':ax.scatter(p['y'],p['x'],marker='D',s=16,c=INK,zorder=5);continue
        defense=info['team']==play['defense']
        color=ORANGE if defense else TEAL
        ax.scatter(p['y'],p['x'],marker='s' if defense else 'o',s=155,c='#f8e6d7' if defense else '#e1eee5',edgecolors=color,lw=.8,zorder=3)
        ax.text(p['y'],p['x'],info['jersey'],ha='center',va='center',fontsize=7,color=INK,zorder=4)
        if p['id']==target:ax.scatter(p['y'],p['x'],s=350,facecolors='none',edgecolors='#5866c9',lw=2,zorder=4)
    ax.set(xlabel='Field width (yards)',ylabel='Tracking x (yards; offense moves upward)',title='Observed positions at 1.8 s after snap')
    ax.legend(handles=[Line2D([],[],marker='o',color=TEAL,ls='',label='JAX offense'),Line2D([],[],marker='s',color=ORANGE,ls='',label='MIA defense')],loc='upper left',frameon=False,fontsize=9)
    ranking=sorted(weights,key=weights.get,reverse=True)
    bars.barh(range(11),[weights[i] for i in ranking],color=TEAL,height=.65)
    bars.set(yticks=range(11),yticklabels=[play['players'][i]['name'] for i in ranking],xlim=(0,1.08),
             xlabel='Weight allocated to Shenault',title=f'Defensive weights | total = {sum(weights.values()):.2f}')
    bars.invert_yaxis();bars.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    for i,pid in enumerate(ranking):bars.text(weights[pid]+.015,i,f'{weights[pid]:.1%}',va='center',fontsize=9)
    save(fig,'play-1621-field.png')

    report=json.loads((ROOT/'examples/results/trend_report.json').read_text())
    counts=report['trendCounts'];n=report['coverage']['included']
    labels={'DU':'Down → Up','U':'Up','UD':'Up → Down','D':'Down','UDU':'Up → Down → Up',
            'DUD':'Down → Up → Down','4+ segments':'4+ legs','flat':'No significant change'}
    fig,(ax,conditional)=plt.subplots(1,2,figsize=(13,5.3),gridspec_kw={'width_ratios':[1.5,1]},layout='constrained')
    ax.barh(range(len(counts)),list(counts.values()),color=[ORANGE if k=='UDU' else TEAL for k in counts],height=.65)
    ax.set(yticks=range(len(counts)),yticklabels=[labels[k] for k in counts],xlabel='Completed-pass plays',
           xlim=(0,max(counts.values())*1.27),title=f'Actual-receiver attention trends | n = {n:,}')
    ax.invert_yaxis()
    for i,value in enumerate(counts.values()):ax.text(value+12,i,f'{value:,}  ({value/n:.2%})',va='center',fontsize=9)
    strata=report['durationStrata']
    conditional.bar(range(4),[s['UDUPercent'] for s in strata.values()],color=ORANGE,width=.55)
    conditional.set(xticks=range(4),xticklabels=['<2 s','2–3 s','3–4 s','≥4 s'],ylim=(0,30),
                    xlabel='Observed pre-release window',ylabel='Up → Down → Up share (%)',title='UDU becomes more common in longer plays')
    for i,s in enumerate(strata.values()):conditional.text(i,s['UDUPercent']+.7,f"{s['UDUPercent']:.1f}%\nn={s['n']}",ha='center',fontsize=9)
    save(fig,'receiver-trends.png')
    print(f'Saved three reproducible figures to {OUT}')


if __name__=='__main__':
    main()
