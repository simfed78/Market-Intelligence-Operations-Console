"""Provider response normalization and research-quality gates, never data synthesis."""
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import hashlib
import json
import pandas as pd
import numpy as np
from .calendar import nyse_sessions


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def chart_url(symbol):
    from urllib.parse import quote
    return f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe="")}?range=2y&interval=1d&events=div%2Csplits'


def normalize(snapshot, symbol, as_of=None):
    empty = pd.DataFrame(columns=['date','close','adj_close','high','low','open','volume'])
    meta = dict(price_status='MISSING',volume_status='MISSING',reason='Nessuna serie acquisita',
                source=None,source_url=None,observed_at=None,available_at=None,retrieved_at=None,currency=None)
    if not snapshot:
        return empty, meta
    if not isinstance(snapshot,dict) or not {'retrieved_at','payload','sha256','source','kind'} <= snapshot.keys():
        return empty, {**meta,'price_status':'DEGRADED','reason':'Schema snapshot incompleto'}
    meta.update({k:snapshot.get(k) for k in ('source','source_url','retrieved_at')})
    meta['available_at'] = snapshot['retrieved_at']  # first known availability: never infer publication
    if snapshot.get('kind') != 'market' or snapshot.get('source') != 'Yahoo Finance':
        meta.update(price_status='SYNTHETIC' if snapshot.get('kind') == 'synthetic' else 'DEGRADED',reason='Provenienza non ammessa al ranking')
        return empty, meta
    if hashlib.sha256(snapshot['payload'].encode()).hexdigest() != snapshot['sha256']:
        meta.update(price_status='DEGRADED',reason='Hash del payload non coerente')
        return empty, meta
    now = pd.Timestamp(as_of or utc_now())
    if now.tzinfo is None:
        now = now.tz_localize('UTC')
    try:
        if pd.Timestamp(snapshot['retrieved_at']).tzinfo is None:
            raise ValueError('Timezone required')
        if pd.Timestamp(snapshot['retrieved_at']) > now:
            return empty, {**meta, 'reason':'Snapshot non disponibile alla data richiesta'}
        data = json.loads(snapshot['payload'])['chart']['result'][0]
        provider = data['meta']
        if provider['symbol'].upper() != symbol.upper():
            raise ValueError('Symbol mismatch')
        q = data['indicators']['quote'][0]
        tz = ZoneInfo(provider.get('exchangeTimezoneName','America/New_York'))
        dates = pd.to_datetime(data['timestamp'], unit='s', utc=True).tz_convert(tz).tz_localize(None).normalize()
        frame = pd.DataFrame({'date':dates, **{k:q.get(k, [None]*len(dates)) for k in ('close','high','low','open','volume')}})
        adj = data['indicators'].get('adjclose', [{}])[0].get('adjclose')
        frame['adj_close'] = adj if adj is not None else np.nan
        # Conservative: the current exchange-local day is always excluded, including after close.
        frame = frame[frame.date < now.tz_convert(tz).tz_localize(None).normalize()].copy()
        frame = frame.sort_values('date').reset_index(drop=True)
        if frame.empty:
            return empty, meta
        meta.update(provider_name=provider.get('longName') or provider.get('shortName'),currency='punti indice' if provider.get('instrumentType')=='INDEX' else provider.get('currency'),
                    observed_at=frame.date.iloc[-1].date().isoformat())
        prices = frame[['open','high','low','close','adj_close']]
        bad = (prices.isna().any().any() or (prices <= 0).any().any() or not np.isfinite(prices.to_numpy()).all()
               or frame.date.duplicated().any() or (frame.high < frame.low).any()
               or (frame.high < frame[['open','close']].max(axis=1)-1e-6).any()
               or (frame.low > frame[['open','close']].min(axis=1)+1e-6).any())
        age = (now.tz_convert(tz).date() - frame.date.iloc[-1].date()).days
        gaps = frame.date.diff().dt.days.max()
        reasons=[]
        if bad: reasons.append('OHLC/rettifiche mancanti, non finiti, incoerenti o date duplicate')
        if len(frame)<253: reasons.append('Meno di 253 sedute')
        if age>4: reasons.append(f'Ultima seduta obsoleta: {age} giorni')
        if gaps>7: reasons.append('Lacune di calendario >7 giorni; sessioni non certificate')
        if provider.get('instrumentType') in ('ETF','EQUITY'):
            venue=provider.get('exchangeName')
            expected=nyse_sessions(frame.date.iloc[0],now.tz_convert(tz).tz_localize(None).normalize()-pd.Timedelta(days=1))
            if venue not in ('PCX','NMS','NGM','NCM','NYQ','ASE','BTS','BATS') or expected is None:
                reasons.append('Calendario venue/anni non supportato')
            elif len(expected.difference(pd.DatetimeIndex(frame.date))) or len(pd.DatetimeIndex(frame.date).difference(expected)):
                reasons.append('Sedute mancanti o inattese nel calendario azionario USA')
        elif provider.get('instrumentType')=='CURRENCY':
            reasons.append('Calendario FX e OHLC non certificati per il ranking')
        if provider.get('instrumentType') not in ('ETF','MUTUALFUND','CURRENCY','INDEX','FUTURE','EQUITY'):
            reasons.append('Tipo provider sconosciuto')
        meta['price_status']='DEGRADED' if reasons else 'VALID'
        meta['reason']='; '.join(reasons) or 'Controlli interni OHLC, rettifiche, unicità, sedute e freschezza superati; fonte singola, non certificato per backtest'
        v=frame.volume
        has_volume=(provider.get('instrumentType') not in ('CURRENCY','INDEX') and not v.isna().any()
                    and np.isfinite(v.to_numpy()).all() and (v>=0).all() and (v.tail(61)>0).all())
        meta['volume_status']='VALID' if has_volume and meta['price_status']=='VALID' else ('DEGRADED' if has_volume else 'MISSING')
        return frame, meta
    except (KeyError,ValueError,TypeError,IndexError) as exc:
        meta.update(price_status='DEGRADED', reason=f'Payload non conforme: {type(exc).__name__}')
        return empty, meta
