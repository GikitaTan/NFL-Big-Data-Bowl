import math
import unittest

from defensive_attention import AttentionConfig, frame_attention, play_attention


def player(pid, x, y, heading=0):
    return {"nflId": str(pid), "x": x, "y": y, "o": heading}


class AttentionTests(unittest.TestCase):
    def test_front_side_back_and_normalization(self):
        rows = frame_attention([player(1, 0, 0)], [player(2, 0, 5), player(3, 5, 0), player(4, 0, -5)])
        self.assertGreater(rows[0]["attention"], rows[1]["attention"])
        self.assertGreater(rows[1]["attention"], rows[2]["attention"])
        self.assertAlmostEqual(sum(r["attention"] for r in rows), 1)
        self.assertAlmostEqual(rows[0]["alignmentCosine"], 1)

    def test_distance_and_each_defender_normalizes_separately(self):
        rows = frame_attention([player(1, 0, 0), player(8, 0, -2)], [player(2, 0, 2), player(3, 0, 8)])
        for pid in ("1", "8"):
            group = [r for r in rows if r["defenderId"] == pid]
            self.assertAlmostEqual(sum(r["attention"] for r in group), 1)
            self.assertGreater(group[0]["attention"], group[1]["attention"])

    def test_rotation_invariance(self):
        first = frame_attention([player(1, 0, 0, 30)], [player(2, 3, 4), player(3, -1, 8)])
        rotated = frame_attention([player(1, 10, 10, 210)], [player(2, 7, 6), player(3, 11, 2)])
        for a, b in zip(first, rotated):
            self.assertAlmostEqual(a["attention"], b["attention"])

    def test_temperature_and_numerical_stability(self):
        d, r = [player(1, 0, 0)], [player(2, 0, 2), player(3, 0, 20)]
        cold = frame_attention(d, r, AttentionConfig(temperature=.01))
        hot = frame_attention(d, r, AttentionConfig(temperature=10))
        self.assertGreater(cold[0]["attention"], hot[0]["attention"])
        extreme = frame_attention(d, r, AttentionConfig(distance_scale=1e-100, temperature=1e-100))
        self.assertTrue(all(math.isfinite(p["attention"]) for p in extreme))

    def test_missing_coordinates_heading_and_empty_candidates(self):
        rows = frame_attention([player(1, 0, 0, "NA")], [player(2, 0, 0), player(3, "NA", 1)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["attention"], 1)
        self.assertEqual(rows[0]["headingMissing"], 1)
        self.assertEqual(rows[0]["alignmentCosine"], 0)
        self.assertEqual(frame_attention([player(1, 0, 0)], []), [])

    def test_config_validation(self):
        for kwargs in ({"temperature": 0}, {"distance_scale": -1}, {"direction_weight": float("nan")}, {"direction_source": "bad"}):
            with self.assertRaises(ValueError):
                AttentionConfig(**kwargs)

    def test_window_roles_ball_and_possession(self):
        rows = []
        for frame, event in ((1, "None"), (2, "ball_snap"), (3, "pass_forward"), (4, "None")):
            for pid, team in ((1, "A"), (2, "B"), (3, "B"), ("", "football")):
                rows.append({**player(pid, 1, 1), "gameId": "10", "playId": "20",
                             "frameId": str(frame), "time": "now", "event": event, "team": team})
        output = list(play_attention(rows, "B", {"2": "Pass Route", "3": "Pass Block"}, {}, AttentionConfig()))
        self.assertEqual(len(output), 2)
        self.assertEqual({p["frameId"] for p in output}, {2, 3})
        self.assertTrue(all(p["defenderId"] == "1" and p["receiverId"] == "2" for p in output))
        position = list(play_attention(rows, "B", {}, {"2": "WR", "3": "TE"}, AttentionConfig(), "position"))
        self.assertEqual(len(position), 4)
        no_snap = [r for r in rows if r["frameId"] != "2"]
        self.assertEqual(list(play_attention(no_snap, "B", {"2": "Pass Route"}, {}, AttentionConfig())), [])


if __name__ == "__main__":
    unittest.main()
