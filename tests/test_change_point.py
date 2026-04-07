import numpy as np
import pandas as pd

from src.models.change_point import detect_change_points


def test_detect_change_points_flags_shift():
    idx = pd.bdate_range("2024-01-01", periods=120)
    values = np.concatenate([np.ones(60) * 0.2, np.ones(60) * -0.3])
    series = pd.Series(values, index=idx)
    result = detect_change_points(series)
    assert isinstance(result.structural_break_flag, bool)
    assert isinstance(result.recent_break_dates, list)
