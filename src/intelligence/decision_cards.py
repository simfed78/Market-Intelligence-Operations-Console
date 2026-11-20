"""Descriptive research explanations; never authorize entries or change rankings."""
from __future__ import annotations

from src.intelligence.opportunities import finite


def decision_summary(row):
    valid = row.get('price_status') == 'VALID' and row.get('signal_state') != 'BLOCKED'
    result = dict(trend='Non disponibile', momentum='Non disponibile', extension=None,
                  confirmation='Aggiornare e verificare i dati prima di valutare la tesi.',
                  invalidation='Non determinabile senza dati qualificati.',
                  volume='MISSING · volumi non qualificati')
    if not valid:
        return result
    price, ma50, ma200 = (finite(row.get(k)) for k in ('price', 'sma50', 'sma200'))
    if price is not None and price > 0 and ma50 is not None and ma200 is not None and min(ma50, ma200) > 0:
        result['trend'] = ('Rialzista' if price > max(ma50, ma200) else
                           'Ribassista' if price < min(ma50, ma200) else 'Misto')
        result['extension'] = (price / ma50 - 1) * 100
    r1, r3 = (finite(row.get(k)) for k in ('ret_21', 'ret_63'))
    if r1 is not None and r3 is not None and min(r1, r3) > -1:
        result['momentum'] = 'In miglioramento' if r1 > (1 + r3)**(1/3) - 1 else 'In rallentamento'
    resistance, support = (finite(row.get(k)) for k in ('resistance20', 'support20'))
    if price is not None and price > 0 and resistance is not None and resistance > 0 and ma50 is not None and ma50 > 0 and ma200 is not None and ma200 > 0:
        result['confirmation'] = (
            f'Controllare la tenuta sopra SMA50 {ma50:,.2f} e SMA200 {ma200:,.2f}; '
            + (f'chiusura sopra il massimo delle 20 sedute precedenti {resistance:,.2f} già osservata.'
               if price > resistance else f'attendere chiusura sopra il massimo delle 20 sedute precedenti {resistance:,.2f}.')
            + ' Condizioni descrittive: modello di ingresso non validato.'
        )
    if support is not None and support > 0:
        result['invalidation'] = f'Una chiusura sotto il minimo delle 20 sedute precedenti {support:,.2f} indebolirebbe la tesi tecnica; riesaminare il candidato. Non è uno stop operativo.'
    if row.get('volume_status') == 'VALID':
        rv, z = (finite(row.get(k)) for k in ('rvol_20', 'volume_z60'))
        parts = [str(row.get('volume_signal') or 'Volume qualificato')]
        if rv is not None:
            parts.append(f'RVOL20 {rv:.2f}×')
        if z is not None:
            parts.append(f'z-score60 {z:+.2f}')
        result['volume'] = ' · '.join(parts) + ' · non misura flussi netti'
    return result
