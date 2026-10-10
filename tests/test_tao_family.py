import unittest
from datetime import date
from decimal import Decimal
from app.tao_models import TaoAssessment, FamilyFact
from app.tao_engine import calculate


def assessment(shares=None, relatives=None):
    shares = shares if shares is not None else [('p','a',45),('q','a',6),('p','b',45),('q','b',6)]
    relatives = relatives if relatives is not None else [('p','q','spouse')]
    return TaoAssessment(title='Rokonsági számítás', as_of='2025-12-31',
        companies=[{'id':i,'name':i.upper()} for i in ['a','b','c']],
        persons=[{'id':i,'name':i.upper()} for i in ['p','q','r']],
        voting_facts=[{'id':str(i),'owner':owner,'company':company,'capital':value,
                       'valid_from':'2024-01-01'} for i,(owner,company,value) in enumerate(shares)],
        family_facts=[{'id':'rel'+str(i),'first':first,'second':second,'relationship':relationship,
                       'reviewed_as_of':'2025-12-31','confirmed':True,
                       'evidence':{'source':'Ellenőrzött rokonsági nyilatkozat'}}
                      for i,(first,second,relationship) in enumerate(relatives)])


def row(data):
    return next(r for r in calculate(data)['rows'] if (r['first'],r['second'])==('a','b'))


def family_values(result):
    return [v for v in result['influence_calculations'] if 'members' in v]


class FamilyTests(unittest.TestCase):
    def test_six_percent_can_create_common_family_majority(self):
        result=row(assessment())
        self.assertTrue(any('hozzátartozók' in signal for signal in result['signals']))
        self.assertEqual([v['value'] for v in family_values(result)],['51%','51%'])
        self.assertEqual(result['result'],'undetermined')
        self.assertEqual(result['family_facts'][0]['evidence']['source'],'Ellenőrzött rokonsági nyilatkozat')

    def test_half_is_not_majority(self):
        data=assessment();data.voting_facts[0].capital=Decimal(44);data.voting_facts[2].capital=Decimal(44)
        self.assertFalse(row(data)['signals'])
        self.assertTrue(all(not v['majority'] for v in family_values(row(data))))

    def test_unconfirmed_missing_source_and_unknown_date(self):
        data=assessment();data.family_facts[0].confirmed=False
        self.assertFalse(row(data)['signals']);self.assertTrue(row(data)['missing'])
        data.family_facts[0].confirmed=True;data.family_facts[0].reviewed_as_of=None
        self.assertFalse(row(data)['signals']);self.assertTrue(row(data)['missing'])
        raw=assessment().model_dump(mode='json');raw['family_facts'][0]['evidence']['source']=' '
        with self.assertRaises(ValueError):TaoAssessment.model_validate(raw)

    def test_partner_and_other_relative_are_not_automatically_close(self):
        for relationship in ['partner','other']:
            data=assessment(relatives=[('p','q',relationship)])
            self.assertFalse(row(data)['signals']);self.assertFalse(family_values(row(data)))

    def test_relationship_is_not_transitive(self):
        shares=[(p,c,20) for p in ['p','q','r'] for c in ['a','b']]
        result=row(assessment(shares,[('p','q','spouse'),('q','r','sibling')]))
        self.assertFalse(result['signals'])
        self.assertTrue(all(len(v['members'])==2 for v in family_values(result)))
        result=row(assessment(shares,[('p','q','sibling'),('q','r','sibling'),('p','r','sibling')]))
        self.assertTrue(result['signals'])
        self.assertEqual([v['value'] for v in family_values(result)],['60%','60%'])

    def test_combined_control_is_calculated_before_indirect_multiplication(self):
        data=assessment([('p','c',45),('q','c',6),('c','a',60),('c','b',60)])
        result=row(data)
        self.assertEqual([v['value'] for v in family_values(result)],['60%','60%'])
        self.assertTrue(any('hozzátartozók' in s for s in result['signals']))

    def test_shared_intermediary_not_double_counted(self):
        result=row(assessment([('p','c',60),('q','c',30),('c','a',60),('c','b',60)]))
        self.assertEqual([v['value'] for v in family_values(result)],['60%','60%'])

    def test_end_exclusive_future_and_reviewed_day(self):
        data=assessment();data.family_facts[0].valid_to=date(2025,12,31)
        self.assertFalse(row(data)['signals']);self.assertFalse(row(data)['missing'])
        data.family_facts[0].valid_to=None;data.family_facts[0].valid_from=date(2026,1,1)
        self.assertFalse(row(data)['signals']);self.assertFalse(row(data)['missing'])
        data.family_facts[0].valid_from=None;data.as_of=date(2024,12,31)
        self.assertFalse(row(data)['signals']);self.assertTrue(row(data)['missing'])

    def test_unknown_vote_and_expert_override_are_respected(self):
        data=assessment();data.voting_facts[1].capital=None
        self.assertFalse(row(data)['signals']);self.assertTrue(row(data)['missing'])
        data=assessment();data.voting_facts.append(data.voting_facts[0].model_copy(update={
            'id':'expert','vote_mode':'expert','votes':Decimal(40),'reason':'Eltérő szavazat'}))
        self.assertFalse(row(data)['signals'])

    def test_legacy_case_and_invalid_references(self):
        raw=assessment().model_dump(mode='json');del raw['family_facts']
        self.assertFalse(row(TaoAssessment.model_validate(raw))['signals'])
        raw=assessment().model_dump(mode='json');raw['family_facts'][0]['first']='a'
        with self.assertRaises(ValueError):TaoAssessment.model_validate(raw)
        raw=assessment().model_dump(mode='json');raw['family_facts'][0]['second']='p'
        with self.assertRaises(ValueError):TaoAssessment.model_validate(raw)

    def test_conflicting_family_sources_are_not_used(self):
        data=assessment(relatives=[('p','q','spouse'),('p','q','partner')])
        result=row(data)
        self.assertFalse(result['signals']);self.assertFalse(family_values(result))
        self.assertTrue(any('eltérő igazolt rokonsági' in m for m in result['missing']))

    def test_duplicate_sources_do_not_double_count_votes(self):
        result=row(assessment(relatives=[('p','q','spouse'),('q','p','spouse')]))
        self.assertEqual([v['value'] for v in family_values(result)],['51%','51%'])
