"""Transparent technical research measures. No calibrated expected-return claims."""
import numpy as np
import pandas as pd

SCALES={'Azioni':0.20,'Obbligazioni':0.07,'Commodities':0.25,'Forex':0.10}


def asset_metrics(asset, frame, meta):
    row={**asset,**meta}
    nulls=['ret_21','ret_63','ret_126','ret_252','drawdown_sample','rvol_5','rvol_20','rvol_60',
           'momentum_1m','momentum_3m','momentum_6m','momentum_12m','timing_score','risk_score','opportunity_score',
           'previous_score','score_change','volume_z60','obv_change20','cmf20','flow_price_divergence']
    row.update({k:None for k in nulls})
    row.update(ranking_eligible=False,data_confidence=meta['price_status'],price=None,
               flow_price_status='MISSING',flow_status='MISSING',valuation_status='MISSING',
               macro_fit_status='MISSING',ath_status='MISSING')
    if frame.empty:
        return row
    p=frame.adj_close
    row['price']=float(frame.close.iloc[-1]) if pd.notna(frame.close.iloc[-1]) else None
    row['drawdown_sample']=float(p.iloc[-1]/p.max()-1) if p.notna().all() else None
    for n in (21,63,126,252):
        if len(p)>n and p.tail(n+1).notna().all() and (p.tail(n+1)>0).all():
            row[f'ret_{n}']=float(p.iloc[-1]/p.iloc[-n-1]-1)
    if meta['price_status']!='VALID' or asset['asset_class']=='Rischio' or asset.get('kind')=='INDEX':
        return row
    row['ranking_eligible']=True
    # Fixed ex-ante asset-class scale. A centered bounded technical index, not a probability.
    scale=SCALES[asset['asset_class']]
    for label,n in [('1m',21),('3m',63),('6m',126),('12m',252)]:
        row[f'momentum_{label}']=float(50+50*np.tanh(row[f'ret_{n}']/(scale*np.sqrt(n/252))))
    row['timing_score']=float(50*int(p.iloc[-1]>p.tail(50).mean())+50*int(p.tail(50).mean()>p.tail(200).mean()))
    vol=float(p.pct_change(fill_method=None).tail(63).std()*np.sqrt(252))
    row['risk_score']=float(100*min(1,vol/(2*scale)))  # realized vol scaled to asset class; higher = more volatility
    if meta['volume_status']=='VALID':
        v=frame.volume
        for n in (5,20,60):
            denominator=v.shift(1).rolling(n).mean().iloc[-1]
            row[f'rvol_{n}']=float(v.iloc[-1]/denominator) if denominator>0 else None
        sd=v.shift(1).rolling(60).std().iloc[-1]
        row['volume_z60']=float((v.iloc[-1]-v.shift(1).rolling(60).mean().iloc[-1])/sd) if sd>0 else None
        signed=np.sign(frame.close.diff())*v
        row['obv_change20']=float(signed.tail(20).sum())
        spread=frame.high-frame.low
        # Raw OHLC consistency, not provider-adjusted synthetic highs/lows.
        mf=((2*frame.close-frame.low-frame.high)/spread.replace(0,np.nan))*v
        if mf.tail(20).notna().all() and v.tail(20).sum()>0:
            row['cmf20']=float(mf.tail(20).sum()/v.tail(20).sum())
        # Increment 2 deliberately not emitted until preregistered/validated.
    return row


def clean_records(frame):
    return frame.astype(object).where(pd.notna(frame),None).to_dict('records')


def normalized_comparison(histories, symbols, lookback=252):
    series=[]
    for symbol in symbols:
        f=histories.get(symbol,pd.DataFrame())
        if not f.empty:
            series.append(f.set_index('date').adj_close.rename(symbol))
    if not series:
        return pd.DataFrame()
    aligned=pd.concat(series,axis=1,join='inner').tail(lookback).dropna(how='any')
    return aligned/aligned.iloc[0]*100 if not aligned.empty else aligned
