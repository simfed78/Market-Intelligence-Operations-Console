"""Declared unit fixtures, never published or mixed into real source snapshots."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.intelligence.opportunities import rank_opportunities, top10, technical_score, evidence, HORIZONS, WEIGHTS
from src.intelligence.store import Store
from src.intelligence.analytics import clean_records


def rows():
    data=[]
    for kind in ['Azioni','Obbligazioni','Commodities']:
        for i in range(6):
            data.append(dict(symbol=f'{kind[:2]}{i}',name='Declared unit fixture',asset_class=kind,kind='ETF',region='USA',
                price_status='VALID',volume_status='VALID',ranking_eligible=True,momentum_1m=30+i*10,
                momentum_3m=35+i*10,momentum_6m=40+i*10,momentum_12m=45+i*10,
                risk_score=10+i*10,timing_score=100,early_opportunity=i==5))
    return pd.DataFrame(data)


def test_top10_deterministic_and_score_coherent():
    r=rank_opportunities(rows())
    top=top10(r)
    assert len(top)==10 and top.priority.tolist()==list(range(1,11))
    assert top.opportunity_score.is_monotonic_decreasing
    assert top.symbol.tolist()==top10(rank_opportunities(rows().sample(frac=1,random_state=3))).symbol.tolist()
    assert len(set(top.head(3).asset_class))==3


@pytest.mark.parametrize('horizon',HORIZONS)
def test_technical_weights_and_no_missing_factor_imputation(horizon):
    row=rows().iloc[5].to_dict();w=WEIGHTS['Azioni'][horizon]
    expected=sum(row['momentum_'+h]*weight for h,weight in zip(HORIZONS,w))
    assert technical_score(row,horizon)==pytest.approx(expected)
    assert all(sum(weights)==pytest.approx(1) for cls in WEIGHTS.values() for weights in cls.values())
    row['momentum_6m']=None
    assert technical_score(row,horizon) is None
    r=rank_opportunities(rows(),horizon)
    assert r[['macro_alignment','relative_value_score','capital_flow_score']].isna().all().all()
    assert not r.signal_state.eq('ENTRY CANDIDATE').any()


@pytest.mark.parametrize('status',['DEGRADED','SYNTHETIC','MISSING'])
def test_invalid_input_excluded_even_with_eligible_flag(status):
    f=rows();bad=f.symbol.iloc[0];f.loc[0,'price_status']=status
    r=rank_opportunities(f)
    assert r.set_index('symbol').loc[bad,'signal_state']=='BLOCKED'
    assert bad not in top10(r).symbol.tolist()


def test_filter_does_not_recompute_score_and_supports_empty():
    r=rank_opportunities(rows());selected=top10(r,asset_classes=['Obbligazioni'],risk=['Alto'])
    assert selected.asset_class.eq('Obbligazioni').all() and selected.risk_category.eq('Alto').all()
    assert all(r.set_index('symbol').loc[row.symbol,'opportunity_score']==row.opportunity_score for row in selected.itertuples())
    assert top10(r,asset_classes=[]).empty
    assert top10(r,early_only=True).early_opportunity.all()


def test_ties_and_small_peer_groups_fail_closed():
    f=rows();f.loc[f.asset_class.eq('Azioni'),['momentum_1m','momentum_3m','momentum_6m','momentum_12m']]=70
    r=rank_opportunities(f)
    assert r[r.asset_class.eq('Azioni')].opportunity_score.nunique()==1
    tiny=rank_opportunities(f.head(2))
    assert tiny.signal_state.eq('BLOCKED').all() and tiny.opportunity_score.isna().all()


def test_prior_rank_unknown_then_comparable_after_real_snapshot():
    f=rows();first=rank_opportunities(f)
    assert first.rank_change.isna().all()
    previous=first.set_index('symbol').to_dict('index')
    f.loc[0,['momentum_1m','momentum_3m','momentum_6m','momentum_12m']]=99
    updated=rank_opportunities(f,previous=previous)
    changed=updated.set_index('symbol').loc[f.symbol.iloc[0]]
    assert changed.rank_change==changed.previous_rank-changed['rank'] and changed.rank_change>0
    changed_universe=rank_opportunities(f.iloc[1:],previous=previous)
    assert changed_universe.rank_change.isna().all()
    assert rank_opportunities(f,'6m',previous).rank_change.isna().all()


def test_persisted_rank_history_model_horizon_and_time_gated(tmp_path):
    store=Store(tmp_path);r=rank_opportunities(rows())
    store.save_rankings('2026-11-07T10:00:00Z','3m',clean_records(r))
    assert not store.previous_rankings('2026-11-07T09:59:00Z','3m')
    assert not store.previous_rankings('2026-11-07T11:00:00Z','6m')
    loaded=store.previous_rankings('2026-11-07T11:00:00Z','3m')
    assert len(loaded)==18 and all(row['model_version']=='technical-priority-v1' for row in loaded.values())


def test_early_signal_requires_all_price_volume_and_benchmark_evidence():
    dates=pd.bdate_range(end='2026-11-06',periods=300)
    p=np.ones(300)*100;p[-85:-21]=np.linspace(95,96,64);p[-21:]=np.linspace(100,102,21)
    f=pd.DataFrame(dict(date=dates,adj_close=p,close=p,high=p+1,low=p-1))
    b=f.assign(adj_close=100.)
    row={**rows().iloc[0].to_dict(),'symbol':'A','benchmark':'B','ret_21':.02,'rvol_20':1.4,'volume_z60':1.,'obv_change20':10.,'cmf20':.1}
    result=evidence(row,{'A':f,'B':b},{'B':{'price_status':'VALID'}})
    assert result['early_opportunity'] and result['price_volume_divergence']
    assert 'potenziale' in result['accumulation']
    assert not evidence({**row,'volume_status':'MISSING'},{'A':f,'B':b},{'B':{'price_status':'VALID'}})['early_opportunity']
    assert not evidence(row,{'A':f,'B':b},{'B':{'price_status':'DEGRADED'}})['early_opportunity']


def test_public_mode_never_reads_core(tmp_path,monkeypatch):
    import shutil
    import src.intelligence.service as svc
    (tmp_path/'config').mkdir();shutil.copy(Path(__file__).parents[1]/'config/research_universe.json',tmp_path/'config')
    monkeypatch.setenv('TRADING_DESK_PUBLIC','1');monkeypatch.setenv('TRADING_DESK_ROOT','/private/core')
    monkeypatch.setattr(svc,'read_core',lambda root:pytest.fail('Core must never be read on public host'))
    result=svc.load_dashboard(tmp_path)
    assert result['public_mode'] and result['core']['status']=='MISSING'


def test_failed_refresh_keeps_snapshots_without_synthetic_fallback(tmp_path,monkeypatch):
    import shutil
    import src.intelligence.refresh as refresh
    (tmp_path/'config').mkdir();shutil.copy(Path(__file__).parents[1]/'config/research_universe.json',tmp_path/'config')
    monkeypatch.setenv('TRADING_DESK_PUBLIC','1')
    monkeypatch.setattr(refresh,'fetch_record',lambda symbol:(_ for _ in ()).throw(OSError('declared offline test')))
    result=refresh.refresh_sources(tmp_path)
    assert result['acquired']==0 and len(result['errors'])==153
    assert result['market_quality']=={'MISSING':145}
    assert Store(tmp_path).latest_snapshots()=={}


def test_real_ranking_read_is_pinned_to_completed_run(tmp_path,monkeypatch):
    import shutil
    from src.intelligence.service import load_dashboard
    (tmp_path/'config').mkdir();shutil.copy(Path(__file__).parents[1]/'config/research_universe.json',tmp_path/'config')
    store=Store(tmp_path);store.save_run('2026-11-07T09:00:00Z',{},[])
    seen=[]
    original=Store.latest_snapshots
    def track(self,as_of=None):
        seen.append(as_of);return original(self,as_of)
    monkeypatch.setattr(Store,'latest_snapshots',track)
    monkeypatch.setenv('TRADING_DESK_PUBLIC','1')
    load_dashboard(tmp_path,as_of='2026-11-07T10:00:00Z')
    assert seen[-1]=='2026-11-07T09:00:00.000000+00:00'
    load_dashboard(tmp_path,as_of='2026-11-07T10:00:00Z',include_unpublished=True)
    assert seen[-1]=='2026-11-07T10:00:00Z'
