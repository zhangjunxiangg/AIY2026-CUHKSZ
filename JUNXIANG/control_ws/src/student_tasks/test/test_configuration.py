from __future__ import annotations

import math
import unittest

import support  # noqa: F401

from student_tasks.configuration import ConfigurationProvenance, require_production
from student_tasks.errors import ControlFailure


class ConfigurationProvenanceTests(unittest.TestCase):
    def test_synthetic_provenance_is_immutable_and_not_measured(self) -> None:
        provenance = ConfigurationProvenance("synthetic", "offline fixture")
        self.assertEqual("synthetic", provenance.kind)
        self.assertIsNone(provenance.measured_at)
        with self.assertRaises((AttributeError, TypeError)):
            provenance.kind = "measured"  # type: ignore[misc]

    def test_measured_provenance_requires_finite_positive_timestamp(self) -> None:
        for timestamp in (None, 0.0, -1.0, math.nan, math.inf):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                ConfigurationProvenance("measured", "field record", timestamp)
        measured = ConfigurationProvenance("measured", "field record", 123.5)
        self.assertEqual(123.5, measured.measured_at)

    def test_kind_source_and_synthetic_timestamp_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            ConfigurationProvenance("guessed", "source")
        with self.assertRaises(ValueError):
            ConfigurationProvenance("synthetic", "  ")
        with self.assertRaises(ValueError):
            ConfigurationProvenance("synthetic", "fixture", 1.0)

    def test_synthetic_configuration_is_rejected_for_production(self) -> None:
        with self.assertRaises(ControlFailure) as caught:
            require_production(ConfigurationProvenance("synthetic", "offline fixture"))
        self.assertEqual("PRODUCTION_CONFIG_REQUIRED", caught.exception.error.code)
        self.assertEqual("synthetic", caught.exception.context["configuration_kind"])

    def test_measured_configuration_is_accepted_for_production(self) -> None:
        measured = ConfigurationProvenance("measured", "signed field record", 123.5)
        self.assertIs(measured, require_production(measured))


if __name__ == "__main__":
    unittest.main()
