import numpy as np
import pandas as pd

from src.data.data_quality import DataQualityChecker


def test_data_quality_report_builds():
    idx = pd.bdate_range(end=pd.Timestamp.today(), periods=30)
    frame = pd.DataFrame({"SPY": np.arange(30)}, index=idx)
    report = DataQualityChecker(stale_days_threshold=5).evaluate({"prices": frame}, {"market_data": False})
    assert "prices" in report.data_health_report
    assert "market_data" in report.fallback_usage_flags
