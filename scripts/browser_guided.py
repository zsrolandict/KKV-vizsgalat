"""Browser regressions for guided corrections, kinship and persisted graph editing."""
from xml.etree import ElementTree as ET
from playwright.sync_api import expect


def validate_guided_workflow(page, out):
    data={
        'title':'Vezetett ellenőrzés','law_date':'2026-10-10','law_source':'Fiktív ellenőrzött jogi tesztforrás','as_of':'2026-10-10','root':'a','years':[2024,2025],
        'companies':[{'id':'a','name':'Vizsgált Alfa Kft.'},{'id':'b','name':'Béta & Társai <teszt>'}],
        'persons':[{'id':'p1','name':'Első tulajdonos'},{'id':'p2','name':'Második tulajdonos'}],
        'ownerships':[{'id':'o1','owner':'p1','company':'a','capital':'100','votes':'100','source':'Okirat'},
                      {'id':'o2','owner':'p2','company':'b','capital':'100','votes':'100','source':'Okirat'}],
        'financials':[{'company':c,'year':y,'employees':'2' if c=='a' else '10',
            'turnover':'1000000','balance':'2000000','start':f'{y}-01-01','end':f'{y}-12-31',
            'accepted':f'{y+1}-05-31','source':'' if c=='b' and y==2024 else 'Beszámoló'}
            for c in ['a','b'] for y in [2024,2025]],
        'rates':[{'year':y,'date':f'{y}-12-31','quoted':f'{y}-12-31','value':'400','source':'MNB – teszt','confirmed':True}
                 for y in [2024,2025]],
    }
    cid=page.evaluate('async data=>(await api("/cases",{method:"POST",body:{data}})).id',data)
    page.goto(f'http://127.0.0.1:8011/#case/{cid}/review')
    page.locator('.tabs [data-tab=calculation]').click()
    expect(page.locator('#preliminary-calculation')).to_contain_text('Előzetes számítás')
    expect(page.locator('#preliminary-calculation')).to_contain_text('rendezendő kérdés')
    expect(page.locator('.calculation-total')).to_contain_text('2')
    page.locator('#preliminary-calculation [data-action=tab]').click()
    page.locator('#review-scope').select_option('all')
    check=page.locator('[data-check-code=relationship_missing][data-check-target=b]')
    expect(check).to_have_count(1)
    expect(check).to_contain_text('Miért szükséges?')
    expect(check).to_contain_text('Mit kell megadnod?')
    expect(check.locator('[data-action=resolve-check]')).to_have_count(2)
    check.locator('[data-year="2025"]').click()
    expect(page.locator('#modal-form [name=second]')).to_have_value('b')
    page.locator('#modal-form [name=reason]').fill('Ellenőrzés folyamatban')
    page.locator('#modal-form [name=source]').fill('Nyilatkozat')
    page.locator('#modal-form [type=submit]').click()
    expect(page.locator('#modal-form')).to_have_count(0)
    unresolved=page.locator('[data-check-code=relation_unresolved]')
    expect(unresolved).to_have_count(1)
    expect(page.locator('.save-feedback')).to_contain_text('még adat vagy döntés szükséges')
    unresolved.locator('[data-year="2025"]').click()
    page.locator('#modal-form [name=relation]').select_option('partner')
    page.locator('#modal-form [name=percent]').fill('30')
    page.locator('#modal-form [name=reason]').fill('Igazolt partnerkapcsolat')
    page.locator('#modal-form [name=confirmed]').check()
    page.locator('#modal-form [name=all_years]').check()
    page.locator('#modal-form [type=submit]').click()
    expect(page.locator('[data-check-code=relation_unresolved]')).to_have_count(0)
    assert page.evaluate('S.calc.years.at(-1).totals.employees')=='5'
    assert page.evaluate('S.dirty') is False
    # A financial correction goes to the exact company and 2024, despite the selected year being 2025.
    page.locator('[data-check-code=financial_source][data-check-target=b] [data-action=resolve-check]').click()
    expect(page.locator('#modal-title')).to_contain_text('2024')
    page.locator('#modal-form [name=source]').fill('Ellenőrzött 2024-es beszámoló')
    with page.expect_response(lambda r: r.request.method=='PUT' and r.url.endswith('/api/cases/'+cid)) as response:
        page.locator('#modal-form [type=submit]').click()
    assert response.value.status==200
    assert not any(b['code']=='financial_source' for b in response.value.json()['calculation']['blockers'])
    expect(page.locator('[data-check-code=financial_source]')).to_have_count(0)
    assert page.evaluate('S.calc.ready') is True
    page.locator('.tabs [data-tab=graph]').click()
    # A simple click still edits the node; capture is only activated once dragging begins.
    page.locator('[data-graph-node=a]').click()
    expect(page.locator('#modal-form [name=name]')).to_have_value('Vizsgált Alfa Kft.')
    page.locator('#modal-root [data-action=close-modal]').first.click()
    page.locator('[data-action=edit-family]').click()
    page.locator('#modal-form [name=relationship]').fill('testvér')
    page.locator('#modal-form [name=source]').fill('Tulajdonosi nyilatkozat')
    expect(page.locator('#relationship-guidance')).to_contain_text('összeszámítási arány még nem változik')
    page.locator('#modal-form [type=submit]').click()
    expect(page.locator('.family-impact')).to_contain_text('testvér')
    assert page.evaluate('S.calc.years.at(-1).totals.employees')=='5'
    page.locator('.family-impact [data-action=family-decision]').click()
    page.locator('#modal-form [name=basis]').select_option('persons')
    page.locator('#modal-form [name=relation]').select_option('linked')
    expect(page.locator('#modal-form [name=acting_together]')).to_have_attribute('required','')
    page.locator('#modal-form [name=all_years]').check()
    page.locator('#modal-form [name=acting_together]').fill('Igazolt közösen gyakorolt irányítás')
    page.locator('#modal-form [name=market]').fill('Azonos releváns piacon működnek')
    page.locator('#modal-form [type=submit]').click()
    expect(page.locator('#modal-form')).to_have_count(0)
    page.wait_for_function('() => !S.dirty && S.calc.years.at(-1).totals.employees === "12"')
    assert page.evaluate('S.calc.years.at(-1).totals.employees')=='12'
    page.locator('.save-feedback summary').click()
    expect(page.locator('.save-feedback')).to_contain_text('30%')
    expect(page.locator('.save-feedback')).to_contain_text('100%')
    # Drag in several steps; arrows must move, and dragging must not open the edit dialog.
    node=page.locator('[data-graph-node=a]')
    before=node.locator('rect').get_attribute('x')
    arrow=page.locator('.graph-wrap path[marker-end]').first.get_attribute('d')
    box=node.bounding_box()
    page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
    page.mouse.down()
    page.mouse.move(box['x']+box['width']/2+100,box['y']+box['height']/2+80,steps=10)
    page.mouse.up()
    expect(page.locator('#modal-form')).to_have_count(0)
    assert node.locator('rect').get_attribute('x')!=before
    assert page.locator('.graph-wrap path[marker-end]').first.get_attribute('d')!=arrow
    position=page.evaluate('S.data.graph_positions.a')
    page.get_by_role('button',name='Elrendezés mentése',exact=True).click()
    expect(page.get_by_role('button',name='Elrendezés mentése',exact=True)).to_be_disabled()
    page.reload()
    page.locator('[data-graph-node=a]').wait_for()
    assert page.evaluate('S.data.graph_positions.a')==position
    node=page.locator('[data-graph-node=a]');node.focus();node.press('ArrowRight')
    assert page.evaluate('S.data.graph_positions.a.x')==position['x']+10
    page.get_by_role('button',name='Elrendezés mentése',exact=True).click()
    expect(page.get_by_role('button',name='Elrendezés mentése',exact=True)).to_be_disabled()
    page.screenshot(path=str(out/'08-mozgathato-ceghalo.png'),full_page=True)
    for kind in ['svg','png']:
        with page.expect_download() as event:
            page.locator(f'[data-action=download-graph][data-kind={kind}]').click()
        path=out/f'vezetett-ceghalo.{kind}';event.value.save_as(path)
        if kind=='svg':
            root=ET.parse(path).getroot()
            assert root.tag.endswith('svg')
            assert 'Béta & Társai <teszt>' in ''.join(root.itertext())
        else:assert path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    # Retained position also appears when switching years.
    page.locator('[data-action=year][data-year="2025"]').click()
    assert page.evaluate('S.data.graph_positions.a.x')==position['x']+10
    # A failed save keeps local changes and an explicit retry action.
    page.route('**/api/cases/'+cid,lambda route: route.fulfill(status=409,json={'detail':'Verzióütközés – teszt'}) if route.request.method=='PUT' else route.continue_())
    node=page.locator('[data-graph-node=a]');node.focus();node.press('ArrowDown')
    page.get_by_role('button',name='Elrendezés mentése',exact=True).click()
    expect(page.locator('.toast.error')).to_contain_text('Verzióütközés')
    assert page.evaluate('S.dirty') is True
    page.unroute('**/api/cases/'+cid)
    page.get_by_role('button',name='Elrendezés mentése',exact=True).click()
    expect(page.get_by_role('button',name='Elrendezés mentése',exact=True)).to_be_disabled()
    # A rejected dialog save preserves the form; retry cannot duplicate the new actor.
    page.locator('.tabs [data-tab=companies]').click()
    page.get_by_role('button',name='Személy felvétele',exact=True).click()
    page.locator('#modal-form [name=name]').fill('Új személy – mentési teszt')
    original_count=page.evaluate('S.data.persons.length')
    page.route('**/api/cases/'+cid,lambda route: route.fulfill(status=409,json={'detail':'Mentési ütközés'}) if route.request.method=='PUT' else route.continue_())
    page.locator('#modal-form [type=submit]').click()
    expect(page.locator('#modal-error')).to_contain_text('Mentési ütközés')
    expect(page.locator('#modal-form [name=name]')).to_have_value('Új személy – mentési teszt')
    assert page.evaluate('S.data.persons.length')==original_count
    page.unroute('**/api/cases/'+cid)
    page.locator('#modal-form [type=submit]').click()
    expect(page.locator('#modal-form')).to_have_count(0)
    assert page.evaluate('S.data.persons.length')==original_count+1
    # Approval tells the reviewer what is missing and surfaces pending replies first.
    page.evaluate('async () => await api(`/cases/${S.cid}/intake`,{method:"POST",body:{message:"Kiegészítés: a feltöltött tulajdonosi nyilatkozatot ellenőrizni kell."}})')
    page.locator('.tabs [data-tab=review]').click()
    expect(page.locator('#review-intake-panel')).to_contain_text('tulajdonosi nyilatkozatot')
    expect(page.locator('#approval-progress')).to_contain_text('1 új ügyfélválaszt')
    for name in ['financials','relationships','rules']:page.locator(f'#approval-form [name={name}]').check()
    expect(page.locator('#approval-form [type=submit]')).to_be_disabled()
    page.locator('#review-intake-panel [data-action=review-intake]').click()
    expect(page.locator('#approval-form [type=submit]')).to_be_enabled()
    page.locator('.tabs [data-tab=documents]').click()
    expect(page.locator('#report-preview-content')).to_contain_text('Kétéves szabály')
    expect(page.locator('#report-preview-content')).to_contain_text('Vizsgált Alfa Kft.')
    expect(page.locator('#report-preview-content')).to_contain_text('jóváhagyásra váró')
    page.screenshot(path=str(out/'11-indokolt-elonezet.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    for tab in ['graph','review','decisions','companies']:
        page.locator(f'.tabs [data-tab={tab}]').click()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),tab
    page.screenshot(path=str(out/'09-vezetes-mobil.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1050})
    page.locator('.tabs [data-tab=review]').click()
    page.screenshot(path=str(out/'10-rendezett-ellenorzes.png'),full_page=True)
    page.goto('http://127.0.0.1:8011/')
    page.get_by_role('heading',name='Ügyeid, egy helyen.').wait_for()


def validate_year_confirmation(page):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from tests.helpers import extended
    data=extended([f'b{i}' for i in range(9)],[]).model_dump(mode='json')
    data['decisions']=[{'id':f'd{i}','first':'a','second':f'b{i}','relation':'independent',
        'reason':'Ellenőrzött önállóság','source':'Okirat','confirmed':False} for i in range(9)]
    cid=page.evaluate('async data=>(await api("/cases",{method:"POST",body:{data}})).id',data)
    page.goto(f'http://127.0.0.1:8011/#case/{cid}/review')
    expect(page.locator('.tabs [data-tab=review] .tab-badge')).to_have_text('9')
    expect(page.locator('[data-check-code=decision_review]')).to_have_count(9)
    page.locator('[data-check-target=d0] [data-year="2025"]').click()
    page.locator('#modal-form [name=confirmed]').check()
    assert not page.locator('#modal-form [name=all_years]').is_checked()
    page.locator('#modal-form [type=submit]').click()
    expect(page.locator('#modal-form')).to_have_count(0)
    expect(page.locator('.tabs [data-tab=review] .tab-badge')).to_have_text('8')
    expect(page.locator('[data-check-code=decision_review]')).to_have_count(8)
    expect(page.locator('.save-feedback')).to_contain_text('8')
    page.reload();expect(page.locator('[data-check-code=decision_review]')).to_have_count(8)
    page.locator('[data-action=review-year][data-year="2024"]').click()
    expect(page.locator('.tabs [data-tab=review] .tab-badge')).to_have_text('9')
    expect(page.locator('[data-check-code=decision_review]')).to_have_count(9)
    # Complete each pair explicitly for both years; the list must eventually reach zero.
    for i in range(9):
        page.locator(f'[data-check-target=d{i}] [data-action=resolve-check]').click()
        page.locator('#modal-form [name=all_years]').check()
        page.locator('#modal-form [type=submit]').click()
        expect(page.locator('#modal-form')).to_have_count(0)
        expect(page.locator('[data-check-code=decision_review]')).to_have_count(8-i)
    expect(page.locator('.tabs [data-tab=review] .tab-badge')).to_have_count(0)
    page.locator('[data-action=review-year][data-year="2025"]').click()
    expect(page.locator('[data-check-code=decision_review]')).to_have_count(0)
