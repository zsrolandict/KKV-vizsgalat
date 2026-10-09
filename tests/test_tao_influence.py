import unittest
from decimal import Decimal
from app.tao_models import TaoAssessment
from app.tao_engine import calculate


class IndirectInfluenceTests(unittest.TestCase):
    def assessment(self, edges, decisions=None):
        actors = sorted({node for edge in edges for node in edge[:2]})
        return TaoAssessment(title='Ptk. számítás', as_of='2025-12-31',
            companies=[{'id': node, 'name': node.upper()} for node in actors],
            voting_facts=[{'id': str(i), 'owner': owner, 'company': target,
                          'valid_from': '2024-01-01',
                          **({'vote_mode': 'explicit', 'vote_bound': 'over_half'} if value == '>50'
                             else {'capital': value})} for i, (owner, target, value) in enumerate(edges)],
            decisions=decisions or [])

    def row(self, data, first='a', second='c'):
        return next(row for row in calculate(data)['rows'] if {row['first'],row['second']} == {first,second})

    def value(self, row, owner='a', target='c'):
        return next(v['value'] for v in row['influence_calculations'] if v['owner'] == owner and v['company'] == target)

    def test_majority_intermediary_is_counted_fully(self):
        row=self.row(self.assessment([('a','b',60),('b','c',60)]))
        self.assertEqual(self.value(row),'60%');self.assertTrue(row['signals'])
        self.assertEqual(row['result'],'undetermined')
        self.assertEqual({f['id'] for f in row['facts']},{'0','1'})

    def test_exactly_half_is_multiplied_and_not_majority(self):
        row=self.row(self.assessment([('a','b',50),('b','c',100)]))
        self.assertEqual(self.value(row),'50%');self.assertFalse(row['signals'])

    def test_multiple_paths_and_direct_votes_are_added(self):
        row=self.row(self.assessment([('a','b',40),('b','c',40),('a','d',40),('d','c',40),('a','c',20)]))
        self.assertEqual(self.value(row),'52%');self.assertTrue(row['signals'])

    def test_combined_control_of_intermediary_is_used_once(self):
        row=self.row(self.assessment([('a','b',60),('a','d',30),('b','d',30),('d','c',70)]))
        self.assertEqual(self.value(row),'70%')

    def test_qualitative_majority_is_not_invented(self):
        row=self.row(self.assessment([('a','b','>50'),('b','c',60)]))
        self.assertEqual(self.value(row),'60%')
        row=self.row(self.assessment([('a','b',60),('b','c','>50')]))
        self.assertEqual(self.value(row),'>50%');self.assertTrue(row['signals'])

    def test_cycle_and_invalid_votes_remain_unresolved(self):
        row=self.row(self.assessment([('a','b',60),('b','c',60),('c','b',20)]))
        self.assertTrue(row['missing']);self.assertFalse(row['signals'])
        row=self.row(self.assessment([('a','c',60),('b','c',60)]))
        self.assertTrue(any('100%' in m for m in row['missing']));self.assertFalse(row['signals'])

    def test_indirect_common_owner_is_a_signal(self):
        data=self.assessment([('p','a',60),('a','b',60),('p','d',60),('d','c',60)])
        row=self.row(data,'b','c')
        self.assertTrue(any('Közös' in signal and 'P' in signal for signal in row['signals']))

    def test_override_and_date_apply_through_chain(self):
        data=self.assessment([('a','b',60),('b','c',60)])
        override=data.voting_facts[0].model_copy(update={'id':'override','vote_mode':'expert','capital':None,'votes':Decimal(40),'reason':'Eltérő szavazat'})
        data.voting_facts.append(override)
        self.assertEqual(self.value(self.row(data)),'24%')
        data.voting_facts[1].valid_to=data.as_of
        self.assertFalse(self.row(data)['signals'])

    def test_six_percent_indirect_votes_change_the_threshold(self):
        row=self.row(self.assessment([('a','b',60),('b','c',6),('a','c',45)]))
        self.assertEqual(self.value(row),'51%');self.assertTrue(row['signals'])

    def test_unknown_and_conflicting_intermediate_are_not_zero(self):
        data=self.assessment([('a','b',60),('b','c',None)])
        self.assertTrue(self.row(data)['missing']);self.assertFalse(self.row(data)['signals'])
        data=self.assessment([('a','b',60),('b','c',60)])
        data.voting_facts.append(data.voting_facts[0].model_copy(update={'id':'conflict','capital':Decimal(40)}))
        self.assertTrue(self.row(data)['missing']);self.assertFalse(self.row(data)['signals'])

    def test_confirmed_expert_decision_takes_priority(self):
        data=self.assessment([('a','b',60),('b','c',60)], decisions=[{
            'first':'a','second':'c','as_of':'2025-12-31','result':'not_related',
            'confirmed':True,'relevant_grounds_reviewed':True,'basis':'Ellenőrzött jogalap',
            'reason':'Indokolt felülbírálat','evidence':{'source':'Szakértői forrás'}}])
        row=self.row(data)
        self.assertEqual(row['result'],'not_related');self.assertTrue(row['signals'])

    def test_qualitative_majority_can_prove_inconsistent_vote_total(self):
        row=self.row(self.assessment([('a','c','>50'),('b','c',50)]))
        self.assertTrue(any('100%' in m for m in row['missing']));self.assertFalse(row['signals'])
