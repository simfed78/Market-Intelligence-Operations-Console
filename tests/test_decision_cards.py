"""All prices below are synthetic test fixtures, never dashboard data."""
import pytest
from src.intelligence.decision_cards import decision_summary


def sample(**changes):
    return dict(price_status='VALID', signal_state='RESEARCH CANDIDATE',
                price=120, sma50=110, sma200=100, resistance20=119,
                support20=95, ret_21=.05, ret_63=.06, volume_status='MISSING',
                **changes)


def test_descriptive_trend_momentum_and_levels():
    result = decision_summary(sample())
    assert result['trend'] == 'Rialzista'
    assert result['momentum'] == 'In miglioramento'
    assert result['extension'] == pytest.approx(9.090909)
    assert 'già osservata' in result['confirmation']
    assert 'non validato' in result['confirmation']
    assert '95.00' in result['invalidation']
    assert result['volume'].startswith('MISSING')


@pytest.mark.parametrize('quality', ['DEGRADED', 'MISSING', 'SYNTHETIC'])
def test_nonvalid_data_cannot_generate_level_interpretations(quality):
    row = sample(); row['price_status'] = quality
    result = decision_summary(row)
    assert result['trend'] == 'Non disponibile'
    assert result['extension'] is None
    assert '119' not in result['confirmation']


def test_missing_factors_never_become_neutral_or_confirmed():
    row = sample(); row.update(sma50=None, sma200=float('nan'), ret_21=None,
                               support20=None, resistance20=None)
    result = decision_summary(row)
    assert result['momentum'] == result['trend'] == 'Non disponibile'
    assert result['extension'] is None
    assert result['invalidation'].startswith('Non determinabile')


def test_declining_trend_and_volume_are_not_net_flows():
    row = sample(); row.update(price=90, ret_21=-.08, volume_status='VALID',
                               rvol_20=2, volume_z60=3, volume_signal='Volume anomalo')
    result = decision_summary(row)
    assert result['trend'] == 'Ribassista'
    assert result['momentum'] == 'In rallentamento'
    assert 'attendere' in result['confirmation']
    assert 'non misura flussi netti' in result['volume']
