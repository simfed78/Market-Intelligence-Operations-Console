"""Allowlisted artifact reader. No Core imports, broker calls, or writes."""
from pathlib import Path
import json
from .market import utc_now

ALLOWLIST={
 'quality':'datasets/spy_full_v2/quality_checks.json',
 'manifest':'datasets/spy_full_v2/manifest.json',
 'failure':'backtests/spy_trend_v1_blocked/qualification_failure.json',
 'verification':'logs/spy_final_verification.json',
 'demo':'data/demo_update/cross_snapshot.json',
 'audit':'data/analysis/audit_results.json',
}


def read_core(root):
    root=Path(root).expanduser().resolve()
    docs={}; errors=[]; mtimes=[]
    for key,relative in ALLOWLIST.items():
        target=(root/relative).resolve()
        # Refuse symlinks escaping the authorized artifact root.
        if not target.is_relative_to(root):
            errors.append(key+': path fuori root'); continue
        try:
            value=json.loads(target.read_text())
            if not isinstance(value,dict): raise ValueError('schema')
            docs[key]=value
            mtimes.append(target.stat().st_mtime)
        except (OSError,ValueError):
            errors.append(key+': MISSING o schema non leggibile')
    q=docs.get('quality',{}); f=docs.get('failure',{}); v=docs.get('verification',{})
    d=docs.get('demo',{}); a=docs.get('audit',{})
    qualification=docs.get('manifest',{}).get('qualification_status')
    # Explicit exact booleans only; never turn a missing key into a successful gate.
    core=dict(schema_version=1,mode='RESEARCH_ONLY',loaded_at=utc_now(),core_observed_at=None,
      phase1_gate='OPEN' if v.get('phase1_gate_passed') is False else 'MISSING',
      phase2_gate='BLOCKED' if qualification=='BLOCKED' or f.get('status')=='BLOCKED' else 'MISSING',
      market_performance_computed=f.get('market_performance_computed'),
      dataset=dict(symbol='SPY',status='DEGRADED' if qualification=='BLOCKED' else 'MISSING',
                   qualification=qualification or 'MISSING', rows=q.get('rows'),
                   missing_volume=(sum(e.get('error')=='missing_volume' for e in q['errors'] if isinstance(e,dict)) if isinstance(q.get('errors'),list) else None),
                   blockers=q.get('blockers') if isinstance(q.get('blockers'),list) else []),
      backtest=dict(status=f.get('status','MISSING'),certified_market_results=False,
                    phase2_complete=f.get('phase2_complete'),reason=f.get('reason')),
      demo=dict(mode='DEMO_READ_ONLY',snapshot_at=d.get('broker_timestamp'),
                reconciliation=a.get('status','MISSING'),reconciliation_snapshot_at=a.get('accountSnapshot'),
                pending_orders=d.get('current_order_count'),cross_snapshot_passed=d.get('passed'),
                note='Snapshot separati; nessun aggiornamento del broker e nessuna certificazione contabile.'),
      tests=dict(raw_hash_valid=v.get('raw_hash_valid'),quarantine_hash_valid=v.get('quarantine_hash_valid'),
                 blocked_repeat_byte_identical=v.get('blocked_repeat_byte_identical'),
                 production_ready=v.get('production_ready'),
                 note='Controlli registrati negli artifact Core; la suite corrente è documentata nel report Phase 2B.'),
      status='DEGRADED' if docs else 'MISSING',reason='; '.join(errors))
    # Source observations, not filesystem mtime presented as market availability.
    core['core_observed_at']=d.get('broker_timestamp')
    return core
