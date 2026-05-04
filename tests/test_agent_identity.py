import sys
import unittest
from unittest.mock import patch

from tools import archestra_bounty_watch
from tools import devto_engagement_check
from tools import devto_public_email_scan
from tools import email_lead_watch
from tools import farcaster_reply_observe
from tools import github_bounty_priority_scan
from tools import github_lead_scan
from tools import github_pr_watch
from tools import github_reply_check
from tools import hn_show_contact_scout
from tools import lobsters_newest_contact_scout
from tools import opire_featured_bounty_check
from tools import pages_traffic_check
from tools.agent_identity import default_agent_name


BUILD_PARSER_MODULES = (
    ("archestra_bounty_watch", archestra_bounty_watch),
    ("devto_engagement_check", devto_engagement_check),
    ("email_lead_watch", email_lead_watch),
    ("farcaster_reply_observe", farcaster_reply_observe),
    ("github_bounty_priority_scan", github_bounty_priority_scan),
    ("hn_show_contact_scout", hn_show_contact_scout),
    ("lobsters_newest_contact_scout", lobsters_newest_contact_scout),
    ("opire_featured_bounty_check", opire_featured_bounty_check),
    ("pages_traffic_check", pages_traffic_check),
)


def parser_agent_default(parser) -> str:
    for action in parser._actions:
        if "--agent" in action.option_strings:
            return action.default
    raise AssertionError("parser has no --agent action")


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

    def test_tool_agent_defaults_follow_runtime_detection(self) -> None:
        with patch.dict("os.environ", {"CLAUDECODE": "1"}, clear=True):
            for name, module in BUILD_PARSER_MODULES:
                with self.subTest(tool=name):
                    self.assertEqual(parser_agent_default(module.build_parser()), "claude")

            self.assertEqual(devto_public_email_scan.parse_args([]).agent, "claude")
            self.assertEqual(github_pr_watch.parse_args([]).agent, "claude")

            with patch.object(sys, "argv", ["github_lead_scan.py"]):
                self.assertEqual(github_lead_scan.parse_args().agent, "claude")

            with patch.object(sys, "argv", ["github_reply_check.py"]):
                self.assertEqual(github_reply_check.parse_args().agent, "claude")
