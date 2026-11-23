"""Bounded non-secret macro source diagnostics (CI only, never trades or posts data)."""
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from src.intelligence.fred_md import parse_fred_md
import json

today=datetime.now(timezone.utc).isoformat()
checks=[
    ("FRED-MD current web", "https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/research/fred-md/monthly/current.csv","md"),
    ("FRED-MD 2026-10 web", "https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/research/fred-md/monthly/2026-10.csv","md"),
    ("FRED-MD 2026-10 files", "https://files.stlouisfed.org/files/htdocs/fred-md/monthly/2026-10.csv","md"),
    ("DBnomics CPI", "https://api.db.nomics.world/v22/series/FRED/CPIAUCSL?observations=1","json"),
    ("DBnomics IP", "https://api.db.nomics.world/v22/series/FRED/INDPRO?observations=1","json"),
    ("BLS CPI v1", "https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0","json"),
]
for name,url,kind in checks:
    try:
        request=Request(url,headers={"User-Agent":"Mozilla/5.0 (TradingDesk-Research/1.0)"})
        with urlopen(request,timeout=8) as response:
            data=response.read(5_000_001)
            status=response.status
        if len(data)>5_000_000:
            raise ValueError("Provider response exceeds safe cap")
        if kind=="md":
            records=parse_fred_md(data.decode("utf-8-sig"),acquired_at=today,source_url=url)
            observed={key:record["payload"].splitlines()[-1].split(",")[0] for key,record in records.items()}
            print(name,"HTTP",status,"last_observations",observed,flush=True)
        else:
            doc=json.loads(data)
            if name.startswith("DBnomics"):
                print(name,"HTTP",status,"top_keys",list(doc)[:8],
                      "series",str(doc.get("series",{}))[:380],flush=True)
            else:
                print(name,"HTTP",status,"status",doc.get("status"),
                      "results",str(doc.get("Results",{}))[:380],flush=True)
    except Exception as exc:
        print(name,"FAILED",type(exc).__name__,str(exc)[:180],flush=True)
