"""Local, read-only NFL Attention Lab. Run: python3 attention_lab/server.py --open-browser."""

import argparse
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from urllib.parse import parse_qs, urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from defensive_attention import iter_plays, number, read_csv, valid_position


class Repository:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or ROOT/'nfl-big-data-bowl-regional-event-data-main/data')
        self.games = {r['gameId']: r for r in read_csv(self.data_dir/'games.csv')}
        self.plays = {(r['gameId'],r['playId']):r for r in read_csv(self.data_dir/'plays.csv')}
        self.players = {r['nflId']:r for r in read_csv(self.data_dir/'players.csv')}
        self.cohort = {(r['gameId'],r['playId']):r for r in read_csv(ROOT/'outputs/receiver_trends/classified.csv')}
        self.last_decline = {(r['gameId'],r['playId']):r for r in read_csv(ROOT/'outputs/last_decline/plays.csv')}
        self.roles = {}
        for r in read_csv(self.data_dir/'pffScoutingData.csv'):
            key=r['gameId'],r['playId']
            if key in self.cohort:
                self.roles.setdefault(key,{})[r['nflId']]=r['pff_role']

    def catalog(self):
        counts={}
        for game,_ in self.cohort:
            counts[game]=counts.get(game,0)+1
        return {'games':[dict(self.games[g],playCount=counts[g]) for g in sorted(counts)],
                'playCount':len(self.cohort), 'defaultGame':'2021101700', 'defaultPlay':'1621'}

    def play_list(self, game_id):
        result=[]
        for (game,play_id),target in self.cohort.items():
            if game != game_id:
                continue
            play=self.plays[(game,play_id)]
            result.append(dict(playId=play_id,receiver=target['receiverName'],
                               quarter=play['quarter'],clock=play['gameClock'],
                               down=play['down'],yardsToGo=play['yardsToGo'],
                               offense=play['possessionTeam'],description=play['playDescription']))
        return sorted(result,key=lambda r:int(r['playId']))

    @lru_cache(maxsize=24)
    def get_play(self, game_id, play_id):
        key=game_id,play_id
        if key not in self.cohort:
            raise KeyError('This play is not in the 4,465 eligible completed-pass samples')
        cohort=self.cohort[key]
        play=self.plays[key]
        _,rows=next(iter_plays(self.data_dir/'tracking'/f'tracking_{game_id}.csv',int(play_id)))
        start,end=int(cohort['snapFrame']),int(cohort['releaseFrame'])
        frames={}
        metadata={}
        for r in rows:
            frame=int(r['frameId'])
            if not start <= frame < end:
                continue
            if not valid_position(r):
                raise ValueError('Invalid player coordinates')
            ball=r['team'].lower()=='football'
            pid='football' if ball else r['nflId']
            player=self.players.get(pid,{})
            metadata[pid]=dict(id=pid,name='Football' if ball else player.get('displayName',pid),
                               jersey='' if ball else r['jerseyNumber'],team=r['team'],
                               position=player.get('officialPosition',''),
                               offense=r['team']==play['possessionTeam'],
                               route=self.roles[key].get(pid,'').lower()=='pass route')
            frames.setdefault(frame,[]).append(dict(id=pid,x=float(r['x']),y=float(r['y']),
                                                     o=number(r.get('o')),dir=number(r.get('dir')),
                                                     s=number(r.get('s')) or 0))
        assert all(f in frames for f in range(start,end))
        decline=self.last_decline.get(key,{})
        suggested=decline.get('topAttractorIds','').split(';')[0]
        if not suggested or suggested not in metadata:
            suggested=next(p for p,m in metadata.items() if m['route'] and p!=cohort['receiverId'])
        return dict(gameId=game_id,playId=play_id,description=play['playDescription'],
                    game=self.games[game_id],offense=play['possessionTeam'],defense=play['defensiveTeam'],
                    targetId=cohort['receiverId'],suggestedMover=suggested,
                    snapFrame=start,releaseFrame=end,playDirection=rows[0]['playDirection'],
                    lineOfScrimmage=float(play['absoluteYardlineNumber']),
                    yardsToGo=float(play['yardsToGo']),players=metadata,
                    frames=[dict(frameId=f,t=round((f-start)/10,1),players=frames[f]) for f in range(start,end)],
                    lastDecline=decline,config=dict(distanceScale=5,directionWeight=2,temperature=1))


def make_handler(repository):
    static=Path(__file__).parent/'static'
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,body,mime='application/json; charset=utf-8'):
            if not isinstance(body,bytes):
                body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parts=urlsplit(self.path)
            query=parse_qs(parts.query)
            # A local read-only service; do not serve API data to other origins.
            host=self.headers.get('Host','').split(':')[0]
            if host not in ('127.0.0.1','localhost'):
                return self.send(403,{'error':'Only localhost access is allowed'})
            try:
                if parts.path=='/api/catalog':
                    return self.send(200,repository.catalog())
                if parts.path=='/api/plays':
                    game=query.get('gameId',[''])[0]
                    if not game.isdigit():return self.send(400,{'error':'A valid gameId is required'})
                    return self.send(200,repository.play_list(game))
                if parts.path=='/api/play':
                    game=query.get('gameId',[''])[0]
                    play=query.get('playId',[''])[0]
                    if not game.isdigit() or not play.isdigit():
                        return self.send(400,{'error':'Numeric gameId and playId values are required'})
                    return self.send(200,repository.get_play(game,play))
                assets={'/':('index.html','text/html; charset=utf-8'),
                        '/app.js':('app.js','text/javascript; charset=utf-8'),
                        '/core.js':('core.js','text/javascript; charset=utf-8'),
                        '/style.css':('style.css','text/css; charset=utf-8')}
                if parts.path in assets:
                    filename,mime=assets[parts.path]
                    return self.send(200,(static/filename).read_bytes(),mime)
                return self.send(404,{'error':'Resource not found'})
            except (KeyError,StopIteration):
                return self.send(404,{'error':'Play not found'})
            except (ValueError,AssertionError):
                return self.send(422,{'error':'This play has incomplete data and cannot be compared reliably'})

        def log_message(self,fmt,*args):
            sys.stderr.write('%s %s\n'%(self.log_date_time_string(),fmt%args))
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open-browser',action='store_true')
    args=parser.parse_args()
    repository=Repository()
    try:
        server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(repository))
    except OSError as error:
        raise SystemExit(f'Port {args.port} is unavailable: {error}. Use --port 8766 to select another port.')
    url=f'http://127.0.0.1:{server.server_port}'
    print(f'Attention Lab ready: {url}',flush=True)
    print(f'{len(repository.cohort)} plays · local data · Ctrl+C to stop',flush=True)
    if args.open_browser:
        threading.Timer(.5,lambda:webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=='__main__':
    main()
