"""Explicit source refresh; never invoked by rendering a dashboard or by Core.

python -m src.intelligence.refresh --root .
python -m src.intelligence.refresh --root . --import-inbox data/intelligence_inbox
"""
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from urllib.request import Request, urlopen
from .market import chart_url, utc_now, normalize
from .store import Store
from .universe import load_universe
from .macro import SERIES
from .service import load_dashboard
from .analytics import clean_records
from .opportunities import HORIZONS, rank_opportunities


def import_record(store, record, allowed):
    symbol=record.get('symbol')
    if symbol not in allowed:
        raise ValueError('Snapshot fuori universo')
    kind='macro' if symbol.startswith('FRED:') else 'market'
    source='FRED' if kind=='macro' else 'Yahoo Finance'
    if record.get('kind')!=kind or record.get('source')!=source:
        raise ValueError('Fonte/tipo non ammessi')
    if hashlib.sha256(record['payload'].encode()).hexdigest()!=record['sha256']:
        raise ValueError('Hash non corrispondente')
    if kind=='market':
        f,meta=normalize(record,symbol)
        if f.empty: raise ValueError('Nessuna barra OHLC interpretabile')
    else:
        if not record['payload'].startswith('observation_date,'):
            raise ValueError('FRED non CSV')
    store.put_snapshot(**{k:record[k] for k in ['symbol','retrieved_at','source','source_url','kind','sha256','payload']})


def fetch_record(symbol):
    macro=symbol.startswith('FRED:')
    url=(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={symbol[5:]}&cosd=2023-01-01' if macro else chart_url(symbol))
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (MultiAssetResearch/1.0)'})
    with urlopen(req,timeout=20) as response:
        payload=response.read().decode('utf-8')
    return dict(symbol=symbol,retrieved_at=utc_now(),source='FRED' if macro else 'Yahoo Finance',
                source_url=url,kind='macro' if macro else 'market',
                sha256=hashlib.sha256(payload.encode()).hexdigest(),payload=payload)


def refresh_sources(root: Path, inbox: Path | None = None):
    root=Path(root).resolve();store=Store(root)
    allowed=set(load_universe(root).symbol)|{'FRED:'+s for s in SERIES}
    run_at=utc_now(); errors=[]; success=[]
    if inbox:
        for file in sorted(inbox.glob('*.json')):
            if file.name=='acquisition_log.json': continue
            try:
                record=json.loads(file.read_text())
                import_record(store,record,allowed); success.append(record['symbol'])
            except (OSError,ValueError,KeyError,TypeError) as exc:
                errors.append(dict(file=file.name,error=type(exc).__name__))
    else:
        # Small bounded concurrency; failed requests never overwrite a good snapshot.
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(fetch_record,s):s for s in sorted(allowed)}
            for future in as_completed(futures):
                symbol=futures[future]
                try:
                    import_record(store,future.result(),allowed); success.append(symbol)
                except Exception as exc:
                    errors.append(dict(symbol=symbol,error=type(exc).__name__))
    data=load_dashboard(root,include_unpublished=True)
    counts=data['metrics'].price_status.value_counts().to_dict()
    summary=dict(mode='RESEARCH_ONLY',requested=len(allowed),acquired=len(success),errors=errors,
                 market_quality=counts,macro_status=data['macro']['status'],
                 note='Research input checks only; not Core qualification. No broker access.')
    completed_at=utc_now()
    summary['started_at']=run_at
    summary['completed_at']=completed_at
    store.save_run(completed_at,summary,clean_records(data['metrics']))
    for horizon in HORIZONS:
        ranked=rank_opportunities(data['metrics'],horizon)
        store.save_rankings(completed_at,horizon,clean_records(ranked))
    return dict(run_at=completed_at,**summary)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--import-inbox',type=Path)
    args=parser.parse_args()
    result=refresh_sources(args.root,args.import_inbox)
    print(json.dumps(result,indent=2))
    return 0 if result['acquired'] else 1


if __name__=='__main__':
    raise SystemExit(main())
