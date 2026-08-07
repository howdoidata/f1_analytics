from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from f1_analytics.data_sources.jolpica import fetch_json
from f1_analytics.data_sources.jolpica_loader import (
    cache_path,
    count_payload_items,
    discover_season_rounds,
    fetch_and_cache,
    merge_payload_pages,
    parse_laps,
    parse_results,
)


def make_timing(driver_id: str, position: int) -> dict:
    return {"driverId": driver_id, "position": str(position), "time": "1:30.000"}


def make_laps_page(
    laps: list[tuple[str, list[dict]]],
    *,
    offset: int,
    total: int,
    limit: int = 100,
) -> dict:
    """One `laps` offset page, shaped like a real Jolpica response.

    `limit` deliberately reports the server-enforced page size (100), which is what
    the loader must read back rather than trusting whatever it requested.
    """
    return {
        "MRData": {
            "limit": str(limit),
            "offset": str(offset),
            "total": str(total),
            "RaceTable": {
                "season": "2026",
                "round": "1",
                "Races": [
                    {
                        "season": "2026",
                        "round": "1",
                        "raceName": "Australian Grand Prix",
                        "Laps": [{"number": number, "Timings": timings} for number, timings in laps],
                    }
                ],
            },
        }
    }


class JolpicaLoaderTests(unittest.TestCase):
    def test_parse_results_preserves_fastest_lap_lap_rank_and_time(self) -> None:
        payload = {
            "MRData": {
                "RaceTable": {
                    "Races": [
                        {
                            "raceName": "Australian Grand Prix",
                            "date": "2026-03-08",
                            "Results": [
                                {
                                    "Driver": {"driverId": "sainz", "code": "SAI"},
                                    "Constructor": {"constructorId": "williams"},
                                    "grid": "10",
                                    "position": "8",
                                    "positionText": "8",
                                    "points": "4",
                                    "laps": "57",
                                    "status": "Finished",
                                    "Time": {"time": "+20.000"},
                                    "FastestLap": {
                                        "rank": "9",
                                        "lap": "54",
                                        "Time": {"time": "1:23.590"},
                                    },
                                }
                            ],
                        }
                    ]
                }
            }
        }

        frame = parse_results(payload, season=2026, round_=1)

        self.assertEqual(["fastest_lap_lap"], [column for column in frame.columns if column == "fastest_lap_lap"])
        self.assertEqual("54", frame.loc[0, "fastest_lap_lap"])
        self.assertEqual("9", frame.loc[0, "fastest_lap_rank"])
        self.assertEqual("1:23.590", frame.loc[0, "fastest_lap_time"])


class JolpicaPaginationTests(unittest.TestCase):
    """Regression cover for the single-page truncation defect (Story 7.8).

    Every test here stubs `fetch_json`; nothing touches the network.
    """

    def test_fetch_and_cache_follows_offset_pages_until_total_is_retrieved(self) -> None:
        # 250 timings across three server pages of 100 / 100 / 50.
        pages = [
            make_laps_page(
                [("1", [make_timing(f"d{i}", i) for i in range(100)])],
                offset=0,
                total=250,
            ),
            make_laps_page(
                [("2", [make_timing(f"d{i}", i) for i in range(100)])],
                offset=100,
                total=250,
            ),
            make_laps_page(
                [("3", [make_timing(f"d{i}", i) for i in range(50)])],
                offset=200,
                total=250,
            ),
        ]
        calls: list[dict] = []

        def stub_fetch_json(path: str, *, params: dict | None = None, **_: object) -> dict:
            calls.append({"path": path, "params": dict(params or {})})
            return pages[len(calls) - 1]

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            with patch(
                "f1_analytics.data_sources.jolpica_loader.fetch_json", side_effect=stub_fetch_json
            ):
                payload = fetch_and_cache(
                    "laps", 2026, 1, cache_dir=cache_dir, sleep_seconds=0.0
                )

            cached = json.loads(
                cache_path("laps", 2026, 1, cache_dir=cache_dir).read_text(encoding="utf-8")
            )

        # Follow-up offset requests were actually issued.
        self.assertEqual(3, len(calls))
        self.assertEqual([0, 100, 200], [call["params"]["offset"] for call in calls])
        self.assertEqual(["2026/1/laps.json"] * 3, [call["path"] for call in calls])

        # Every row from every page is present, in the payload and on disk.
        self.assertEqual(250, count_payload_items("laps", payload))
        self.assertEqual(250, len(parse_laps(payload, 2026, 1)))
        self.assertEqual(250, len(parse_laps(cached, 2026, 1)))
        self.assertEqual(3, cached["_pagination"]["pages"])
        self.assertEqual(250, cached["_pagination"]["reported_total"])

    def test_fetch_and_cache_extends_timings_for_a_lap_split_across_pages(self) -> None:
        # Lap "5" straddles the page boundary with disjoint timings on each side.
        first_half = [make_timing("leclerc", 1), make_timing("russell", 2)]
        second_half = [make_timing("norris", 3)]
        pages = [
            make_laps_page(
                [("4", [make_timing("piastri", 1)]), ("5", first_half)],
                offset=0,
                total=4,
                limit=3,
            ),
            make_laps_page([("5", second_half)], offset=3, total=4, limit=3),
        ]
        calls: list[int] = []

        def stub_fetch_json(path: str, *, params: dict | None = None, **_: object) -> dict:
            calls.append(int((params or {}).get("offset", 0)))
            return pages[len(calls) - 1]

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "f1_analytics.data_sources.jolpica_loader.fetch_json", side_effect=stub_fetch_json
            ):
                payload = fetch_and_cache(
                    "laps", 2026, 1, cache_dir=Path(tmp), sleep_seconds=0.0
                )

        laps = payload["MRData"]["RaceTable"]["Races"][0]["Laps"]
        lap_five = next(lap for lap in laps if lap["number"] == "5")

        self.assertEqual([0, 3], calls)
        self.assertEqual(2, len(laps), "the split lap must not be duplicated")
        self.assertEqual(
            3,
            len(lap_five["Timings"]),
            "split-lap timings must be extended, never replaced by the later page",
        )
        self.assertEqual(
            ["leclerc", "russell", "norris"],
            [timing["driverId"] for timing in lap_five["Timings"]],
        )
        self.assertEqual(4, len(parse_laps(payload, 2026, 1)))

    def test_merge_payload_pages_sums_disjoint_timings_for_a_repeated_lap(self) -> None:
        merged = merge_payload_pages(
            [
                make_laps_page([("16", [make_timing("verstappen", 1)])], offset=0, total=3),
                make_laps_page(
                    [("16", [make_timing("hamilton", 2), make_timing("alonso", 3)])],
                    offset=1,
                    total=3,
                ),
            ]
        )

        laps = merged["MRData"]["RaceTable"]["Races"][0]["Laps"]

        self.assertEqual(1, len(laps))
        self.assertEqual(3, len(laps[0]["Timings"]))
        self.assertEqual(3, count_payload_items("laps", merged))

    def test_merge_payload_pages_extends_standings_lists(self) -> None:
        def standings_page(entries: list[str], *, offset: int, total: int) -> dict:
            return {
                "MRData": {
                    "limit": "100",
                    "offset": str(offset),
                    "total": str(total),
                    "StandingsTable": {
                        "season": "2026",
                        "round": "1",
                        "StandingsLists": [
                            {
                                "season": "2026",
                                "round": "1",
                                "DriverStandings": [
                                    {"Driver": {"driverId": entry}} for entry in entries
                                ],
                            }
                        ],
                    },
                }
            }

        merged = merge_payload_pages(
            [
                standings_page(["norris", "piastri"], offset=0, total=3),
                standings_page(["leclerc"], offset=2, total=3),
            ]
        )
        standings = merged["MRData"]["StandingsTable"]["StandingsLists"]

        self.assertEqual(1, len(standings))
        self.assertEqual(3, len(standings[0]["DriverStandings"]))
        self.assertEqual(3, count_payload_items("driverStandings", merged))

    def test_fetch_and_cache_raises_and_writes_nothing_when_merge_misses_total(self) -> None:
        # Server claims 250 items but stops handing them out after 100.
        pages = [
            make_laps_page(
                [("1", [make_timing(f"d{i}", i) for i in range(100)])], offset=0, total=250
            ),
            make_laps_page([], offset=100, total=250),
        ]
        calls: list[int] = []

        def stub_fetch_json(path: str, *, params: dict | None = None, **_: object) -> dict:
            calls.append(int((params or {}).get("offset", 0)))
            return pages[len(calls) - 1]

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            with patch(
                "f1_analytics.data_sources.jolpica_loader.fetch_json", side_effect=stub_fetch_json
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    fetch_and_cache("laps", 2026, 1, cache_dir=cache_dir, sleep_seconds=0.0)

            self.assertFalse(cache_path("laps", 2026, 1, cache_dir=cache_dir).exists())

        self.assertIn("merge mismatch", str(ctx.exception))

    def test_fetch_and_cache_handles_a_single_page_endpoint_without_extra_requests(self) -> None:
        page = {
            "MRData": {
                "limit": "100",
                "offset": "0",
                "total": "2",
                "RaceTable": {
                    "Races": [
                        {
                            "season": "2026",
                            "round": "1",
                            "Results": [
                                {"Driver": {"driverId": "norris"}, "position": "1"},
                                {"Driver": {"driverId": "piastri"}, "position": "2"},
                            ],
                        }
                    ]
                },
            }
        }
        calls: list[int] = []

        def stub_fetch_json(path: str, *, params: dict | None = None, **_: object) -> dict:
            calls.append(int((params or {}).get("offset", 0)))
            return page

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "f1_analytics.data_sources.jolpica_loader.fetch_json", side_effect=stub_fetch_json
            ):
                payload = fetch_and_cache(
                    "results", 2026, 1, cache_dir=Path(tmp), sleep_seconds=0.0
                )

        self.assertEqual([0], calls)
        self.assertEqual(2, len(parse_results(payload, 2026, 1)))

    def test_discover_season_rounds_follows_the_same_paginated_path(self) -> None:
        def races_page(rounds: list[int], *, offset: int, total: int) -> dict:
            return {
                "MRData": {
                    "limit": "2",
                    "offset": str(offset),
                    "total": str(total),
                    "RaceTable": {
                        "season": "2026",
                        "Races": [
                            {"season": "2026", "round": str(round_)} for round_ in rounds
                        ],
                    },
                }
            }

        pages = [races_page([1, 2], offset=0, total=3), races_page([3], offset=2, total=3)]
        calls: list[int] = []

        def stub_fetch_json(path: str, *, params: dict | None = None, **_: object) -> dict:
            calls.append(int((params or {}).get("offset", 0)))
            return pages[len(calls) - 1]

        with patch(
            "f1_analytics.data_sources.jolpica_loader.fetch_json", side_effect=stub_fetch_json
        ):
            rounds = discover_season_rounds(2026, sleep_seconds=0.0)

        self.assertEqual([0, 2], calls)
        self.assertEqual([1, 2, 3], rounds)

    def test_count_payload_items_rejects_an_unmapped_endpoint(self) -> None:
        with self.assertRaises(ValueError):
            count_payload_items("seasons", {"MRData": {}})


class JolpicaRateLimitTests(unittest.TestCase):
    def _http_error(self, code: int, headers: dict | None = None) -> HTTPError:
        return HTTPError("https://example.invalid", code, "boom", headers or {}, None)

    def test_fetch_json_retries_after_http_429_then_succeeds(self) -> None:
        responses = [self._http_error(429), self._http_error(429), {"MRData": {"total": "0"}}]
        slept: list[float] = []

        class StubResponse:
            def __init__(self, payload: dict) -> None:
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(self._payload).encode("utf-8")

        def stub_urlopen(request: object, timeout: int = 30):
            item = responses.pop(0)
            if isinstance(item, HTTPError):
                raise item
            return StubResponse(item)

        with patch("f1_analytics.data_sources.jolpica.urlopen", side_effect=stub_urlopen):
            with patch(
                "f1_analytics.data_sources.jolpica.time.sleep", side_effect=slept.append
            ):
                payload = fetch_json("2026/1/laps.json", backoff_seconds=1.0)

        self.assertEqual({"MRData": {"total": "0"}}, payload)
        self.assertEqual([1.0, 2.0], slept, "backoff must grow between 429 retries")
        self.assertEqual([], responses)

    def test_fetch_json_raises_runtime_error_when_the_429_retry_budget_runs_out(self) -> None:
        def stub_urlopen(request: object, timeout: int = 30):
            raise HTTPError("https://example.invalid", 429, "slow down", {"Retry-After": "3"}, None)

        slept: list[float] = []
        with patch("f1_analytics.data_sources.jolpica.urlopen", side_effect=stub_urlopen):
            with patch(
                "f1_analytics.data_sources.jolpica.time.sleep", side_effect=slept.append
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    fetch_json("2026/1/laps.json", max_retries=2, backoff_seconds=1.0)

        self.assertIn("HTTP 429", str(ctx.exception))
        self.assertEqual([3.0, 3.0], slept, "Retry-After header must be honoured")

    def test_fetch_json_does_not_retry_non_429_http_errors(self) -> None:
        attempts: list[int] = []

        def stub_urlopen(request: object, timeout: int = 30):
            attempts.append(1)
            raise HTTPError("https://example.invalid", 500, "server error", {}, None)

        with patch("f1_analytics.data_sources.jolpica.urlopen", side_effect=stub_urlopen):
            with self.assertRaises(RuntimeError) as ctx:
                fetch_json("2026/1/laps.json")

        self.assertEqual(1, len(attempts))
        self.assertIn("HTTP 500", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
