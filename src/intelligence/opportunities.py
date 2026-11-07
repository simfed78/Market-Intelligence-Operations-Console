"""Research priority model 1.0. No expected-return calibration, entry authorization or broker imports.

Cross-class comparability is deliberately ordinal: a within-class percentile of a
technical-only composite. It is NOT comparable absolute attractiveness or valuation.
All mandatory factors must exist; absent values never become neutral 50s.
"""
from __future__ import annotations
import hashlib
import json
import numpy as np
import pandas as pd

MODEL_VERSION='technical-priority-v1'
HORIZONS=('1m','3m','6m','12m')
WEIGHTS={
 'Azioni':{'1m':(.5,.3,.15,.05),'3m':(.15,.45,.25,.15),'6m':(.1,.2,.45,.25),'12m':(.05,.15,.3,.5)},
 'Obbligazioni':{'1m':(.35,.35,.2,.1),'3m':(.1,.4,.3,.2),'6m':(.05,.2,.4,.35),'12m':(.05,.1,.3,.55)},
 'Commodities':{'1m':(.55,.3,.1,.05),'3m':(.2,.45,.25,.1),'6m':(.1,.25,.45,.2),'12m':(.05,.2,.35,.4)},
 'Forex':{'1m':(.55,.25,.15,.05),'3m':(.2,.4,.3,.1),'6m':(.1,.25,.4,.25),'12m':(.05,.15,.35,.45)},
}
EARLY_LIMIT={'Azioni':.05,'Obbligazioni':.02,'Commodities':.07,'Forex':.03}


def finite(value):
    try:
        x=float(value)
        return x if np.isfinite(x) else None
    except (ValueError,TypeError):return None


def subcategory(row):
    symbol=row.get('symbol')
    if row.get('asset_class')=='Obbligazioni':
        groups={'Corporate IG':{'LQD','VCIT'},'Corporate HY':{'HYG','JNK'},'Credito tasso variabile':{'BKLN'},'Titoli inflation-linked':{'TIP','STIP'},'Credito cartolarizzato':{'MBB'},'Governativi emergenti':{'EMB','EMLC'},'Aggregate / internazionale':{'AGG','BND','BNDX','IGOV','BWX'}}
        return next((name for name,tickers in groups.items() if symbol in tickers),'Governativi USA / duration')
    if row.get('asset_class')=='Commodities':
        return 'Metallo fisico / trust' if symbol in {'GLD','IAU','SLV','PPLT','PALL'} else 'Paniere / futures commodity'
    return (row.get('exposure_label') or row.get('region')) if row.get('asset_class')=='Azioni' else 'Cross valutario'


def eligible(row):
    return (row.get('price_status')=='VALID' and row.get('ranking_eligible')==True
            and row.get('kind') in ('ETF','ETP','FX') and row.get('asset_class') in WEIGHTS)


def technical_score(row,horizon):
    values=[finite(row.get('momentum_'+h)) for h in HORIZONS]
    if not eligible(row) or any(v is None or not 0<=v<=100 for v in values):return None
    return float(np.dot(values,WEIGHTS[row['asset_class']][horizon]))


def evidence(row, histories, metrics):
    """Signals consume already qualified inputs only. No effect on composite weights."""
    result=dict(rs_21=None,rs_63=None,rs_improvement=None,rs_status='MISSING',
                sma50=None,sma200=None,resistance20=None,support20=None,breakout_confirmed=False,
                early_opportunity=False,early_status='MISSING',volume_signal='MISSING',
                accumulation='Non determinabile',price_volume_divergence=False)
    if not eligible(row):return result
    f=histories.get(row['symbol'],pd.DataFrame())
    if not f.empty and {'date','adj_close','close','high','low'}<=set(f.columns):
        p=f.adj_close
        if len(p)>=200 and p.notna().all() and (p>0).all():
            factor=float(f.close.iloc[-1]/p.iloc[-1])
            result.update(sma50=float(p.tail(50).mean()*factor),sma200=float(p.tail(200).mean()*factor),
                          resistance20=float(f.high.iloc[-21:-1].max()),support20=float(f.low.iloc[-21:-1].min()))
            result['breakout_confirmed']=float(f.close.iloc[-1])>result['resistance20']
    benchmark=row.get('benchmark');b=metrics.get(benchmark,{})
    bh=histories.get(benchmark,pd.DataFrame())
    if b.get('price_status')=='VALID' and not f.empty and not bh.empty:
        aligned=pd.concat([f.set_index('date').adj_close.rename('a'),bh.set_index('date').adj_close.rename('b')],axis=1,join='inner').dropna()
        if len(aligned)>=85 and (aligned>0).all().all():
            ratio=aligned.a/aligned.b
            r21=float(ratio.iloc[-1]/ratio.iloc[-22]-1)
            r63=float(ratio.iloc[-1]/ratio.iloc[-64]-1)
            prior=float(ratio.iloc[-22]/ratio.iloc[-85]-1)
            result.update(rs_21=r21,rs_63=r63,rs_improvement=r63-prior,rs_status='VALID')
    if row.get('volume_status')=='VALID':
        rv=finite(row.get('rvol_20'));z=finite(row.get('volume_z60'))
        obv=finite(row.get('obv_change20'));cmf=finite(row.get('cmf20'))
        if rv is not None or z is not None:
            anomaly=(rv is not None and rv>=1.5) or (z is not None and z>=2)
            result['volume_signal']='Volume anomalo' if anomaly else 'Volume nella norma'
        ret=finite(row.get('ret_21'));limit=EARLY_LIMIT[row['asset_class']]
        flat=ret is not None and abs(ret)<=limit
        if obv is not None and cmf is not None and obv>0 and cmf>0:
            result['accumulation']='Accumulo potenziale · OBV e CMF concordi (non flussi netti)'
            result['price_volume_divergence']=flat
        complete=(ret is not None and rv is not None and obv is not None and cmf is not None and result['rs_status']=='VALID')
        if complete:
            result['early_status']='VALID'
            result['early_opportunity']=bool(flat and rv>=1.2 and obv>0 and cmf>0 and result['rs_improvement']>0)
    return result


def decorate_metrics(metrics, histories):
    frame=metrics.copy()
    lookup={r['symbol']:r for r in frame.to_dict('records')}
    rows=[]
    for row in frame.to_dict('records'):
        row['exposure_label']=row.get('name')
        row['name']=row.get('provider_name') or row.get('name')
        rows.append({**row,**evidence(row,histories,lookup)})
    return pd.DataFrame(rows)


def rank_opportunities(metrics, horizon='3m', previous=None):
    if horizon not in HORIZONS:raise ValueError('Unknown horizon')
    previous=previous or {}
    rows=[]
    for r in metrics.to_dict('records'):
        r.setdefault('early_opportunity',False)
        r.setdefault('volume_signal','MISSING')
        r.setdefault('price_volume_divergence',False)
        score=technical_score(r,horizon)
        risk=finite(r.get('risk_score'))
        timing=finite(r.get('timing_score'))
        missing=score is None or risk is None or timing is None or not 0<=risk<=100 or timing not in (0,50,100)
        state='BLOCKED' if missing else 'RESEARCH CANDIDATE' if score>=60 and timing>=50 else 'WATCHLIST'
        row={**r,'technical_score':score,'opportunity_score':None,'horizon':horizon,'signal_state':state,
             'model_version':MODEL_VERSION,'macro_alignment':None,'relative_value_score':None,'capital_flow_score':None,
             'macro_alignment_status':'MISSING','relative_value_status':'MISSING','capital_flow_status':'MISSING',
             'included_factors':'Solo momentum tecnico 1/3/6/12m; percentile entro asset class',
             'risk_category':'Non determinabile' if risk is None else 'Basso' if risk<25 else 'Medio' if risk<50 else 'Alto',
             'entry_validation':'MISSING · modello di ingresso non validato; nessuna promozione ENTRY CANDIDATE',
             'rank':None,'rank_change':None,'previous_rank':None,'peer_count':None,'coverage_key':None,
             'subcategory':subcategory(r),'rationale':'Dati essenziali mancanti/non validi' if missing else
                f"Momentum {horizon}: indice tecnico {score:.1f}/100; conferma {timing:.0f}/100. "
                +('Trend da approfondire.' if state=='RESEARCH CANDIDATE' else 'Attendere miglioramento del trend.'),
             'updated_at':r.get('retrieved_at')}
        rows.append(row)
    frame=pd.DataFrame(rows)
    if frame.empty:return frame
    candidates=frame[frame.signal_state!='BLOCKED']
    for asset_class, peers in candidates.groupby('asset_class',sort=True):
        idx=peers.index;n=len(peers)
        frame.loc[idx,'peer_count']=n
        coverage=hashlib.sha256(json.dumps(sorted(peers.symbol.tolist())).encode()).hexdigest()[:16]
        frame.loc[idx,'coverage_key']=coverage
        if n<3:
            frame.loc[idx,'signal_state']='BLOCKED'
            frame.loc[idx,'rationale']='Meno di tre peer validi: percentile non confrontabile.'
            continue
        # Average ties: identical technical measures receive identical ordinal score.
        percentiles=(peers.technical_score.rank(method='average')-1)/(n-1)*100
        frame.loc[idx,'opportunity_score']=percentiles
    scored=frame[frame.opportunity_score.notna()].sort_values(['opportunity_score','asset_class','symbol'],ascending=[False,True,True])
    global_coverage=hashlib.sha256(json.dumps(sorted(scored.symbol.tolist())).encode()).hexdigest()[:16]
    for rank,(idx,row) in enumerate(scored.iterrows(),start=1):
        frame.at[idx,'rank']=rank
        old=previous.get(row['symbol'],{})
        # No invented historical rank; unchanged universe + identical model/horizon only.
        if (old.get('model_version')==MODEL_VERSION and old.get('horizon')==horizon
            and old.get('global_coverage')==global_coverage and old.get('coverage_key')==row['coverage_key']
            and finite(old.get('rank')) is not None):
            frame.at[idx,'previous_rank']=int(old['rank'])
            frame.at[idx,'rank_change']=int(old['rank'])-rank
    frame['global_coverage']=global_coverage
    return frame.sort_values(['rank','symbol'],na_position='last').reset_index(drop=True)


def top10(frame, asset_classes=None, regions=None, risk=None, early_only=False):
    """Filter precomputed full-universe scores; never inflate percentiles by filtering."""
    selected=frame.copy()
    if selected.empty:return selected
    if asset_classes is not None:selected=selected[selected.asset_class.isin(asset_classes)]
    if regions is not None:selected=selected[selected.region.isin(regions)]
    if risk is not None:selected=selected[selected.risk_category.isin(risk)]
    if early_only:selected=selected[selected.early_opportunity.eq(True)]
    selected=selected[selected.signal_state.ne('BLOCKED')&selected.opportunity_score.notna()].sort_values(['rank','symbol']).head(10).copy()
    selected.insert(0,'priority',range(1,len(selected)+1))
    return selected
