"""UI acceptance tests use explicitly synthetic fixtures, never real signals."""
from copy import deepcopy
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from app import intelligence_dashboard as ui
from app import fineco_workspace as fineco_ui
from src.intelligence.opportunities import rank_opportunities,HORIZONS

class MemoryStore:
    shortlist=[]
    def __init__(self,root):pass
    def get_shortlist(self):return MemoryStore.shortlist.copy()
    def set_shortlist(self,symbols):
        if len(symbols)>10:raise ValueError('Max10')
        MemoryStore.shortlist=list(symbols)

@pytest.fixture
def dashboard_model():
    assets=[];metrics=[];histories={}
    dates=pd.bdate_range(end='2026-11-06',periods=300)
    history=pd.DataFrame(dict(date=dates,close=range(100,400),adj_close=range(100,400),high=range(101,401),low=range(99,399),volume=range(1000,1300)))
    for symbol,ac,level in [('SPY','Azioni',65),('QQQ','Azioni',70),('IWM','Azioni',75),('IEF','Obbligazioni',65),('TLT','Obbligazioni',70),('LQD','Obbligazioni',75),('FAKE','Azioni',99),('NONE','Forex',50)]:
        status='SYNTHETIC' if symbol=='FAKE' else 'MISSING' if symbol=='NONE' else 'VALID'
        asset=dict(symbol=symbol,name=symbol+' declared fixture',asset_class=ac,region='USA',kind='ETF',currency='USD',benchmark='SPY',exposure_note='Declared fixture')
        assets.append(asset)
        metrics.append(dict(**asset,price_status=status,volume_status=status,source='Declared fixture',source_url='https://example.test/fixture',observed_at='2026-11-06',available_at='2026-11-07T08:00:00Z',retrieved_at='2026-11-07T08:00:00Z',price=123.45,
            ret_21=.02,ret_63=.06,ret_126=.08,ret_252=.1,drawdown_sample=-.01,momentum_1m=level,momentum_3m=level+2,momentum_6m=level+3,momentum_12m=level+4,timing_score=100,risk_score=30,rvol_5=1.1,rvol_20=1.2,rvol_60=1.3,
            volume_z60=0.1,obv_change20=1.,cmf20=.1,opportunity_score=None,data_confidence=status,ranking_eligible=status!='MISSING',early_opportunity=False,volume_signal='Volume nella norma',reason='Declared fixture only',
            score_change_1m=1.,score_change_3m=2.,score_change_6m=2.5,score_change_12m=3.))
        histories[symbol]=history.copy()
    f=pd.DataFrame(metrics)
    return dict(universe=pd.DataFrame(assets),metrics=f,histories=histories,opportunities={h:rank_opportunities(f,h) for h in HORIZONS},public_mode=False,
        macro=dict(status='MISSING',label='Non disponibile',reason='Declared missing source',observations=pd.DataFrame()),core=dict(mode='RESEARCH_ONLY',phase1_gate='OPEN',phase2_gate='BLOCKED',market_performance_computed=False,demo=dict(mode='DEMO_READ_ONLY')),latest_run=dict(run_at='2026-11-07T08:00:00Z'),errors=[])


def launch(monkeypatch,model):
    ui._load.clear();MemoryStore.shortlist=[]
    monkeypatch.setattr(ui,'load_dashboard',lambda root:deepcopy(model))
    monkeypatch.setattr(ui,'Store',MemoryStore)
    monkeypatch.setattr(fineco_ui,'_published_research',lambda:None)
    return AppTest.from_string('from app.intelligence_dashboard import main\nmain()',default_timeout=25).run()


def check(app):assert not app.exception,[e.message for e in app.exception]


def test_homepage_order_top10_factors_and_all_views(monkeypatch,dashboard_model):
    app=launch(monkeypatch,dashboard_model);check(app)
    headings=[h.value for h in app.subheader]
    assert headings[:5]==['Global Macro & Risk Regime','Top 10 Multi-Asset Opportunities','Emerging Opportunities / Capital Flow Radar','Equity vs Bonds Relative Value','Market Risk & Vulnerabilities']
    top=app.dataframe[0].value
    assert top.opportunity_score.is_monotonic_decreasing
    assert 'FAKE' not in top.symbol.tolist() and top.signal_state.eq('RESEARCH CANDIDATE').all()
    assert top.rank_change.isna().all() and 'ret_126' in top
    factors=app.dataframe[1].value
    assert factors[['macro_alignment','relative_value_score','capital_flow_score']].isna().all().all()
    for h in ['1 mese','6 mesi','12 mesi','3 mesi']:
        app.radio[1].set_value(h).run();check(app)
        assert app.dataframe[0].value.horizon.eq(ui.HORIZONS[h][0].removeprefix('momentum_')).all()
    for view in ui.VIEWS:
        app.radio[0].set_value(view).run();check(app)
        if view=='Asset explorer':assert len(app.get('plotly_chart'))==2
        if view=='Data quality':assert 'source_url' in app.dataframe[0].value


def test_filters_empty_asset_region_risk_and_early(monkeypatch,dashboard_model):
    app=launch(monkeypatch,dashboard_model)
    classes=next(x for x in app.multiselect if x.label=='Asset class')
    classes.set_value(['Azioni']).run();check(app)
    assert app.dataframe[0].value.asset_class.eq('Azioni').all()
    next(x for x in app.multiselect if x.label=='Rischio volatilità').set_value(['Alto']).run();check(app)
    assert any('Nessuna opportunità' in i.value for i in app.info)
    next(x for x in app.multiselect if x.label=='Asset class').set_value([]).run()
    for view in ui.VIEWS:
        app.radio[0].set_value(view).run();check(app)


def test_top10_detail_navigation_and_shortlist(monkeypatch,dashboard_model):
    app=launch(monkeypatch,dashboard_model)
    choice=next(x for x in app.selectbox if x.label=='Apri una scheda strumento')
    expected=choice.options[-1].split(' · ')[0]
    choice.select(expected).run()
    next(b for b in app.button if b.label=='Apri analisi completa').click().run();check(app)
    assert app.radio[0].value=='Asset explorer' and app.selectbox[0].value==expected
    assert any('Tesi di ricerca' in h.value for h in app.subheader)
    next(x for x in app.multiselect if x.label=='Monitoraggio approfondito').set_value(['SPY','IEF']).run()
    next(b for b in app.button if b.label=='Salva shortlist').click().run();check(app)
    assert set(MemoryStore.shortlist)=={'SPY','IEF'}
    next(x for x in app.checkbox if x.label=='Solo shortlist').check().run();check(app)
    assert set(app.selectbox[0].options)=={'SPY · SPY declared fixture','IEF · IEF declared fixture'}


def test_missing_sources_and_public_core_independent(monkeypatch,dashboard_model):
    model=deepcopy(dashboard_model);model['metrics']=pd.DataFrame();model['opportunities']={};model['histories']={};model['core']={};model['latest_run']=None
    app=launch(monkeypatch,model)
    for view in ui.VIEWS:
        app.radio[0].set_value(view).run();check(app)
    assert app.dataframe[0].value.price_status.eq('MISSING').all()


def test_public_shortlists_are_session_private(monkeypatch,dashboard_model):
    model=deepcopy(dashboard_model);model['public_mode']=True
    app=launch(monkeypatch,model)
    next(m for m in app.multiselect if m.label=='Monitoraggio approfondito').set_value(['SPY']).run()
    next(b for b in app.button if b.label=='Salva shortlist').click().run();check(app)
    assert app.session_state['public_shortlist']==['SPY']
    assert MemoryStore.shortlist==[]
    other=launch(monkeypatch,model);check(other)
    assert next(m for m in other.multiselect if m.label=='Monitoraggio approfondito').value==[]


def test_hosted_cold_start_shows_progress_not_false_outage(monkeypatch,dashboard_model):
    model=deepcopy(dashboard_model);model['public_mode']=True;model['latest_run']=None
    calls=[]
    def start(root,**kwargs):
        calls.append(root);return {'status':'RUNNING','completed':44,'total':153}
    monkeypatch.setattr(ui,'start_public_refresh',start)
    monkeypatch.setattr(ui,'public_status',lambda root:{'status':'RUNNING','completed':44,'total':153})
    app=launch(monkeypatch,model);check(app)
    assert len(calls)==1 and not app.warning
    assert app.get('progress') and not MemoryStore.shortlist


def test_mobile_compact_cards_put_action_near_ticker(monkeypatch,dashboard_model):
    monkeypatch.setattr(ui,'_compact_default',lambda:True)
    app=launch(monkeypatch,dashboard_model);check(app)
    assert not app.metric  # no four full-width macro cards above the opportunities
    assert next(c for c in app.checkbox if c.label=='Vista compatta').value
    buttons=[b for b in app.button if b.label=='Apri scheda']
    assert len(buttons)==6
    assert any('Da approfondire' in w.value for w in app.markdown)
    buttons[0].click().run();check(app)
    assert app.radio[0].value=='Asset explorer'


def test_fineco_workspace_default_is_private_and_no_unfunded_orders(monkeypatch,dashboard_model):
    app=launch(monkeypatch,dashboard_model)
    app.radio[0].set_value("Fineco · Piano operativo").run();check(app)
    actions=app.dataframe[0].value
    assert set(actions["ETF/ETC"])=={"VALL","PRAB","SGLN"}
    assert actions["EUR massimo"].eq(0).all()
    assert all(actions["Azione"]=="ATTENDERE")
    assert not any("612.56" in str(m.value) for m in app.markdown)
    assert any("Budget investibile non confermato" in w.value for w in app.warning)
    assert any("Commodities" in m.value for m in app.markdown)


def test_fineco_primary_navigation_and_release_are_visible(monkeypatch,dashboard_model):
    app=launch(monkeypatch,dashboard_model);check(app)
    assert any(ui.APP_RELEASE in x.value for x in app.caption)
    button=next(b for b in app.button if b.label=="Apri Fineco · Piano operativo")
    button.click().run();check(app)
    assert app.radio[0].value=="Fineco · Piano operativo"
    assert {x for x in app.dataframe[0].value["ETF/ETC"]}=={"VALL","PRAB","SGLN"}
