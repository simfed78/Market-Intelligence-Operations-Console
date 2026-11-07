"""Hosted load, publication and diagnostics tests; no real network traffic."""
from threading import Event
from pathlib import Path
from urllib.error import HTTPError, URLError
from email.message import Message
from datetime import datetime,timezone
import hashlib
import shutil
import time
import pytest
from src.intelligence import hosted
from src.intelligence.refresh import source_error,cache_usable
from src.intelligence.service import load_dashboard
from src.intelligence.store import Store


def test_duplicate_start_is_running_not_outage(tmp_path,monkeypatch):
    started=Event();release=Event();calls=[]
    def refresh(root,**kw):
        calls.append(root);kw['progress']({'completed':44,'total':153})
        started.set();assert release.wait(2)
        return {'acquired':44,'cached':0,'errors':[]}
    monkeypatch.setattr(hosted,'refresh_sources',refresh)
    try:
        first=hosted.start_public_refresh(tmp_path)
        assert started.wait(1)
        second=hosted.start_public_refresh(tmp_path)
        assert second['status']=='RUNNING' and second['job_id']==first['job_id']
        assert second['completed']==44 and len(calls)==1
    finally:release.set()
    for _ in range(100):
        if hosted.public_status(tmp_path)['status']=='COMPLETE':break
        time.sleep(.01)
    assert hosted.public_status(tmp_path)['status']=='COMPLETE'


def test_failure_is_diagnostic_and_not_retried_by_render(tmp_path,monkeypatch):
    calls=[]
    def bad(root,**kwargs):calls.append(root);raise OSError('declared test failure')
    monkeypatch.setattr(hosted,'refresh_sources',bad)
    result=hosted.refresh_public(tmp_path)
    assert result['errors'][0]['error']=='OSError'
    state=hosted.start_public_refresh(tmp_path)
    assert state['status']=='FAILED' and len(calls)==1


def test_http_diagnostics_preserve_status_not_credentials():
    headers=Message();headers['Retry-After']='60'
    error=source_error('SPY',HTTPError('https://example.test',429,'Too Many Requests',headers,None))
    assert error['http_status']==429 and error['retry_after_seconds']==60
    assert 'Limite richieste' in error['detail']
    error=source_error('FRED:CPI',URLError('token=declared-private-value&connection=failed'))
    assert 'declared-private-value' not in error['detail'] and 'redacted' in error['detail']


def test_cold_start_never_exposes_unpublished_partial_data(tmp_path,monkeypatch):
    (tmp_path/'config').mkdir();shutil.copy(Path(__file__).parents[1]/'config/research_universe.json',tmp_path/'config')
    monkeypatch.setenv('TRADING_DESK_PUBLIC','1')
    def forbidden(*args,**kwargs):pytest.fail('Partial snapshots must remain unpublished')
    monkeypatch.setattr(Store,'latest_snapshots',forbidden)
    result=load_dashboard(tmp_path)
    assert result['metrics'].price_status.eq('MISSING').all()
    assert result['opportunities']['3m'].signal_state.eq('BLOCKED').all()


def test_macro_cache_requires_original_hash_and_six_hour_freshness():
    now=datetime(2026,11,7,12,tzinfo=timezone.utc)
    payload='observation_date,CPIAUCSL\n2026-08-01,99\n2026-09-01,100\n'
    r=dict(kind='macro',source='FRED',symbol='FRED:CPIAUCSL',retrieved_at='2026-11-07T10:00:00Z',payload=payload,sha256=hashlib.sha256(payload.encode()).hexdigest())
    assert cache_usable(r,now)
    assert not cache_usable({**r,'sha256':'broken'},now)
    assert not cache_usable({**r,'retrieved_at':'2026-11-07T01:00:00Z'},now)


def test_exhausted_public_budget_does_not_start_more_network_requests(tmp_path,monkeypatch):
    from src.intelligence import refresh
    (tmp_path/'config').mkdir();shutil.copy(Path(__file__).parents[1]/'config/research_universe.json',tmp_path/'config')
    monkeypatch.setenv('TRADING_DESK_PUBLIC','1')
    monkeypatch.setattr(refresh,'fetch_record',lambda symbol:pytest.fail('No source request after exhausted budget'))
    result=refresh.refresh_sources(tmp_path,budget_seconds=0)
    assert len(result['errors'])==153 and result['acquired']==0
    assert all(e['error']=='TimeoutError' for e in result['errors'])
