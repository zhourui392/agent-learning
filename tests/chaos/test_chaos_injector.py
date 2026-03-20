"""Tests for ChaosInjector."""

import unittest

from src.chaos.chaos_injector import InMemoryChaosInjector
from src.chaos.models import ChaosScenario
from src.config_center.config_store import ConfigCenter


class TestInMemoryChaosInjector(unittest.TestCase):
    def test_inject_and_remove(self):
        injector = InMemoryChaosInjector()
        scenario = ChaosScenario(fault_type="latency", target_component="rag")
        injector.inject(scenario)
        self.assertEqual(len(injector.active_scenarios()), 1)
        injector.remove(scenario)
        self.assertEqual(len(injector.active_scenarios()), 0)

    def test_wrap_execution_success(self):
        injector = InMemoryChaosInjector()
        scenario = ChaosScenario(
            fault_type="latency",
            target_component="rag",
            parameters={"delay_ms": 1},
        )
        result = injector.wrap_execution(scenario, lambda: "ok")
        self.assertTrue(result.success)
        self.assertGreater(result.recovery_time_ms, 0)
        self.assertEqual(len(injector.active_scenarios()), 0)

    def test_wrap_execution_error_injection(self):
        injector = InMemoryChaosInjector()
        scenario = ChaosScenario(
            fault_type="error",
            target_component="gateway",
            parameters={"error_rate": 1.0},
        )
        result = injector.wrap_execution(scenario, lambda: "should not reach")
        self.assertFalse(result.success)
        self.assertFalse(result.error_isolated)
        self.assertTrue(result.cascading_failure)

    def test_wrap_execution_timeout(self):
        injector = InMemoryChaosInjector()
        scenario = ChaosScenario(
            fault_type="timeout",
            target_component="api",
            parameters={"timeout_ms": 1},
        )
        result = injector.wrap_execution(scenario, lambda: "nope")
        self.assertFalse(result.success)
        self.assertIn("timeout", result.error.lower())

    def test_wrap_execution_resource_exhaustion(self):
        injector = InMemoryChaosInjector()
        scenario = ChaosScenario(
            fault_type="resource_exhaustion",
            target_component="memory",
        )
        result = injector.wrap_execution(scenario, lambda: "nope")
        self.assertFalse(result.success)

    def test_collect_results(self):
        injector = InMemoryChaosInjector()
        s1 = ChaosScenario(fault_type="latency", target_component="a", parameters={"delay_ms": 1})
        s2 = ChaosScenario(fault_type="latency", target_component="b", parameters={"delay_ms": 1})
        injector.wrap_execution(s1, lambda: 1)
        injector.wrap_execution(s2, lambda: 2)
        self.assertEqual(len(injector.collect_results()), 2)

    def test_from_config_center(self):
        cc = ConfigCenter()
        cc.put("chaos_scenarios", "s1", {
            "fault_type": "latency",
            "target_component": "rag",
            "parameters": {"delay_ms": 50},
            "duration_seconds": 5.0,
        })
        injector = InMemoryChaosInjector.from_config_center(cc)
        self.assertEqual(len(injector._preset_scenarios), 1)

    def test_from_config_center_empty(self):
        cc = ConfigCenter()
        injector = InMemoryChaosInjector.from_config_center(cc)
        self.assertEqual(len(injector._preset_scenarios), 0)


if __name__ == "__main__":
    unittest.main()
