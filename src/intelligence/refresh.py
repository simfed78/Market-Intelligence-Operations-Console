"""Explicit source refresh; never invoked by rendering a dashboard or by Core.

python -m src.intelligence.refresh --root .
python -m src.intelligence.refresh --root . --import-inbox data/intelligence_inbox
"""
from pathlib import Path
import argparse
import csv
import os
from io import StringIO
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import re
import time
from threading import Lock
from datetime import datetime, timezone
from .market import chart_url, utc_now, normalize
from .store import Store
from .universe import load_universe
from .macro import SERIES, macro_context
from .service import load_dashboard
from .analytics import clean_records
from .opportunities import HORIZONS, rank_opportunities

FRED_TIMEOUT_SECONDS = 8
FRED_API_TIMEOUT_SECONDS = 12
FRED_CIRCUIT_FAILURES = 2
# FRED is published at daily/monthly/weekly cadence, unlike price bars.
MACRO_CACHE_HOURS = 26


class FredCircuitOpen(RuntimeError):
    """Skip further public FRED requests after repeated connectivity failures."""


def _fred_api_payload(code, key):
    """Optional official FRED API JSON -> original two-column CSV snapshot contract."""
    params = urlencode({"series_id": code, "observation_start": "2023-01-01",
                        "file_type": "json", "api_key": key})
    req = Request("https://api.stlouisfed.org/fred/series/observations?" + params,
                  headers={"User-Agent": "TradingDesk-Research/1.0"})
    with urlopen(req, timeout=FRED_API_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    rows = data.get("observations") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("Official FRED API returned no observations")
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["observation_date", code])
    valid = 0
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("Invalid FRED response item")
        date, value = item.get("date"), item.get("value")
        if not isinstance(date, str) or not isinstance(value, str):
            raise ValueError("Invalid FRED observation")
        if value != ".":
            try:
                number = float(value)
            except ValueError as exc:
                raise ValueError("Invalid FRED numeric value") from exc
            if not -float("inf") < number < float("inf"):
                raise ValueError("Nonfinite FRED numeric value")
            valid += 1
        writer.writerow([date, value])
    if not valid:
        raise ValueError("No numeric observations in FRED response")
    # Never persist or display a URL containing the API key.
    safe_url = ("https://api.stlouisfed.org/fred/series/observations?"
                + urlencode({"series_id": code, "observation_start": "2023-01-01",
                             "file_type": "json"}))
    return buffer.getvalue(), safe_url


def _fred_connectivity_failure(exc):
    return isinstance(exc, (TimeoutError, URLError)) or (
        isinstance(exc, HTTPError) and exc.code in (429, 502, 503, 504)
    )


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
    macro = symbol.startswith('FRED:')
    code = symbol.removeprefix('FRED:') if macro else None
    # API key is optional for scheduled ingestion; not required by Streamlit.
    key = os.getenv("FRED_API_KEY", "").strip() if macro else ""
    if macro and key:
        payload, url = _fred_api_payload(code, key)
    else:
        url = (f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}&cosd=2023-01-01'
               if macro else chart_url(symbol))
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (MultiAssetResearch/1.0)'})
        with urlopen(req, timeout=FRED_TIMEOUT_SECONDS if macro else 20) as response:
            payload = response.read().decode('utf-8')
    if macro and not payload.startswith(f"observation_date,{code}\n"):
        raise ValueError("FRED response does not match its series CSV schema")
    return dict(symbol=symbol, retrieved_at=utc_now(),
                source='FRED' if macro else 'Yahoo Finance',
                source_url=url, kind='macro' if macro else 'market',
                sha256=hashlib.sha256(payload.encode()).hexdigest(), payload=payload)


def source_error(symbol, exc):
    detail=str(getattr(exc,'reason',exc))[:200]
    detail=re.sub(r'(api_key|token|password|authorization)=([^&\s]+)',r'\1=[redacted]',detail,flags=re.I)
    out={'symbol':symbol,'error':type(exc).__name__,'detail':detail}
    if isinstance(exc,HTTPError):
        out['http_status']=exc.code
        if exc.code==429:out['detail']='Limite richieste della fonte raggiunto; nessuna sostituzione dei dati.'
        value=exc.headers.get('Retry-After') if exc.headers else None
        if value and value.isdigit():out['retry_after_seconds']=int(value)
    return out


def cache_usable(record, now):
    try:
        age=(now-datetime.fromisoformat(record['retrieved_at'].replace('Z','+00:00'))).total_seconds()
        if age<0:return False
        if hashlib.sha256(record['payload'].encode()).hexdigest()!=record['sha256']:return False
        if record['kind']=='market':
            return age<=6*3600 and normalize(record,record['symbol'],as_of=now.isoformat())[1]['price_status']=='VALID'
        if record['kind']!='macro' or record['source']!='FRED' or age>MACRO_CACHE_HOURS*3600:
            return False
        observations=macro_context({record['symbol']:record},as_of=now.isoformat())['observations']
        selected=observations[observations.series.eq(record['symbol'].removeprefix('FRED:'))]
        return bool(not selected.empty and selected.value.notna().all() and selected.stale.eq(False).all())
    except (KeyError,ValueError,TypeError):return False


def refresh_sources(root: Path, inbox: Path | None = None, *, progress=None, use_cached=False, request_interval=0, budget_seconds=None):
    root=Path(root).resolve();store=Store(root)
    allowed=set(load_universe(root).symbol)|{'FRED:'+s for s in SERIES}
    run_at=utc_now(); errors=[]; success=[]; cached=[]
    done=0;total=len(allowed)
    def report(symbol):
        nonlocal done
        done+=1
        if progress:progress({'completed':done,'total':total,'acquired':len(success),'cached':len(cached),'errors':len(errors),'symbol':symbol})
    if inbox:
        for file in sorted(inbox.glob('*.json')):
            if file.name=='acquisition_log.json': continue
            try:
                record=json.loads(file.read_text())
                import_record(store,record,allowed); success.append(record['symbol'])
            except (OSError,ValueError,KeyError,TypeError) as exc:
                errors.append(source_error(file.name,exc))
    else:
        snapshots=store.latest_snapshots() if use_cached else {}
        now=datetime.now(timezone.utc)
        pending=[]
        for symbol in sorted(allowed):
            if symbol in snapshots and cache_usable(snapshots[symbol],now):
                cached.append(symbol);report(symbol)
            else:pending.append(symbol)
        throttle = Lock()
        next_request = [0.0]
        network_started = time.monotonic()
        fred_failures = [0]

        def fetch_paced(symbol):
            if (symbol.startswith("FRED:") and fred_failures[0] >= FRED_CIRCUIT_FAILURES):
                raise FredCircuitOpen("FRED temporaneamente non disponibile; uso ultimo snapshot verificato.")
            if budget_seconds is not None and time.monotonic()-network_started>=budget_seconds:
                raise TimeoutError('Tempo massimo aggiornamento raggiunto; fonte non richiesta in questo run')
            if request_interval:
                with throttle:
                    pause=max(0,next_request[0]-time.monotonic())
                    if pause:time.sleep(pause)
                    next_request[0]=time.monotonic()+request_interval
            if budget_seconds is not None and time.monotonic()-network_started>=budget_seconds:
                raise TimeoutError('Tempo massimo aggiornamento raggiunto; fonte non richiesta in questo run')
            return fetch_record(symbol)

        # Market quotations first; optional macro requests cannot starve 145 assets.
        # FRED calls are sequential so the fail-fast circuit can stop a provider outage.
        for group, workers in (([s for s in pending if not s.startswith("FRED:")],3),
                               ([s for s in pending if s.startswith("FRED:")],1)):
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures={pool.submit(fetch_paced,symbol):symbol for symbol in group}
                for future in as_completed(futures):
                    symbol=futures[future]
                    try:
                        record=future.result()
                        import_record(store,record,allowed)
                        success.append(symbol)
                    except Exception as exc:
                        if symbol.startswith("FRED:") and _fred_connectivity_failure(exc):
                            fred_failures[0] += 1
                        errors.append(source_error(symbol,exc))
                    report(symbol)
    data=load_dashboard(root,include_unpublished=True)
    counts=data['metrics'].price_status.value_counts().to_dict()
    summary=dict(mode='RESEARCH_ONLY',requested=len(allowed),acquired=len(success),cached=len(cached),errors=errors,
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
    parser.add_argument('--request-interval',type=float,default=0.0,
                        help='Minimum seconds between provider requests (CI pacing).')
    parser.add_argument('--budget-seconds',type=float,default=None,
                        help='Maximum time budget for submitting provider requests.')
    args=parser.parse_args()
    if args.request_interval < 0 or (args.budget_seconds is not None and args.budget_seconds <= 0):
        parser.error('Request interval must be nonnegative and budget seconds must be positive.')
    result=refresh_sources(args.root,args.import_inbox,request_interval=args.request_interval,
                           budget_seconds=args.budget_seconds)
    print(json.dumps(result,indent=2))
    return 0 if result['acquired'] else 1


if __name__=='__main__':
    raise SystemExit(main())
