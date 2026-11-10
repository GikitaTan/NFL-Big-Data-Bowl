import unittest

from last_decline_attribution import attribution, last_decline


class LastDeclineTests(unittest.TestCase):
    def test_last_decline_precedes_final_rise(self):
        up=[i/10 for i in range(15)]
        down=list(reversed(up))
        trend,_,interval=last_decline(up+down+up)
        self.assertEqual(trend,'UDU')
        self.assertTrue(interval[0]<interval[1]<len(up+down+up)-1)

    def test_no_decline(self):
        self.assertIsNone(last_decline([i/10 for i in range(30)])[2])
        self.assertIsNone(last_decline([1]*30)[2])

    def test_all_tied_top_attractors_are_retained(self):
        a={'1':{'10':.8,'20':.1,'30':.1}}
        b={'1':{'10':.2,'20':.4,'30':.4}}
        pairs,details,top,major,total=attribution(a,b,'10')
        self.assertEqual(top,['20','30'])
        self.assertEqual(major,['20','30'])
        self.assertAlmostEqual(total,.36)
        self.assertAlmostEqual(sum(r['scoreShare'] for r in pairs),1)

    def test_gain_from_different_defender_not_counted(self):
        a={'1':{'10':.8,'20':.1,'30':.1},'2':{'10':.1,'20':.1,'30':.8}}
        b={'1':{'10':.2,'20':.1,'30':.7},'2':{'10':.1,'20':.7,'30':.2}}
        pairs,_,top,_,_=attribution(a,b,'10')
        self.assertEqual(top,['30'])
        self.assertEqual(next(r for r in pairs if r['attractorId']=='20')['Transfer'],0)


if __name__=='__main__':
    unittest.main()
