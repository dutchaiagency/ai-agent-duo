import json
import unittest
from datetime import UTC, date, datetime

from tools import pages_traffic_check as traffic


class PagesTrafficCheckTests(unittest.TestCase):
    def test_payload_counts_today_and_rolling_window(self) -> None:
        page = traffic.PageCounter(
            "playbook",
            "Playbook",
            "https://example.test/playbook/",
            "example.test/playbook",
        )
        payload = {
            "total": 99,
            "monthly": 40,
            "weekly": 20,
            "items": [
                {
                    "from": "2026-04-25",
                    "to": "2026-05-02",
                    "data": [
                        {"day": "2026-05-02", "value": 3},
                        {"day": "2026-05-01", "value": 4},
                        {"day": "2026-04-27", "value": 5},
                        {"day": "2026-04-25", "value": 100},
                    ],
                }
            ],
        }

        result = traffic.page_traffic_from_payload(
            page,
            payload,
            today=date(2026, 5, 2),
            window_days=7,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.total, 99)
        self.assertEqual(result.window_hits, 12)
        self.assertEqual(result.today_hits, 3)

    def test_render_markdown_includes_machine_readable_snapshot(self) -> None:
        pages = [
            traffic.PageTraffic(
                key="index",
                label="Home",
                public_url="https://example.test/",
                urn="example.test/index",
                api_url="https://hits.sh/api/urns/example.test/index",
                status="ok",
                total=10,
                monthly=10,
                weekly=5,
                window_hits=5,
                today_hits=1,
            )
        ]

        markdown = traffic.render_markdown(
            pages,
            generated_at=datetime(2026, 5, 2, 11, 30, tzinfo=UTC),
            window_days=7,
            bot_baseline_7d=210,
        )
        blob = markdown.split("```json", 1)[1].split("```", 1)[0]
        data = json.loads(blob)

        self.assertEqual(data["provider"], "hits.sh")
        self.assertFalse(data["counter_endpoint_increments"])
        self.assertEqual(data["pages"][0]["window_hits"], 5)


if __name__ == "__main__":
    unittest.main()
