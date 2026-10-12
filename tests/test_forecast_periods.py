"""The forecast list starts with the period that is in progress.

CWA's township forecast lists the current 12-hour period first. Dropping it
left the daily forecast without an entry for today until the evening.
Run with: python3 -m unittest discover -s tests -v
"""
import importlib.util
import pathlib
import unittest

PATH = (pathlib.Path(__file__).parent.parent / "custom_components" / "opencwb"
        / "core" / "utils" / "opendata_cwb.py")
spec = importlib.util.spec_from_file_location("opendata_cwb", PATH)
opendata_cwb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opendata_cwb)

STARTS = ["2026-10-12T06:00:00+08:00", "2026-10-12T18:00:00+08:00", "2026-10-13T06:00:00+08:00"]


def _element(name, key, values, extra=None):
    return {
        "ElementName": name,
        "Time": [
            {"StartTime": start, "ElementValue": [{key: value, **(extra or {})}]}
            for start, value in zip(STARTS, values)
        ],
    }


def _response(description):
    return {"records": {"Locations": [{
        "DatasetDescription": description,
        "Location": [{
            "Latitude": "24.99", "Longitude": "121.57",
            "WeatherElement": [
                _element("最高溫度", "MaxTemperature", ["30", "24", "29"]),
                _element("最低溫度", "MinTemperature", ["24", "19", "19"]),
                _element("天氣現象", "Weather", ["晴時多雲"] * 3, {"WeatherCode": "02"}),
            ],
        }],
    }]}}


class ForecastPeriodsTest(unittest.TestCase):
    def test_daily_forecast_includes_current_period(self):
        value = opendata_cwb.OpendataCWB.to_dict(_response("臺灣各縣市鄉鎮未來1週天氣預報"))
        daily = value["daily"]
        self.assertEqual(len(daily), 3)
        self.assertEqual(daily[0]["dt"], value["current"]["dt"])
        self.assertEqual(
            [(d["main"]["temp_min"], d["main"]["temp_max"]) for d in daily],
            [(24, 30), (19, 24), (19, 29)],
        )

    def test_hourly_forecast_includes_current_period(self):
        value = opendata_cwb.OpendataCWB.to_dict(_response("臺灣各縣市鄉鎮未來3天天氣預報"))
        self.assertEqual(len(value["hourly"]), 3)


if __name__ == "__main__":
    unittest.main()
