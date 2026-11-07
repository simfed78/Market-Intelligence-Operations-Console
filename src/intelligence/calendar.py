"""Bounded NYSE/NYSE Arca regular-session calendar for the MVP US-listed proxies.

Official schedules: https://www.nyse.com/markets/hours-calendars
Extra 2025-01-09 closure: Carter national day of mourning.
Scope intentionally 2024–2027. Unknown years/venues fail closed for ranking.
Early closes remain sessions; this does not qualify execution timestamps.
"""
from datetime import date, timedelta
from dateutil.easter import easter
import pandas as pd


def nth_weekday(year,month,weekday,n):
    d=date(year,month,1)
    return d+timedelta(days=(weekday-d.weekday())%7+7*(n-1))


def observed(d):
    return d-timedelta(days=1) if d.weekday()==5 else d+timedelta(days=1) if d.weekday()==6 else d


def nyse_sessions(start,end):
    start=pd.Timestamp(start);end=pd.Timestamp(end)
    if start.year<2024 or end.year>2027:
        return None
    holidays=set()
    for y in range(start.year,end.year+1):
        newyear=date(y,1,1)
        if newyear.weekday()==6:newyear+=timedelta(days=1)
        holidays.update([newyear,nth_weekday(y,1,0,3),nth_weekday(y,2,0,3),easter(y)-timedelta(days=2),
                         max(date(y,5,d) for d in range(25,32) if date(y,5,d).weekday()==0),
                         observed(date(y,6,19)),observed(date(y,7,4)),nth_weekday(y,9,0,1),
                         nth_weekday(y,11,3,4),observed(date(y,12,25))])
    holidays.add(date(2025,1,9))
    return pd.DatetimeIndex([d for d in pd.bdate_range(start,end) if d.date() not in holidays])
