"""Tests for the CWA weather code -> Home Assistant condition mapping.

Home Assistant is not required: the few modules the integration imports are
replaced by stubs. Run with: python3 -m unittest discover -s tests -v
"""
import importlib
import pathlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

COMPONENT = pathlib.Path(__file__).parent.parent / "custom_components" / "opencwb"

# https://developers.home-assistant.io/docs/core/entity/weather/#recommended-values-for-state-and-condition
HA_CONDITIONS = {
    "clear-night", "cloudy", "exceptional", "fog", "hail", "lightning",
    "lightning-rainy", "partlycloudy", "pouring", "rainy", "snowy",
    "snowy-rainy", "sunny", "windy", "windy-variant",
}


def _stub(name, **attrs):
    module = mock.MagicMock(name=name)
    module.configure_mock(**attrs)
    sys.modules[name] = module


def _load():
    """Import const.py and weather_update_coordinator.py without Home Assistant."""
    weather_attrs = {
        "ATTR_CONDITION_" + c.upper().replace("-", "_"): c for c in HA_CONDITIONS
    }
    for attr in ("condition", "is_daytime", "precipitation", "precipitation_probability",
                 "pressure", "temperature", "templow", "datetime", "wind_bearing",
                 "wind_speed"):
        weather_attrs["ATTR_FORECAST_" + attr.upper()] = attr
    weather_attrs["ATTR_FORECAST_TEMP"] = "temperature"
    weather_attrs["ATTR_FORECAST_TEMP_LOW"] = "templow"
    weather_attrs["ATTR_FORECAST_TIME"] = "datetime"

    _stub("async_timeout")
    _stub("homeassistant")
    _stub("homeassistant.components")
    _stub("homeassistant.components.sensor")
    _stub("homeassistant.components.weather", **weather_attrs)
    _stub("homeassistant.const")
    _stub("homeassistant.helpers")
    _stub("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=object)
    _stub("homeassistant.util")

    # Register the packages by hand so their __init__.py (which need Home
    # Assistant and the HTTP client dependencies) are not executed.
    for name, path in (
        ("custom_components", COMPONENT.parent),
        ("custom_components.opencwb", COMPONENT),
        ("custom_components.opencwb.core", COMPONENT / "core"),
    ):
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package

    return (
        importlib.import_module("custom_components.opencwb.const"),
        importlib.import_module("custom_components.opencwb.weather_update_coordinator"),
    )


const, coordinator = _load()
Coordinator = coordinator.WeatherUpdateCoordinator
TAIWAN = timezone(timedelta(hours=8))

# One representative description per code, from the official CWA table
# https://www.cwa.gov.tw/V8/C/K/Weather_Icon.html (code 40 is not defined).
EXPECTED = {
    1: "sunny",             # 晴天
    2: "partlycloudy",      # 晴時多雲
    3: "partlycloudy",      # 多雲時晴
    4: "partlycloudy",      # 多雲
    5: "cloudy",            # 多雲時陰
    6: "cloudy",            # 陰時多雲
    7: "cloudy",            # 陰天
    8: "rainy",             # 多雲短暫雨
    9: "rainy",             # 多雲時陰短暫雨
    10: "rainy",            # 陰時多雲短暫雨
    11: "rainy",            # 雨天
    12: "rainy",            # 多雲時陰有雨
    13: "rainy",            # 陰時多雲有雨
    14: "rainy",            # 陰有雨
    15: "lightning-rainy",  # 多雲陣雨或雷雨
    16: "lightning-rainy",  # 多雲時陰陣雨或雷雨
    17: "lightning-rainy",  # 陰時多雲有雷陣雨
    18: "lightning-rainy",  # 陰有陣雨或雷雨
    19: "rainy",            # 晴午後多雲局部雨
    20: "rainy",            # 多雲午後局部雨
    21: "lightning-rainy",  # 晴午後多雲陣雨或雷雨
    22: "lightning-rainy",  # 多雲午後局部陣雨或雷雨
    23: "snowy-rainy",      # 多雲局部陣雨或雪
    24: "fog",              # 晴有霧
    25: "fog",              # 晴時多雲有霧
    26: "fog",              # 多雲時晴有霧
    27: "fog",              # 多雲有霧
    28: "fog",              # 陰有霧
    29: "rainy",            # 多雲局部雨
    30: "rainy",            # 多雲時陰局部雨
    31: "rainy",            # 多雲有霧有局部雨
    32: "rainy",            # 多雲時陰有霧有局部雨
    33: "lightning-rainy",  # 多雲局部陣雨或雷雨
    34: "lightning-rainy",  # 多雲時陰局部陣雨或雷雨
    35: "lightning-rainy",  # 多雲有陣雨或雷雨有霧
    36: "lightning-rainy",  # 多雲時陰有陣雨或雷雨有霧
    37: "snowy-rainy",      # 多雲局部雨或雪有霧
    38: "rainy",            # 短暫陣雨有霧
    39: "rainy",            # 有雨有霧
    41: "lightning-rainy",  # 短暫陣雨或雷雨有霧
    42: "snowy",            # 下雪
}


def _timestamp(hour):
    return int(datetime(2026, 10, 12, hour, tzinfo=TAIWAN).timestamp())


class ConditionTest(unittest.TestCase):

    def test_every_code_maps_to_the_expected_condition(self):
        for code, condition in EXPECTED.items():
            with self.subTest(code=code):
                self.assertEqual(Coordinator._get_condition(code, True), condition)

    def test_table_is_consistent(self):
        codes = [c for v in const.CONDITION_CLASSES.values() for c in v]
        self.assertEqual(sorted(codes), sorted(EXPECTED), "missing or duplicated code")
        self.assertLessEqual(set(const.CONDITION_CLASSES), HA_CONDITIONS)

    def test_wind_is_never_derived_from_the_weather_code(self):
        self.assertNotIn("windy", const.CONDITION_CLASSES)
        self.assertNotIn("windy-variant", const.CONDITION_CLASSES)

    def test_only_clear_sky_differs_at_night(self):
        self.assertEqual(Coordinator._get_condition(1, False), "clear-night")
        for code, condition in EXPECTED.items():
            if code != 1:
                with self.subTest(code=code):
                    self.assertEqual(Coordinator._get_condition(code, False), condition)

    def test_unknown_code_does_not_raise(self):
        for code in (0, 40, 43, None):
            with self.subTest(code=code):
                self.assertIsNone(Coordinator._get_condition(code, True))

    def test_is_daytime(self):
        self.assertEqual(
            [Coordinator._is_daytime(_timestamp(h)) for h in (0, 5, 6, 12, 17, 18, 23)],
            [False, False, True, True, True, False, False])


class WindBearingTest(unittest.TestCase):

    def test_text_is_converted_to_degrees(self):
        self.assertEqual(Coordinator._get_wind_bearing("偏東風"), 90)
        self.assertEqual(Coordinator._get_wind_bearing("東北風"), 45)
        self.assertEqual(sorted(const.WIND_BEARINGS.values()), list(range(0, 360, 45)))

    def test_unknown_value_is_kept(self):
        self.assertEqual(Coordinator._get_wind_bearing("靜風"), "靜風")
        self.assertIsNone(Coordinator._get_wind_bearing(None))


class ForecastTest(unittest.TestCase):
    """The case reported for 文山區: 晴時多雲 (code 2) with a light breeze."""

    @staticmethod
    def _convert(hour, weather_code):
        entry = mock.MagicMock(weather_code=weather_code, precipitation_probability=0.1)
        entry.reference_time.return_value = _timestamp(hour)
        entry.wind.return_value = {"speed": 4, "deg": "偏東風", "gust": 3}
        entry.temperature.return_value = {"temp_max": 23, "temp_min": 21}
        return Coordinator._convert_forecast(object.__new__(Coordinator), entry)

    def test_mostly_clear_with_light_wind_is_not_windy(self):
        forecast = self._convert(6, 2)
        self.assertEqual(forecast["condition"], "partlycloudy")
        self.assertEqual(forecast["wind_bearing"], 90)
        self.assertEqual(forecast["wind_speed"], 4)
        self.assertIs(forecast["is_daytime"], True)

    def test_night_period(self):
        forecast = self._convert(18, 1)
        self.assertEqual(forecast["condition"], "clear-night")
        self.assertIs(forecast["is_daytime"], False)


if __name__ == "__main__":
    unittest.main()
