"""
Tests for p6 tools — PubMed, UniProt, vector store.
All external HTTP calls are mocked — no network required.
"""

from unittest.mock import MagicMock, patch



# ---------------------------------------------------------------------------
# PubMed tests
# ---------------------------------------------------------------------------

class TestPubmedSearch:
    def test_returns_list_of_pmid_title(self):
        mock_search = MagicMock()
        mock_search.__enter__ = lambda s: s
        mock_search.__exit__ = MagicMock(return_value=False)
        mock_search.read = MagicMock(return_value=b'<eSearchResult><IdList><Id>12345678</Id></IdList></eSearchResult>')

        mock_fetch = MagicMock()
        mock_fetch.__enter__ = lambda s: s
        mock_fetch.__exit__ = MagicMock(return_value=False)

        with patch("src.tools.pubmed.Entrez.esearch", return_value=mock_search), \
             patch("src.tools.pubmed.Entrez.read", return_value={"IdList": ["12345678"]}), \
             patch("src.tools.pubmed.Entrez.efetch", return_value=mock_fetch), \
             patch("src.tools.pubmed.Medline.parse", return_value=[
                 {"PMID": "12345678", "TI": "TP53 mutations in glioblastoma"}
             ]), \
             patch("src.tools.pubmed.time.sleep"):
            from src.tools.pubmed import search
            results = search("TP53 glioblastoma", max_results=1)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["pmid"] == "12345678"
        assert "TP53" in results[0]["title"]

    def test_returns_empty_list_when_no_results(self):
        with patch("src.tools.pubmed.Entrez.esearch"), \
             patch("src.tools.pubmed.Entrez.read", return_value={"IdList": []}), \
             patch("src.tools.pubmed.time.sleep"):
            from src.tools.pubmed import search
            results = search("xyznonexistenttopic12345")
        assert results == []

    def test_returns_error_dict_on_exception(self):
        with patch("src.tools.pubmed.Entrez.esearch", side_effect=Exception("network error")), \
             patch("src.tools.pubmed.time.sleep"):
            from src.tools.pubmed import search
            results = search("anything")
        assert len(results) == 1
        assert "error" in results[0]


class TestPubmedFetch:
    def test_returns_full_record(self):
        mock_handle = MagicMock()
        with patch("src.tools.pubmed.Entrez.efetch", return_value=mock_handle), \
             patch("src.tools.pubmed.Medline.parse", return_value=[{
                 "PMID": "12345678",
                 "TI":   "TP53 mutations in glioblastoma",
                 "AB":   "Background: TP53 is frequently mutated...",
                 "AU":   ["Smith J", "Jones A"],
                 "TA":   "Nature Cancer",
                 "DP":   "2023 Jan",
             }]), \
             patch("src.tools.pubmed.time.sleep"):
            from src.tools.pubmed import fetch
            result = fetch("12345678")

        assert result["pmid"] == "12345678"
        assert result["year"] == "2023"
        assert "url" in result
        assert "pubmed.ncbi.nlm.nih.gov/12345678" in result["url"]

    def test_returns_error_on_empty_record(self):
        mock_handle = MagicMock()
        with patch("src.tools.pubmed.Entrez.efetch", return_value=mock_handle), \
             patch("src.tools.pubmed.Medline.parse", return_value=[]), \
             patch("src.tools.pubmed.time.sleep"):
            from src.tools.pubmed import fetch
            result = fetch("99999999")
        assert "error" in result


# ---------------------------------------------------------------------------
# UniProt tests
# ---------------------------------------------------------------------------

class TestUniprotLookup:
    def _mock_response(self, data: dict):
        resp = MagicMock()
        resp.json.return_value = data
        resp.raise_for_status = MagicMock()
        return resp

    def test_returns_accession_and_gene(self):
        mock_data = {
            "results": [{
                "primaryAccession": "P04637",
                "genes": [{"geneName": {"value": "TP53"}}],
                "proteinDescription": {
                    "recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}
                },
                "organism": {"scientificName": "Homo sapiens"},
                "sequence": {"length": 393},
                "features": [],
                "comments": [],
            }]
        }
        with patch("src.tools.uniprot.requests.get", return_value=self._mock_response(mock_data)):
            from src.tools.uniprot import lookup
            result = lookup("TP53", organism="human")

        assert result["accession"] == "P04637"
        assert result["gene"] == "TP53"
        assert "uniprot.org/uniprot/P04637" in result["url"]
        assert result["length"] == 393

    def test_returns_error_when_not_found(self):
        with patch("src.tools.uniprot.requests.get",
                   return_value=self._mock_response({"results": []})):
            from src.tools.uniprot import lookup
            result = lookup("NONEXISTENTGENE999")
        assert "error" in result

    def test_returns_error_on_network_failure(self):
        import requests as req
        with patch("src.tools.uniprot.requests.get",
                   side_effect=req.RequestException("timeout")):
            from src.tools.uniprot import lookup
            result = lookup("TP53")
        assert "error" in result


# ---------------------------------------------------------------------------
# Vector store tests
# ---------------------------------------------------------------------------

class TestVectorStore:
    def test_index_and_search(self, tmp_path):
        from src.tools.vector_store import index, search

        docs = [
            {"text": "TP53 is a tumour suppressor gene frequently mutated in cancer.", "source": "doc1"},
            {"text": "SciLifeLab provides genomics infrastructure for Swedish researchers.", "source": "doc2"},
        ]
        n = index(docs, persist_dir=str(tmp_path))
        assert n >= 2

        results = search("tumour suppressor", k=2, persist_dir=str(tmp_path))
        assert isinstance(results, list)
        assert len(results) >= 1
        assert "text" in results[0]
        assert "score" in results[0]
        # Top result should be about TP53, not SciLifeLab
        assert "TP53" in results[0]["text"] or "tumour" in results[0]["text"].lower()

    def test_search_empty_corpus_returns_empty(self, tmp_path):
        from src.tools.vector_store import search
        results = search("anything", k=3, persist_dir=str(tmp_path / "empty"))
        assert results == []

    def test_index_deduplicates_on_reindex(self, tmp_path):
        from src.tools.vector_store import index
        docs = [{"text": "Same document indexed twice.", "source": "dup"}]
        n1 = index(docs, persist_dir=str(tmp_path))
        n2 = index(docs, persist_dir=str(tmp_path))
        assert n1 == n2   # same count — upsert deduplicates by ID
