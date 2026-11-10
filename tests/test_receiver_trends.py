import unittest

from receiver_trend_distribution import classify, identify_target, matches_name


class TrendTests(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(classify([1]*30)[0], 'flat')
        up=[i/10 for i in range(15)]
        down=list(reversed(up))
        self.assertEqual(classify(up)[0], 'U')
        self.assertEqual(classify(down)[0], 'D')
        self.assertEqual(classify(up+down+up)[0], 'UDU')
        self.assertEqual(classify(down+up+down)[0], 'DUD')

    def test_noise_is_ignored(self):
        self.assertEqual(classify([1+.01*(-1)**i for i in range(40)])[0], 'flat')

    def test_suffixes_and_initials(self):
        self.assertTrue(matches_name('L.Shenault', 'Laviska Shenault Jr.'))
        self.assertTrue(matches_name('Dj.Moore', 'D.J. Moore'))
        self.assertTrue(matches_name('A.Green', 'A.J. Green'))
        self.assertTrue(matches_name('A.St.Brown', 'Amon-Ra St. Brown'))
        self.assertFalse(matches_name('D.Moore', 'Elijah Moore'))

    def test_unique_roster_matching(self):
        players={'1':{'displayName':'Laviska Shenault'},'2':{'displayName':'Laquon Treadwell'}}
        self.assertEqual(identify_target('T.Lawrence pass short right to L.Shenault to JAX 30.',set(players),players),('1','L.Shenault'))

    def test_compound_surname_and_replay_correction(self):
        players={'1':{'displayName':'Amon-Ra St. Brown'},'2':{'displayName':'Kendall Hinton'}}
        self.assertEqual(identify_target('J.Goff pass short to A.St. Brown to DET 20.',set(players),players)[0], '1')
        self.assertEqual(identify_target('pass intended for K.Hinton INTERCEPTED. N.Hobbs to LV 10. REVERSED. pass short to K.Hinton to LV 12.',set(players),players)[0], '2')

    def test_historical_name_is_scoped_to_player_id(self):
        players={'48415':{'displayName':'Deonte Harty'}}
        self.assertEqual(identify_target('J.Winston pass short to D.Harris to NO 30.',set(players),players)[0],'48415')


if __name__ == '__main__':
    unittest.main()
