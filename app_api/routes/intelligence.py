"""Versioned research contract, separate from historical legacy endpoints."""
from fastapi import APIRouter
from src.intelligence.service import load_dashboard
from src.intelligence.analytics import clean_records


def build_intelligence_router(root):
    router=APIRouter(prefix='/research/v1')

    @router.get('/state')
    def state():
        data=load_dashboard(root)
        macro=data['macro'].copy()
        macro['observations']=clean_records(macro['observations'])
        return dict(schema_version=1,mode='RESEARCH_ONLY',universe=clean_records(data['universe']),
                    metrics=clean_records(data['metrics']),opportunities={h:clean_records(f) for h,f in data['opportunities'].items()},macro=macro,core=data['core'],latest_run=data['latest_run'],errors=data['errors'])

    return router
