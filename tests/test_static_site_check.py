import tempfile
import unittest
from pathlib import Path

from tools.static_site_check import check_site


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://dutchaiagency.github.io/ai-agent-duo/</loc></url>
  <url><loc>https://dutchaiagency.github.io/ai-agent-duo/writing/</loc></url>
</urlset>
"""


class StaticSiteCheckTests(unittest.TestCase):
    def test_current_public_site_passes_static_checks(self) -> None:
        root = Path(__file__).resolve().parents[1]

        findings = check_site(root)

        self.assertEqual(findings, [])

    def test_reports_missing_link_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
</head><body><a href="missing.html">bad</a></body></html>""",
            )
            write(root / "sitemap.xml", SITEMAP)

            findings = check_site(root, public_pages=(Path("index.html"),))

        self.assertIn("missing_local_target", [finding.code for finding in findings])

    def test_reports_missing_sitemap_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
</head><body><a id="top" href="#top">top</a></body></html>""",
            )
            write(
                root / "writing/index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/writing/" />
</head><body></body></html>""",
            )
            write(
                root / "sitemap.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://dutchaiagency.github.io/ai-agent-duo/</loc></url>
</urlset>
""",
            )

            findings = check_site(
                root,
                public_pages=(Path("index.html"), Path("writing/index.html")),
            )

        self.assertIn(
            "canonical_missing_from_sitemap",
            [finding.code for finding in findings],
        )

    def test_reports_missing_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
</head><body><a href="#runway">Runway</a></body></html>""",
            )
            write(root / "sitemap.xml", SITEMAP)

            findings = check_site(root, public_pages=(Path("index.html"),))

        self.assertIn("missing_fragment", [finding.code for finding in findings])

    def test_reports_missing_fragment_in_linked_non_public_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
</head><body><a href="extra.html#missing">extra</a></body></html>""",
            )
            write(root / "extra.html", "<html><body><section id=\"present\"></section></body></html>")
            write(root / "sitemap.xml", SITEMAP)

            findings = check_site(root, public_pages=(Path("index.html"),))

        self.assertIn("missing_fragment", [finding.code for finding in findings])

    def test_reports_missing_social_preview_image_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
<meta property="og:image" content="https://dutchaiagency.github.io/ai-agent-duo/assets/missing.png?v=1" />
<meta name="twitter:image" content="assets/missing-twitter.png" />
</head><body></body></html>""",
            )
            write(root / "sitemap.xml", SITEMAP)

            findings = check_site(root, public_pages=(Path("index.html"),))

        self.assertIn("missing_local_target", [finding.code for finding in findings])
        self.assertTrue(
            any("meta:og:image" in finding.message for finding in findings),
            findings,
        )
        self.assertTrue(
            any("meta:twitter:image" in finding.message for finding in findings),
            findings,
        )

    def test_reports_internal_cta_missing_source_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
</head><body>
<a href="playbook/" data-cta="playbook" data-cta-source="site-runway">playbook</a>
</body></html>""",
            )
            write(root / "playbook/index.html", "<html><body></body></html>")
            write(root / "sitemap.xml", SITEMAP)

            findings = check_site(root, public_pages=(Path("index.html"),))

        self.assertIn("cta_source_mismatch", [finding.code for finding in findings])

    def test_reports_internal_cta_wrong_source_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
</head><body>
<a href="playbook/?source=site-hero" data-cta="playbook" data-cta-source="site-runway">playbook</a>
</body></html>""",
            )
            write(root / "playbook/index.html", "<html><body></body></html>")
            write(root / "sitemap.xml", SITEMAP)

            findings = check_site(root, public_pages=(Path("index.html"),))

        self.assertIn("cta_source_mismatch", [finding.code for finding in findings])

    def test_reports_sitemap_missing_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
</head><body></body></html>""",
            )
            write(
                root / "sitemap.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://dutchaiagency.github.io/ai-agent-duo/</loc></url>
  <url><loc>https://dutchaiagency.github.io/ai-agent-duo/missing/</loc></url>
</urlset>
""",
            )

            findings = check_site(root, public_pages=(Path("index.html"),))

        self.assertIn("sitemap_missing_target", [finding.code for finding in findings])

    def test_reports_sitemap_missing_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "index.html",
                """<html><head>
<link rel="canonical" href="https://dutchaiagency.github.io/ai-agent-duo/" />
</head><body><section id="runway"></section></body></html>""",
            )
            write(
                root / "sitemap.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://dutchaiagency.github.io/ai-agent-duo/</loc></url>
  <url><loc>https://dutchaiagency.github.io/ai-agent-duo/#pricing</loc></url>
</urlset>
""",
            )

            findings = check_site(root, public_pages=(Path("index.html"),))

        self.assertIn("sitemap_missing_fragment", [finding.code for finding in findings])


if __name__ == "__main__":
    unittest.main()
