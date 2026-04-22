from __future__ import annotations

import unittest

from lpupdate.metrics_display import format_metric_value_for_display


class TestFormatMetricValueForDisplay(unittest.TestCase):
    def test_money_dict_usd_millions(self) -> None:
        s = format_metric_value_for_display({"value": 2_600_000.0, "currency": "USD", "period": "annual"})
        self.assertIn("2", s)
        self.assertIn("M", s)
        self.assertIn("annual", s)

    def test_plain_float_not_dict_repr(self) -> None:
        s = format_metric_value_for_display({"value": 2_600_000.0, "currency": "USD"})
        self.assertFalse(s.startswith("{"))

    def test_list_metric_compact(self) -> None:
        s = format_metric_value_for_display([12.5, 14.0])
        self.assertIn("12", s)

    def test_int_and_str(self) -> None:
        self.assertEqual(format_metric_value_for_display(42), "42")
        self.assertEqual(format_metric_value_for_display("hello"), "hello")

    def test_string_value_metric_with_period(self) -> None:
        s = format_metric_value_for_display({"value": "Profitable", "period": "Q1 2026"})
        self.assertEqual(s, "Profitable (Q1 2026)")

    def test_string_value_metric_with_unit_and_period(self) -> None:
        s = format_metric_value_for_display({"value": "<1%", "unit": "%", "period": "Q1 2026"})
        self.assertEqual(s, "<1% (Q1 2026)")


if __name__ == "__main__":
    unittest.main()
