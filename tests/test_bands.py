import pytest

from psi_bot.bands import european_aqi_band, pm25_band, psi_band


@pytest.mark.parametrize(
    ("value", "descriptor"),
    [
        (0, "Good"),
        (50, "Good"),
        (51, "Moderate"),
        (100, "Moderate"),
        (101, "Unhealthy"),
        (200, "Unhealthy"),
        (201, "Very Unhealthy"),
        (300, "Very Unhealthy"),
        (301, "Hazardous"),
    ],
)
def test_psi_band_boundaries(value: int, descriptor: str) -> None:
    assert psi_band(value).descriptor == descriptor


@pytest.mark.parametrize(
    ("value", "number", "descriptor"),
    [
        (0, 1, "Normal"),
        (55, 1, "Normal"),
        (56, 2, "Elevated"),
        (150, 2, "Elevated"),
        (151, 3, "High"),
        (250, 3, "High"),
        (251, 4, "Very High"),
    ],
)
def test_pm25_band_boundaries(value: int, number: int, descriptor: str) -> None:
    band = pm25_band(value)
    assert band.number == number
    assert band.descriptor == descriptor


@pytest.mark.parametrize(
    ("value", "descriptor"),
    [
        (0, "Good"),
        (20, "Good"),
        (20.1, "Fair"),
        (40, "Fair"),
        (40.1, "Moderate"),
        (60, "Moderate"),
        (60.1, "Poor"),
        (80, "Poor"),
        (80.1, "Very poor"),
        (100, "Very poor"),
        (100.1, "Extremely poor"),
    ],
)
def test_european_aqi_band_boundaries(value: float, descriptor: str) -> None:
    assert european_aqi_band(value).descriptor == descriptor


@pytest.mark.parametrize("classifier", [psi_band, pm25_band, european_aqi_band])
def test_negative_readings_are_rejected(classifier: object) -> None:
    with pytest.raises(ValueError):
        classifier(-1)  # type: ignore[operator]
