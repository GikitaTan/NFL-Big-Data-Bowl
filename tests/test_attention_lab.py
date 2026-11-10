import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from attention_lab.server import Repository
from project_paths import ROOT, data_directory


class AttentionLabDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (data_directory()/'games.csv').is_file():
            raise unittest.SkipTest('Integration tests require the separately downloaded NFL dataset')
        cls.repository = Repository()

    def test_catalog_has_entire_valid_cohort(self):
        catalog=self.repository.catalog()
        self.assertEqual(catalog['playCount'],4465)
        self.assertEqual(len(catalog['games']),122)
        self.assertEqual(sum(g['playCount'] for g in catalog['games']),4465)

    def test_selected_play_identity_and_frames(self):
        play=self.repository.get_play('2021101700','1621')
        self.assertEqual(play['players'][play['targetId']]['name'],'Laviska Shenault')
        self.assertEqual(play['suggestedMover'],'52733')
        self.assertEqual([f['frameId'] for f in play['frames']],list(range(7,37)))
        self.assertTrue(all(len(f['players'])==23 for f in play['frames']))
        self.assertEqual(play['frames'][-1]['frameId'],play['releaseFrame']-1)

    def test_matching_teams_for_opposite_offense(self):
        play=self.repository.get_play('2021090900','137')
        self.assertEqual(play['offense'],'DAL')
        self.assertEqual(play['players'][play['targetId']]['name'],'Amari Cooper')
        self.assertEqual(len([p for p in play['players'].values() if p['offense']]),11)
        self.assertEqual(len([p for p in play['players'].values() if p['team']==play['defense']]),11)

    def test_unknown_or_path_like_ids_never_become_file_access(self):
        for game,play in [('999','1'),('../','../../'),('2021090900','97')]:
            with self.assertRaises(KeyError):
                self.repository.get_play(game,play)

    def test_clean_checkout_uses_bundled_cohort_without_outputs(self):
        with tempfile.TemporaryDirectory() as tmp,patch('attention_lab.server.ROOT',Path(tmp)):
            repository=Repository(data_directory(),ROOT/'examples/results/receiver_cohort.csv')
            self.assertEqual(repository.last_decline,{})
            self.assertEqual(repository.catalog()['playCount'],4465)
            self.assertEqual(repository.get_play('2021101700','1621')['suggestedMover'],'52733')


if __name__=='__main__':
    unittest.main()
