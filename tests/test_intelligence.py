"""Synthetic unit fixtures are confined to tests, never shipped as research data."""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np
import pandas as pd
import pytest
from src.intelligence.market import normalize
from src.intelligence.analytics import asset_metrics, normalized_comparison
from src.intelligence.store import Store
from src.intelligence.refresh import import_record
from src.intelligence.core_monitor import read_core
from src.intelligence.service import load_dashboard
from src.intelligence.calendar import nyse_sessions

NOW='2026-11-07T12:00:00+00:00'
ROOT=Path(__file__).resolve().parents[1]


def fixture_snapshot():
    dates=nyse_sessions('2024-01-01','2026-11-06')[-300:].tz_localize('UTC')+pd.Timedelta(hours=14,minutes=30)
    p=np.linspace(90,120,len(dates)).tolist()
    q={'open':p,'high':[v+1 for v in p],'low':[v-1 for v in p],'close':p,'volume':list(range(1000,1300))}
    body={'chart':{'result':[{'meta':{'symbol':'SPY','currency':'USD','exchangeTimezoneName':'America/New_York','instrumentType':'ETF','exchangeName':'PCX'},
        'timestamp':(dates.astype('int64')//10**9).tolist(),'indicators':{'quote':[q],'adjclose':[{'adjclose':p}]}}]}}
    # pandas 3 indexes may carry microsecond units; convert each explicitly.
    body['chart']['result'][0]['timestamp']=[int(d.timestamp()) for d in dates]
    return make_snapshot(body)


def make_snapshot(body):
    payload=json.dumps(body)
    return dict(symbol='SPY',source='Yahoo Finance',source_url='https://query1.finance.yahoo.com/v8/finance/chart/SPY',
        retrieved_at='2026-11-07T10:00:00+00:00',kind='market',sha256=hashlib.sha256(payload.encode()).hexdigest(),payload=payload)


def mutate(snap, fn):
    body=json.loads(snap['payload']);fn(body['chart']['result'][0]);return make_snapshot(body)


def asset():
    return dict(symbol='SPY',name='S&P 500 proxy',asset_class='Azioni',region='USA',kind='ETF',currency='USD')


def test_returns_and_rvol_have_independent_expected_values():
    f,m=normalize(fixture_snapshot(),'SPY',NOW)
    assert m['price_status']=='VALID'
    r=asset_metrics(asset(),f,m)
    assert r['ret_21']==pytest.approx(120/(90+(299-21)*30/299)-1)
    assert r['rvol_20']==pytest.approx(1299/np.mean(np.arange(1279,1299)))
    assert r['timing_score']==100 and r['ranking_eligible']
    assert r['opportunity_score'] is None and r['flow_price_divergence'] is None


@pytest.mark.parametrize('field,value',[('volume',None),('volume',0),('volume',-1)])
def test_bad_volume_never_filled_or_used(field,value):
    s=mutate(fixture_snapshot(),lambda c:c['indicators']['quote'][0][field].__setitem__(-1,value))
    f,m=normalize(s,'SPY',NOW);r=asset_metrics(asset(),f,m)
    assert m['volume_status']=='MISSING' and r['rvol_20'] is None
    assert r['cmf20'] is None and r['ranking_eligible'] # volume not used by technical ranking


@pytest.mark.parametrize('condition',['hash','synthetic','stale','badclose','duplicate','wrong_symbol'])
def test_invalid_sources_never_rank(condition):
    s=fixture_snapshot()
    if condition=='hash': s['sha256']='0'*64
    if condition=='synthetic': s['kind']='synthetic'
    if condition=='badclose': s=mutate(s,lambda c:c['indicators']['quote'][0]['close'].__setitem__(-1,None))
    if condition=='duplicate': s=mutate(s,lambda c:c['timestamp'].__setitem__(-1,c['timestamp'][-2]))
    if condition=='wrong_symbol': s=mutate(s,lambda c:c['meta'].__setitem__('symbol','QQQ'))
    f,m=normalize(s,'SPY','2026-12-07T12:00:00+00:00' if condition=='stale' else NOW)
    assert m['price_status']!='VALID'
    r=asset_metrics(asset(),f,m)
    assert not r['ranking_eligible'] and r['momentum_3m'] is None


def test_availability_is_retrieval_never_backdated():
    s=fixture_snapshot()
    f,m=normalize(s,'SPY','2026-11-07T09:59:00+00:00')
    assert f.empty and m['price_status']=='MISSING'
    f,m=normalize(s,'SPY',NOW)
    assert m['available_at']==s['retrieved_at']


def test_current_exchange_session_excluded():
    s=fixture_snapshot();s['retrieved_at']='2026-11-06T18:00:00+00:00'
    f,m=normalize(s,'SPY','2026-11-06T19:00:00+00:00')
    assert str(f.date.iloc[-1].date())=='2026-11-05'


def test_comparisons_use_intersection_no_fill():
    a=pd.DataFrame({'date':pd.to_datetime(['2026-11-02','2026-11-03','2026-11-04']),'adj_close':[10,11,12]})
    b=pd.DataFrame({'date':pd.to_datetime(['2026-11-02','2026-11-04']),'adj_close':[20,24]})
    f=normalized_comparison({'A':a,'B':b},['A','B'])
    assert len(f)==2 and f.iloc[-1].tolist()==[120,120]


def test_store_timezones_hash_idempotency_and_asof(tmp_path,monkeypatch):
    monkeypatch.setattr('src.intelligence.market.utc_now',lambda:NOW)
    s=Store(tmp_path);r=fixture_snapshot()
    import_record(s,r,{'SPY'});import_record(s,r,{'SPY'})
    assert len(s.latest_snapshots())==1
    assert not s.latest_snapshots('2026-11-07T10:59:00+01:00')
    assert 'SPY' in s.latest_snapshots('2026-11-07T11:00:00+01:00')
    with s.connection() as c: assert c.execute('SELECT count(*) FROM snapshots').fetchone()[0]==1
    r['sha256']='corrupt'
    with pytest.raises(ValueError):import_record(s,r,{'SPY'})


def test_shortlist_limit_and_membership(tmp_path):
    (tmp_path/'config').mkdir();shutil.copy(ROOT/'config/research_universe.json',tmp_path/'config')
    s=Store(tmp_path)
    s.set_shortlist(['SPY','IEF']);assert s.get_shortlist()==['SPY','IEF']
    with pytest.raises(ValueError):s.set_shortlist(['SECRET'])
    with pytest.raises(ValueError):s.set_shortlist([str(i) for i in range(11)])


def test_core_reader_fail_closed_and_sanitized(tmp_path):
    result=read_core(tmp_path)
    assert result['phase2_gate']=='MISSING' and result['market_performance_computed'] is None
    assert result['dataset']['rows'] is None
    p=tmp_path/'data/demo_update/cross_snapshot.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'current_order_count':547,'clientId':'PRIVATE','balance':999}))
    result=read_core(tmp_path)
    assert result['demo']['pending_orders']==547
    assert 'PRIVATE' not in json.dumps(result) and '999' not in json.dumps(result)


def test_empty_dashboard_works_without_core_or_sources(tmp_path,monkeypatch):
    monkeypatch.setenv('TRADING_DESK_ROOT',str(tmp_path/'no_core'))
    (tmp_path/'config').mkdir();shutil.copy(ROOT/'config/research_universe.json',tmp_path/'config')
    d=load_dashboard(tmp_path)
    assert len(d['metrics'])==len(json.loads((ROOT/'config/research_universe.json').read_text())) and not d['metrics'].ranking_eligible.any()
    assert d['macro']['status']=='MISSING' and d['core']['status']=='MISSING'
    assert d['metrics'].opportunity_score.isna().all()


def test_run_history_asof_and_previous(tmp_path):
    s=Store(tmp_path)
    for t,v in [('2026-11-06T10:00:00Z',20),('2026-11-07T10:00:00+00:00',30)]:
        s.save_run(t,{'acquired':1},[{'symbol':'SPY','momentum_3m':v}])
    assert s.latest_run('2026-11-06T12:00:00Z')['run_at'].startswith('2026-11-06')
    assert s.previous_metrics('2026-11-07T10:00:00Z')['SPY']['momentum_3m']==20


def test_missing_internal_session_fails_closed():
    s=fixture_snapshot()
    def remove(c):
        c['timestamp'].pop(-10)
        for v in c['indicators']['quote'][0].values(): v.pop(-10)
        c['indicators']['adjclose'][0]['adjclose'].pop(-10)
    f,m=normalize(mutate(s,remove),'SPY',NOW)
    assert m['price_status']=='DEGRADED' and 'Sedute mancanti' in m['reason']
    assert not asset_metrics(asset(),f,m)['ranking_eligible']


def test_calendar_special_closure_and_holiday():
    sessions=nyse_sessions('2025-01-01','2025-01-21')
    assert pd.Timestamp('2025-01-09') not in sessions
    assert pd.Timestamp('2025-01-20') not in sessions
    assert pd.Timestamp('2025-01-10') in sessions
    assert nyse_sessions('2023-12-01','2024-01-10') is None


@pytest.mark.parametrize('broken',[{'payload':'x'}, {'kind':'macro','source':'FRED'}])
def test_partial_snapshot_isolated(broken):
    from src.intelligence.macro import macro_context
    f,m=normalize(broken,'SPY',NOW)
    assert f.empty and m['price_status']!='VALID'
    macro=macro_context({'FRED:CPIAUCSL':broken},NOW)
    assert macro['status']=='MISSING'


def test_macro_stale_nonfinite_and_month_gaps_never_classify():
    from src.intelligence.macro import macro_context
    for failure in ('stale','infinite','monthgap'):
        snapshots={}
        for code in ('CPIAUCSL','INDPRO'):
            dates=pd.date_range('2020-01-01' if failure=='stale' else '2025-05-01',periods=18,freq='MS')
            values=[100+i for i in range(18)]
            if failure=='infinite': values[-1]=float('inf')
            f=pd.DataFrame({'observation_date':dates,code:values})
            if failure=='monthgap': f=f.drop(index=5)
            text=f.to_csv(index=False)
            snapshots['FRED:'+code]=dict(kind='macro',source='FRED',retrieved_at='2026-11-07T10:00:00Z',payload=text,sha256=hashlib.sha256(text.encode()).hexdigest())
        result=macro_context(snapshots,NOW)
        assert result['label']=='Non disponibile'


def test_core_null_errors_and_symlink_are_safe(tmp_path):
    p=tmp_path/'datasets/spy_full_v2/quality_checks.json';p.parent.mkdir(parents=True)
    p.write_text('{"errors":null}')
    result=read_core(tmp_path)
    assert result['dataset']['missing_volume'] is None
    p.unlink();p.symlink_to('/etc/hosts')
    result=read_core(tmp_path)
    assert 'path fuori root' in result['reason']


def test_database_reader_does_not_mutate_and_corrupt_db_degrades(tmp_path,monkeypatch):
    s=Store(tmp_path);s.save_run('2026-11-07T10:00:00Z',{},[])
    before=hashlib.sha256(s.path.read_bytes()).hexdigest()
    s.latest_run();s.latest_snapshots();s.get_shortlist()
    assert hashlib.sha256(s.path.read_bytes()).hexdigest()==before
    s.path.write_bytes(b'corrupt')
    (tmp_path/'config').mkdir();shutil.copy(ROOT/'config/research_universe.json',tmp_path/'config')
    monkeypatch.setenv('TRADING_DESK_ROOT',str(tmp_path/'absent'))
    data=load_dashboard(tmp_path)
    assert data['errors'] and not data['metrics'].ranking_eligible.any()


def test_readonly_research_api_empty_contract(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app_api.main import create_app
    (tmp_path/'config').mkdir();shutil.copy(ROOT/'config/research_universe.json',tmp_path/'config')
    monkeypatch.setenv('TRADING_DESK_ROOT',str(tmp_path/'absent'))
    client=TestClient(create_app(tmp_path))
    reply=client.get('/research/v1/state')
    assert reply.status_code==200
    body=reply.json()
    assert body['schema_version']==1 and len(body['metrics'])==len(json.loads((ROOT/'config/research_universe.json').read_text()))
    assert all(not row['ranking_eligible'] for row in body['metrics'])
    assert client.post('/research/v1/state').status_code==405
    assert not (tmp_path/'data').exists()


def test_benchmark_index_is_not_ranked_as_tradeable_etf():
    f,m=normalize(fixture_snapshot(),'SPY',NOW)
    assert m['price_status']=='VALID'
    r=asset_metrics({**asset(),'kind':'INDEX'},f,m)
    assert not r['ranking_eligible'] and r['momentum_3m'] is None
