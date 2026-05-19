import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import literature_search


PUBMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2024</Year>
              <Month>May</Month>
              <Day>08</Day>
            </PubDate>
          </JournalIssue>
          <Title>Journal of Useful Tests</Title>
        </Journal>
        <ArticleTitle>A careful paper about useful metadata.</ArticleTitle>
        <Abstract>
          <AbstractText Label="Background">Metadata should be easy to export.</AbstractText>
          <AbstractText Label="Results">The parser keeps the abstract text.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <ForeName>Ada</ForeName>
            <LastName>Lovelace</LastName>
          </Author>
          <Author>
            <ForeName>Grace</ForeName>
            <LastName>Hopper</LastName>
          </Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1000/example</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


class PubMedMetadataTests(unittest.TestCase):
    def test_run_search_returns_explicit_pubmed_metadata(self) -> None:
        esearch_payload = json.dumps(
            {"esearchresult": {"idlist": ["12345678"]}}
        ).encode("utf-8")

        with patch(
            "literature_search.make_request",
            side_effect=[esearch_payload, PUBMED_XML.encode("utf-8")],
        ):
            _query, results_by_source, errors, payload = literature_search.run_search(
                keywords=["metadata"],
                sources=["pubmed"],
                quiet_errors=True,
            )

        self.assertEqual(errors, {})
        result = results_by_source["pubmed"][0]
        result_payload = payload["results"]["pubmed"][0]

        self.assertEqual(result.pmid, "12345678")
        self.assertEqual(result.journal, "Journal of Useful Tests")
        self.assertEqual(result.publication_year, "2024")
        self.assertEqual(result.authors, ["Ada Lovelace", "Grace Hopper"])
        self.assertIn("Metadata should be easy to export.", result.abstract or "")
        self.assertEqual(result_payload["pmid"], "12345678")
        self.assertEqual(result_payload["publication_year"], "2024")
        self.assertEqual(result_payload["doi"], "10.1000/example")

    def test_write_csv_payload_flattens_results_for_spreadsheets(self) -> None:
        payload = {
            "query": "metadata",
            "results": {
                "pubmed": [
                    {
                        "source": "pubmed",
                        "title": "A careful paper about useful metadata.",
                        "authors": ["Ada Lovelace", "Grace Hopper"],
                        "journal": "Journal of Useful Tests",
                        "publication_year": "2024",
                        "published": "2024-05-08",
                        "pmid": "12345678",
                        "doi": "10.1000/example",
                        "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                        "abstract": "Metadata should be easy to export.",
                        "snippet": "Metadata should be easy to export.",
                        "source_id": "12345678",
                    }
                ]
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.csv"
            literature_search.write_csv_payload(payload, str(path))

            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["query"], "metadata")
        self.assertEqual(rows[0]["authors"], "Ada Lovelace; Grace Hopper")
        self.assertEqual(rows[0]["pmid"], "12345678")
        self.assertEqual(rows[0]["abstract"], "Metadata should be easy to export.")


if __name__ == "__main__":
    unittest.main()
