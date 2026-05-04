import unittest

from tools.agent_identity import default_agent_name


class AgentIdentityTests(unittest.TestCase):
    def test_prefers_explicit_runtime_agent_env(self) -> None:
        self.assertEqual(
            default_agent_name({"AGENT_NAME": "claude", "BRIDGE_AGENT_NAME": "codex"}),
            "claude",
        )
        self.assertEqual(default_agent_name({"BRIDGE_AGENT_NAME": "claude"}), "claude")

    def test_claudecode_hint_before_fallback(self) -> None:
        self.assertEqual(default_agent_name({"CLAUDECODE": "1"}), "claude")
        self.assertEqual(default_agent_name({"CLAUDECODE": ""}), "codex")

    def test_supports_custom_fallback(self) -> None:
        self.assertEqual(default_agent_name({}, fallback="unknown"), "unknown")
