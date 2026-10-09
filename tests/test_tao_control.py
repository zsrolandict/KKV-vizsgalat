import unittest
from datetime import date
from app.tao_models import TaoAssessment
from app.tao_engine import calculate


def assessment(controls=None, management=None, votes=None):
    return TaoAssessment(title='Irányítási próba',as_of='2025-12-31',
        companies=[{'id':i,'name':i.upper()} for i in ['a','b','c']],
        persons=[{'id':'p','name':'Közös vezető'}],
        control_facts=controls or [], management_facts=management or [], voting_facts=votes or [])


def right(**changes):
    return {'id':'r','owner':'a','company':'b','kind':'appointments', 'membership':'member',
            'condition':'yes','confirmed':True,'reviewed_as_of':'2025-12-31',
            'reason':'A többség megválasztása a társasági szerződés szerint.',
            'evidence':{'source':'Ellenőrzött társasági szerződés'},**changes}


def management(**changes):
    return {'id':'m','first':'a','second':'b','managers':['p'],
            'common_management':'yes','business_control':'yes','financial_control':'yes',
            'confirmed':True,'reviewed_as_of':'2025-12-31',
            'reason':'A két vállalkozás üzleti és pénzügyi döntéseinek irányítása igazolt.',
            'evidence':{'source':'Ellenőrzött irányítási nyilatkozat'},**changes}


def row(data,first='a',second='b'):
    return next(r for r in calculate(data)['rows'] if (r['first'],r['second'])==(first,second))


class ControlTests(unittest.TestCase):
    def test_appointment_right_without_majority_votes(self):
        result=row(assessment([right()]))
        self.assertEqual(result['stage'],'control_signal');self.assertTrue(result['signals'])
        self.assertEqual(result['result'],'undetermined')
        self.assertEqual(result['control_facts'][0]['evidence']['source'],'Ellenőrzött társasági szerződés')
        self.assertFalse(result['influence_calculations'])

    def test_membership_and_legal_condition_required(self):
        for changes in [{'membership':'unknown'},{'membership':'not_member'},{'condition':'unknown'},{'condition':'no'},{'confirmed':False}]:
            result=row(assessment([right(**changes)]));self.assertFalse(result['signals'])
        with self.assertRaises(ValueError):assessment([right(kind='generic_contract')])

    def test_voting_agreement_strict_threshold(self):
        for percent,expected in [(50,False),(51,True),(None,False)]:
            result=row(assessment([right(kind='voting_agreement',aligned_votes=percent)]))
            self.assertEqual(bool(result['signals']),expected)

    def test_right_chain_and_common_mixed_control(self):
        data=assessment([right(),right(id='r2',owner='b',company='c')])
        self.assertTrue(row(data,'a','c')['signals'])
        self.assertIn(['a','b','c'],[v['route'] for v in row(data,'a','c')['control_calculations']])
        data=assessment([right(owner='p',company='a')],votes=[{'id':'v','owner':'p','company':'b','capital':60,'valid_from':'2024-01-01'}])
        result=row(data)
        self.assertTrue(any('Közös' in s for s in result['signals']))
        self.assertTrue(result['facts'])

    def test_dates_and_unverified_rights(self):
        data=assessment([right(valid_to='2025-12-31')]);self.assertFalse(row(data)['signals']);self.assertFalse(row(data)['missing'])
        data=assessment([right(reviewed_as_of=None)]);self.assertFalse(row(data)['signals']);self.assertTrue(row(data)['missing'])

    def test_conflicting_control_sources_are_not_used(self):
        result=row(assessment([right(),right(id='r2',condition='no')]))
        self.assertFalse(result['signals']);self.assertTrue(result['missing'])

    def test_same_manager_is_not_enough(self):
        result=row(assessment(management=[management(business_control='unknown',financial_control='unknown')]))
        self.assertFalse(result['signals']);self.assertTrue(result['missing'])
        self.assertEqual(result['stage'],'management_review')
        self.assertEqual(result['result'],'undetermined')

    def test_both_business_and_financial_control_required(self):
        for changes in [{'business_control':'no'},{'financial_control':'no'},{'common_management':'no'},{'confirmed':False}]:
            self.assertFalse(row(assessment(management=[management(**changes)]))['signals'])
        result=row(assessment(management=[management()]))
        self.assertTrue(result['signals']);self.assertEqual(result['stage'],'control_signal')

    def test_management_not_transitive_and_conflicts_visible(self):
        data=assessment(management=[management(),management(id='m2',first='b',second='c')])
        self.assertFalse(row(data,'a','c')['signals'])
        data=assessment(management=[management(),management(id='m2',business_control='no')])
        self.assertFalse(row(data)['signals']);self.assertTrue(row(data)['missing'])

    def test_proof_and_reference_validation(self):
        for changes in [{'reason':''},{'evidence':{'source':''}},{'owner':'unknown'},{'company':'p'}]:
            with self.assertRaises(ValueError):assessment([right(**changes)])
        for changes in [{'reason':''},{'evidence':{'source':''}},{'managers':['missing']},{'managers':['p','p']},{'second':'a'}]:
            with self.assertRaises(ValueError):assessment(management=[management(**changes)])

    def test_expert_result_has_priority_and_legacy_defaults(self):
        data=assessment(management=[management()]);raw=data.model_dump(mode='json')
        raw['decisions']=[{'first':'a','second':'b','as_of':'2025-12-31','result':'not_related','confirmed':True,
                          'relevant_grounds_reviewed':True,'reason':'Indokolt felülbírálat','basis':'Tao',
                          'evidence':{'source':'Szakértői dokumentum'}}]
        self.assertEqual(row(TaoAssessment.model_validate(raw))['result'],'not_related')
        del raw['control_facts'];del raw['management_facts']
        self.assertFalse(TaoAssessment.model_validate(raw).control_facts)

    def test_documented_over_half_agreement_without_invented_percentage(self):
        data=assessment([right(kind='voting_agreement',aligned_bound='over_half')])
        result=row(data);self.assertTrue(result['signals'])
        self.assertIsNone(result['control_facts'][0]['aligned_votes'])
        with self.assertRaises(ValueError):assessment([right(kind='voting_agreement',aligned_bound='over_half',aligned_votes=51)])

    def test_management_end_and_missing_day(self):
        data=assessment(management=[management(valid_to='2025-12-31')])
        self.assertFalse(row(data)['signals']);self.assertFalse(row(data)['missing'])
        data=assessment(management=[management(reviewed_as_of=None)])
        self.assertFalse(row(data)['signals']);self.assertTrue(row(data)['missing'])

    def test_voting_majority_then_controlling_right(self):
        votes=[{'id':'v','owner':'a','company':'b','capital':60,'valid_from':'2024-01-01'}]
        data=assessment([right(owner='b',company='c')],votes=votes)
        result=row(data,'a','c')
        self.assertTrue(result['signals'])
        self.assertTrue(result['facts'])
        self.assertTrue(result['control_facts'])
