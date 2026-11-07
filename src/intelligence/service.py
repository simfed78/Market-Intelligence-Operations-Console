"""Unified view contract, isolated from legacy fallback data and Core execution."""
from pathlib import Path
import os
import sqlite3
import platform
import pandas as pd
from .universe import load_universe
from .store import Store
from .market import normalize, utc_now
from .analytics import asset_metrics
from .macro import macro_context
from .core_monitor import read_core
from .opportunities import decorate_metrics, rank_opportunities, HORIZONS


def load_dashboard(root: Path, as_of=None, *, include_unpublished=False):
    root=Path(root)
    now=as_of or utc_now()
    universe=load_universe(root)
    store=Store(root)
    read_errors=[]
    try:
        latest=store.latest_run(now)
        cutoff=now if include_unpublished or not latest else latest['run_at']
        snapshots=store.latest_snapshots(as_of=cutoff) if latest or include_unpublished else {}
        previous=store.previous_metrics(latest['run_at']) if latest else {}
    except (OSError,sqlite3.DatabaseError):
        snapshots={};latest=None;previous={}
        read_errors.append('Database locale non leggibile: nessun dato promosso nel ranking.')
    metrics=[]; histories={}
    for asset in universe.to_dict('records'):
        f,meta=normalize(snapshots.get(asset['symbol']),asset['symbol'],as_of=now)
        histories[asset['symbol']]=f
        row=asset_metrics(asset,f,meta)
        old=previous.get(asset['symbol'],{})
        for horizon in ('1m','3m','6m','12m'):
            prior=old.get('momentum_'+horizon)
            current=row['momentum_'+horizon]
            row['previous_score_'+horizon]=prior
            row['score_change_'+horizon]=(current-prior) if current is not None and prior is not None else None
        row['previous_score']=row['previous_score_3m']
        row['score_change']=row['score_change_3m']
        metrics.append(row)
    core_root=Path(os.getenv('TRADING_DESK_ROOT',str(Path.home()/'Documents/TRADING DESK')))
    public_mode=os.getenv('TRADING_DESK_PUBLIC')=='1' or (platform.system()!='Darwin' and not os.getenv('TRADING_DESK_ROOT'))
    core=({'status':'MISSING','reason':'Monitor Core disabilitato nella versione pubblica.'} if public_mode else read_core(core_root)) if as_of is None else {'status':'MISSING','reason':'Il monitor Core rappresenta soltanto lo stato corrente; escluso dalle viste storiche.'}
    enriched=decorate_metrics(pd.DataFrame(metrics),histories)
    ranked={}
    for horizon in HORIZONS:
        try:
            prior=store.previous_rankings(latest['run_at'] if latest else now,horizon)
        except (OSError,sqlite3.DatabaseError):
            prior={}
        ranked[horizon]=rank_opportunities(enriched,horizon,prior)
    return dict(universe=universe,metrics=enriched,histories=histories,opportunities=ranked,public_mode=public_mode,
                macro=macro_context(snapshots,now),core=core,latest_run=latest,
                errors=read_errors+(latest.get('errors',[]) if latest else []))
