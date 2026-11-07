"""Shared public acquisition state. Busy is not a provider outage; no broker reads."""
from threading import Lock, Thread
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from .refresh import refresh_sources, source_error

_LOCK=Lock()
_STATE_LOCK=Lock()
_STATE={}


def public_status(root):
    with _STATE_LOCK:
        if _STATE.get('root')!=str(Path(root).resolve()):return {'status':'IDLE'}
        return deepcopy(_STATE)


def _progress(update):
    with _STATE_LOCK:_STATE.update(update)


def _work(root):
    try:
        result=refresh_sources(root,use_cached=True,request_interval=.35,budget_seconds=120,progress=_progress)
        _progress({'status':'COMPLETE','result':result})
        return result
    except Exception as exc:
        result={'acquired':0,'cached':0,'errors':[source_error('refresh',exc)]}
        _progress({'status':'FAILED','result':result})
        return result
    finally:
        _LOCK.release()


def _begin(root, force=False):
    global _STATE
    old=public_status(root)
    if old.get('status')=='RUNNING':return old,False
    if not force and old.get('status') in ('COMPLETE','FAILED'):return old,False
    if not _LOCK.acquire(blocking=False):return {'status':'RUNNING'},False
    with _STATE_LOCK:
        _STATE={'root':str(Path(root).resolve()),'status':'RUNNING','job_id':uuid4().hex,
                'completed':0,'total':153,'acquired':0,'cached':0,'errors':0}
    return public_status(root),True


def start_public_refresh(root, *, force=False):
    state,created=_begin(root,force)
    if created:Thread(target=_work,args=(root,),daemon=True,name='public-market-refresh').start()
    return state


def refresh_public(root):
    """Synchronous compatibility wrapper; UI uses the nonblocking starter."""
    state,created=_begin(root,force=True)
    return _work(root) if created else state
