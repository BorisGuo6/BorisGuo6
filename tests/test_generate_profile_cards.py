import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_profile_cards import (  # noqa: E402
    ContributionActivity,
    ProfileStats,
    language_color,
    render_contribution_card,
    render_languages_card,
    render_stats_card,
)


class ProfileCardTests(unittest.TestCase):
    def test_stats_card_is_valid_svg(self):
        card = render_stats_card(
            "BorisGuo6",
            ProfileStats(stars=42, contributions=365, public_repositories=17, followers=8),
        )

        root = ET.fromstring(card)

        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn("365", card)
        self.assertIn("42", card)

    def test_languages_card_is_ranked_and_valid_svg(self):
        card = render_languages_card(
            "BorisGuo6", {"Python": 800, "C++": 150, "Shell": 50}
        )

        ET.fromstring(card)

        self.assertIn("Python 80.0%", card)
        self.assertLess(card.index("Python 80.0%"), card.index("C++ 15.0%"))

    def test_fallback_language_color_is_deterministic(self):
        self.assertEqual(language_color("UnlistedLanguage"), language_color("UnlistedLanguage"))

    def test_contribution_card_is_valid_svg(self):
        card = render_contribution_card(
            "BorisGuo6",
            ContributionActivity(
                total=365,
                followers=8,
                commits=240,
                pull_requests=32,
                issues=14,
                reviews=79,
            ),
        )

        ET.fromstring(card)

        self.assertIn("Commits", card)
        self.assertIn("Pull requests", card)
        self.assertIn("Code reviews", card)


if __name__ == "__main__":
    unittest.main()
