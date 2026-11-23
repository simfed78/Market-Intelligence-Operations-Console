"""Latest revised macro context; intentionally unsuitable for historical regime testing."""
from io import StringIO
import hashlib
import pandas as pd
import numpy as np
from .market import utc_now

SERIES={
 'CPIAUCSL':('CPI USA','indice',75), 'INDPRO':('Produzione industriale USA','indice',75),
 'DGS10':('Treasury 10 anni','%',7),'DFII10':('Treasury reale 10 anni','%',7),
 'T10YIE':('Breakeven 10 anni','%',7),'BAMLH0A0HYM2':('HY option adjusted spread','punti %',7),
 'BAMLC0A0CM':('IG option adjusted spread','punti %',7),'NFCI':('Financial conditions Chicago Fed','indice',21)
}


def macro_context(snapshots, as_of=None):
    now=pd.Timestamp(as_of or utc_now())
    rows=[]
    data={}
    for code,(name,unit,max_age) in SERIES.items():
        snap=snapshots.get('FRED:'+code)
        row=dict(series=code,name=name,value=None,unit=unit,status='MISSING',observed_at=None,
                 available_at=None,retrieved_at=None,source='FRED',source_url=f'https://fred.stlouisfed.org/series/{code}',
                 publication_at=None,vintage='Revised latest; release/vintage unknown')
        row.update(stale=None,reason='Nessuna serie valida acquisita')
        if (isinstance(snap,dict) and snap.get('kind')=='macro'
                and snap.get('source') in ('FRED','FRED-MD','BLS','FRB-G17')):
            try:
                if pd.Timestamp(snap['retrieved_at'])>now: raise ValueError('Not yet available')
                if hashlib.sha256(snap['payload'].encode()).hexdigest()!=snap['sha256']: raise ValueError('Hash mismatch')
                f=pd.read_csv(StringIO(snap['payload']))
                f.columns=['date','value']
                f['date']=pd.to_datetime(f.date)
                f['value']=pd.to_numeric(f.value,errors='coerce')
                f=f[(f.date<=now.tz_localize(None).normalize())&f.value.notna()].sort_values('date')
                valid_values=not f.empty and np.isfinite(f.value.to_numpy()).all()
                if code in ('CPIAUCSL','INDPRO'):
                    valid_values=valid_values and (f.value>0).all() and not f.date.dt.to_period('M').duplicated().any()
                    if len(f)>1 and not (code=='CPIAUCSL' and snap.get('source')=='BLS'):
                        valid_values=valid_values and len(pd.period_range(f.date.iloc[0],f.date.iloc[-1],freq='M'))==len(f)
                if valid_values and not f.date.duplicated().any():
                    data[code]=f
                    row.update(value=float(f.value.iloc[-1]), observed_at=f.date.iloc[-1].date().isoformat(),
                               available_at=snap['retrieved_at'],retrieved_at=snap['retrieved_at'],
                               source=snap['source'], source_url=snap.get('source_url'),
                               status='DEGRADED',reason='Osservazione da '+snap['source']+'; release/vintage storici non qualificati')
                    row['stale']=(now.tz_localize(None).date()-f.date.iloc[-1].date()).days>max_age
            except (ValueError,KeyError,TypeError):
                pass
        rows.append(row)
    frame=pd.DataFrame(rows)
    label='Non disponibile'
    reason='Servono CPI e produzione industriale reali con sufficiente storia. Nessun fallback neutrale.'
    fresh=set(frame.loc[frame.get('stale',pd.Series(True,index=frame.index)).eq(False),'series'])
    if all(c in data and c in fresh and len(data[c])>=16 for c in ('CPIAUCSL','INDPRO')):
        c=data['CPIAUCSL'].set_index('date').value
        g=data['INDPRO'].set_index('date').value
        # Point-in-observation-date comparisons, not positional "12 rows ago":
        # BLS may explicitly mark a month unavailable (e.g. a survey interruption).
        comparable=None
        for observed in reversed(c.index):
            year_ago=observed-pd.DateOffset(months=12)
            earlier=observed-pd.DateOffset(months=3)
            earlier_year=observed-pd.DateOffset(months=15)
            if all(d in c.index for d in (year_ago,earlier,earlier_year)):
                comparable=(observed,year_ago,earlier,earlier_year)
                break
        current_growth=g.index[-1]
        previous_growth=current_growth-pd.DateOffset(months=3)
        if comparable is not None and previous_growth in g.index:
            observed,year_ago,earlier,earlier_year=comparable
            inflation=float(c.loc[observed]/c.loc[year_ago]-1)*100
            old=float(c.loc[earlier]/c.loc[earlier_year]-1)*100
            growth=float(g.loc[current_growth]/g.loc[previous_growth]-1)*100
            label=('Espansione' if growth>0 else 'Contrazione')+' / '+('inflazione in accelerazione' if inflation>old else 'disinflazione')
            reason=(f'Contesto USA indicativo: produzione industriale 3 mesi {growth:+.2f}% '
                    f'(a {current_growth:%Y-%m}); CPI annuo {inflation:.2f}% '
                    f'(a {observed:%Y-%m}), contro {old:.2f}% tre mesi prima. '
                    'Confronti solo tra mesi effettivamente osservati, nessuna interpolazione; '
                    'dati rivisti, vintage storici non certificati, escluso dal ranking.')
    return dict(status='DEGRADED' if frame.value.notna().any() else 'MISSING',label=label,reason=reason,observations=frame)
