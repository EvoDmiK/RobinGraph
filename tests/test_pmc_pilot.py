"""Small checks for the one-article PMC pilot parser."""

from __future__ import annotations

import unittest

from scripts.load_pmc_pilot import article_hash, parse_article


class PmcPilotParseTest(unittest.TestCase):
    def test_keeps_body_text_and_excludes_figure_content(self) -> None:
        oai = b"""
        <record><article>
          <article-meta>
          <article-id pub-id-type="pmcid">PMC9946348</article-id>
          <article-id pub-id-type="doi">10.1126/test</article-id>
          <article-title>Pilot title</article-title>
          <license>https://creativecommons.org/licenses/by/4.0/</license>
          </article-meta>
          <abstract><p>Birds declined in the city.</p></abstract>
          <body><sec><title>Results</title><p>Evidence from the field.</p>
            <fig><caption><p>Excluded figure caption.</p></caption></fig>
          </sec></body>
        </article></record>"""
        title, doi, chunks = parse_article(oai)
        self.assertEqual(("Pilot title", "10.1126/test"), (title, doi))
        self.assertEqual(2, len(chunks))
        self.assertEqual("Abstract paragraph 1", chunks[0]["locator"])
        self.assertEqual("Birds declined in the city.", chunks[0]["text"])
        self.assertEqual("Results paragraph 1", chunks[1]["locator"])

    def test_rejects_article_without_expected_license(self) -> None:
        with self.assertRaisesRegex(ValueError, "CC BY"):
            parse_article(b"<record><article-meta><license>CC BY-NC</license></article-meta></record>")

    def test_hash_ignores_oai_response_date(self) -> None:
        first = b"<record><responseDate>2026-09-29</responseDate><article><body>Birds</body></article></record>"
        second = b"<record><responseDate>2026-09-30</responseDate><article><body>Birds</body></article></record>"
        self.assertEqual(article_hash(first), article_hash(second))


if __name__ == "__main__":
    unittest.main()
