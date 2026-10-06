import unittest
from decimal import Decimal as D, localcontext
from app.demo import demonstration
from app.engine import calculate,category,transition
from app.models import Assessment
from .helpers import sample,extended


class CalculationTests(unittest.TestCase):
    def test_excel_reference_and_full_scenario(self):
        d=demonstration();r=calculate(d)
        self.assertEqual(r['years'][0]['totals'],{'employees':'126.5','turnover':'3273330500','balance':'1888382000'})
        self.assertEqual(r['years'][1]['totals'],{'employees':'140.5','turnover':'3641805000','balance':'2365322000'})
        self.assertEqual(r['category'],'medium');self.assertFalse(r['ready'])
        full=calculate(d,'all')
        self.assertEqual(full['years'][0]['totals']['employees'],'169')
        self.assertEqual(full['years'][1]['totals']['employees'],'183')
        self.assertEqual(full['years'][1]['totals']['turnover'],'5275428000')
        self.assertFalse(full['ready'])

    def test_exact_25_percent_is_partner(self):
        r=calculate(extended(['b'],[('a','b',25)]))
        b=next(row for row in r['years'][-1]['rows'] if row['company']=='b')
        self.assertEqual(b['percent'],'25');self.assertEqual(b['relation'],'partner')
        self.assertEqual(r['years'][-1]['totals']['employees'],'4.5')

    def test_decimal_accuracy_does_not_depend_on_request_worker_context(self):
        data=extended(['b'],[('a','b','33.3333333333')]).model_dump(mode='json')
        for f in data['financials']:
            if f['company']=='b':f['turnover']='10000000000000000000.12345678'
        with localcontext() as ctx:
            ctx.prec=60
            expected=D('10000000000000000000.12345678')*D('33.3333333333')/100+D(1000000)
        with localcontext() as ctx:
            ctx.prec=28
            result=calculate(Assessment.model_validate(data))
        self.assertEqual(D(result['years'][-1]['totals']['turnover']),expected)

    def test_50_percent_without_control_is_partner(self):
        r=calculate(extended(['b'],[('a','b',50)]))
        self.assertEqual(r['years'][-1]['totals']['employees'],'7')

    def test_votes_take_precedence_for_control(self):
        d=extended(['b'],[('a','b',20)]).model_dump(mode='json')
        d['ownerships'][0]['votes']='60'
        r=calculate(Assessment.model_validate(d))
        self.assertEqual(r['years'][-1]['totals']['employees'],'12')

    def test_control_right_below_majority(self):
        d=extended(['b'],[('a','b',10)]).model_dump(mode='json')
        d['ownerships'][0].update(control=True,reason='Kinevezési jog')
        r=calculate(Assessment.model_validate(d))
        self.assertEqual(r['years'][-1]['totals']['employees'],'12')

    def test_linked_chain_is_not_product_of_shares(self):
        r=calculate(extended(['b','c'],[('a','b',60),('b','c',60)]))
        self.assertEqual(r['years'][-1]['totals']['employees'],'22')
        self.assertTrue(r['ready'])
        c=next(row for row in r['years'][-1]['rows'] if row['company']=='c')
        self.assertIn('Okirat',c['reason'])
        self.assertIn('B Kft.',c['reason'])

    def test_partner_linked_block_is_weighted_as_a_whole(self):
        r=calculate(extended(['b','c'],[('a','b',40),('b','c',70)]))
        self.assertEqual(r['years'][-1]['totals']['employees'],'10')
        self.assertEqual([x['percent'] for x in r['years'][-1]['rows']],['100','40','40'])

    def test_partner_of_partner_is_not_recursively_added(self):
        r=calculate(extended(['b','c'],[('a','b',40),('b','c',40)]))
        self.assertEqual(r['years'][-1]['totals']['employees'],'6')

    def test_ninth_company_is_included(self):
        d=demonstration().model_dump(mode='json')
        d['decisions'][-1].update(relation='linked',percent='0')
        r=calculate(Assessment.model_validate(d))
        self.assertEqual(r['years'][-1]['totals']['employees'],'160.5')
        self.assertEqual(r['years'][-1]['totals']['turnover'],'4078014000')

    def test_exact_financial_boundary_and_one_forint_over(self):
        self.assertEqual(category(D('9.9'),D(800000000),D(800000000),D(400)),'micro')
        self.assertEqual(category(D('9.9'),D(800000001),D(800000001),D(400)),'small')
        self.assertEqual(category(D('9'),D('800000500'),D('800000500'),D(400)),'small')

    def test_employment_boundaries_and_financial_or(self):
        for n,expected in [('9.9','micro'),('10','small'),('49.9','small'),('50','medium'),('249.9','medium'),('250','large')]:
            with self.subTest(n=n):self.assertEqual(category(D(n),D(100),D(100),D(400)),expected)
        self.assertEqual(category(D(2),D(900000000),D(1),D(400)),'micro')

    def test_two_years_do_not_change_status_immediately(self):
        h=transition([(2024,'medium'),(2025,'small')],'medium')
        self.assertEqual(h[-1]['effective'],'medium')
        self.assertTrue(h[-1]['pending'])
        self.assertEqual(transition([(2024,'small'),(2025,'small')],'medium')[-1]['effective'],'small')

    def test_different_boundaries_confirm_independently(self):
        self.assertEqual(transition([(2024,'medium'),(2025,'large')],'small')[-1]['effective'],'medium')
        self.assertEqual(transition([(2024,'small'),(2025,'micro')],'medium')[-1]['effective'],'small')

    def test_unknown_previous_state_and_missing_year_block(self):
        self.assertIsNone(transition([(2024,'medium'),(2025,'small')])[-1]['effective'])
        self.assertIsNone(transition([(2023,'small'),(2025,'small')])[-1]['effective'])
        self.assertIsNone(transition([(2024,None),(2025,'small')])[-1]['effective'])

    def test_missing_money_is_not_zero(self):
        d=sample().model_dump(mode='json');d['financials'][-1]['balance']=None
        r=calculate(Assessment.model_validate(d));self.assertFalse(r['ready'])
        self.assertIsNone(r['years'][-1]['category'])

    def test_multiple_partner_routes_require_resolution(self):
        d=extended(['b','c'],[('a','b',40),('a','c',30),('b','c',70)])
        r=calculate(d);self.assertIn('multiple_paths',[b['code'] for b in r['blockers']])
        raw=d.model_dump(mode='json');raw['overrides']=[{'year':y,'company':'b','percent':'45','reason':'Szakértőileg rendezett adatblokk','confirmed':True} for y in [2024,2025]]
        r=calculate(Assessment.model_validate(raw));self.assertTrue(r['ready'])
        self.assertEqual(r['years'][-1]['totals']['employees'],'11')

    def test_consolidated_accounts_are_not_counted_twice(self):
        d=extended(['b'],[('a','b',70)]).model_dump(mode='json')
        for f in d['financials']:
            if f['company']=='a':f.update(consolidated=True,included=['b'],employees='12')
        r=calculate(Assessment.model_validate(d));self.assertEqual(r['years'][-1]['totals']['employees'],'12')

    def test_public_share_profiles_and_review(self):
        raw=sample().model_dump(mode='json');raw['public_review']={'capital':'25','votes':'25','confirmed':True,'reason':'Közjogi részesedés ellenőrizve'}
        hu=calculate(Assessment.model_validate(raw));self.assertEqual(hu['category'],'micro')
        raw['profile']='EU'
        for f in raw['financials']:f['employment_method']='AWU'
        eu=calculate(Assessment.model_validate(raw));self.assertEqual(eu['category'],'public')

    def test_person_group_requires_market_and_acting_together(self):
        d=extended(['b'],[]).model_dump(mode='json')
        d['decisions']=[{'id':'d','first':'a','second':'b','relation':'linked','basis':'persons','reason':'Családtagok','source':'Nyilatkozat','confirmed':True}]
        r=calculate(Assessment.model_validate(d));self.assertIn('persons_market',[b['code'] for b in r['blockers']])

    def test_ownership_dates_change_annual_network(self):
        d=extended(['b'],[('a','b',60)]).model_dump(mode='json');d['ownerships'][0]['start']='2025-01-01'
        d['decisions']=[{'id':'old','first':'a','second':'b','relation':'independent','confirmed':True,'reason':'Korábbi önállóság','source':'Okirat','end':'2024-12-31'}]
        r=calculate(Assessment.model_validate(d))
        self.assertEqual(r['years'][0]['totals']['employees'],'2')
        self.assertEqual(r['years'][1]['totals']['employees'],'12')

    def test_date_rate_mismatch_blocks(self):
        d=sample().model_dump(mode='json');d['rates'][-1]['date']='2025-12-30'
        r=calculate(Assessment.model_validate(d));self.assertIn('rate_date',[b['code'] for b in r['blockers']])

    def test_future_statement_acceptance_blocks(self):
        d=sample().model_dump(mode='json');d['financials'][-1]['accepted']='2027-01-01'
        r=calculate(Assessment.model_validate(d));self.assertIn('financial_acceptance',[b['code'] for b in r['blockers']])


if __name__=='__main__':unittest.main()
