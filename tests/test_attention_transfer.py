import copy
import unittest

from attention_transfer import ExcludedPlay, analyze_play, event_frame, transfer_score


def fixture():
    rows = []
    for frame, event in ((1, 'ball_snap'), (4, 'None'), (6, 'None'),
                         (7, 'pass_forward'), (10, 'pass_outcome_caught')):
        people = [('1', 'OFF', 0, 1), ('2', 'OFF', 4, 1), ('3', 'OFF', 10, 1)]
        people += [(str(i), 'DEF', i - 10, 4) for i in range(10, 21)]
        people += [('', 'football', 0, 1)]
        for pid, team, x, y in people:
            rows.append(dict(gameId='100', playId='200', nflId=pid, team=team,
                             frameId=str(frame), event=event, x=str(x), y=str(y), o='180'))
    play = dict(gameId='100', playId='200', possessionTeam='OFF', defensiveTeam='DEF', passResult='C')
    roles = {'1': 'Pass Route', '2': 'Pass Route', '3': 'Pass Block'}
    players = {'1': {'displayName': 'Target', 'officialPosition': 'WR'},
               '2': {'displayName': 'Attractor', 'officialPosition': 'TE'}}
    return rows, play, roles, players


class TransferTests(unittest.TestCase):
    def test_formula_and_direction(self):
        start = {'j1': {'A': .2, 'B': .8}, 'j2': {'A': .7, 'B': .3}}
        end = {'j2': {'B': .6, 'A': .4}, 'j1': {'B': .5, 'A': .5}}
        score, evidence = transfer_score(start, end, 'A', 'B')
        self.assertAlmostEqual(score, .09)
        self.assertAlmostEqual(evidence[0]['deltaAttractor'], .3)
        self.assertEqual(evidence[1]['contribution'], 0)
        self.assertAlmostEqual(transfer_score(start, end, 'B', 'A')[0], .09)

    def test_no_cross_defender_multiplication(self):
        start = {'1': {'A': .1, 'B': .3, 'C': .6}, '2': {'A': .1, 'B': .5, 'C': .4}}
        end = {'1': {'A': .3, 'B': .3, 'C': .4}, '2': {'A': .1, 'B': .2, 'C': .7}}
        self.assertEqual(transfer_score(start, end, 'A', 'B')[0], 0)
        with self.assertRaises(ValueError):
            transfer_score(start, {'1': end['1']}, 'A', 'B')

    def test_frames_target_and_zero_tie(self):
        summary, pairs, details = analyze_play(*fixture())
        self.assertEqual((summary['targetId'], summary['t0Frame'], summary['t1Frame']), ('1', 4, 6))
        self.assertEqual(summary['Transfer'], 0)
        self.assertEqual(summary['attractorId'], '')
        self.assertEqual(len(details), 11)
        self.assertEqual(len(pairs), 1)

    def test_missing_event_and_distance_outlier(self):
        rows, play, roles, players = fixture()
        without_catch = [r for r in rows if r['event'] != 'pass_outcome_caught']
        with self.assertRaisesRegex(ExcludedPlay, 'missing_pass_outcome_caught'):
            analyze_play(without_catch, play, roles, players)
        for r in rows:
            if r['event'] == 'pass_outcome_caught' and r['team'] == 'football':
                r['x'] = '100'
        with self.assertRaisesRegex(ExcludedPlay, 'catch_distance_too_large'):
            analyze_play(rows, play, roles, players)

    def test_nearest_all_offense_before_role_filter(self):
        rows, play, roles, players = fixture()
        roles['1'] = 'Pass Block'
        with self.assertRaisesRegex(ExcludedPlay, 'not_route_runner'):
            analyze_play(rows, play, roles, players)

    def test_ambiguous_receiver_and_changed_candidates(self):
        rows, play, roles, players = fixture()
        modified = copy.deepcopy(rows)
        for r in modified:
            if r['event'] == 'pass_outcome_caught' and r['nflId'] == '2':
                r['x'] = '.05'
        with self.assertRaisesRegex(ExcludedPlay, 'ambiguous_nearest_receiver'):
            analyze_play(modified, play, roles, players)
        modified = [r for r in rows if not (r['frameId'] == '6' and r['nflId'] == '2')]
        with self.assertRaisesRegex(ExcludedPlay, 'inconsistent_route_candidates'):
            analyze_play(modified, play, roles, players)

    def test_annotated_event_priority(self):
        rows, *_ = fixture()
        rows.append({'frameId': '5', 'event': 'autoevent_passforward'})
        self.assertEqual(event_frame(rows, 'pass_forward', 'autoevent_passforward'), (7, 'pass_forward'))
        fallback = [r for r in rows if r['event'] != 'pass_forward']
        self.assertEqual(event_frame(fallback, 'pass_forward', 'autoevent_passforward'), (5, 'autoevent_passforward'))


if __name__ == '__main__':
    unittest.main()
