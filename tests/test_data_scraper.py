import pytest

from evohunter.data_scraper import ScrapeError, clean_scraped_text, scrape_source, scrape_sources


def test_clean_scraped_text_removes_html_noise():
    html = """
    <html>
      <head><script>window.secret = true</script><style>.x{}</style></head>
      <body>
        <h1>Alice Zhang</h1>
        <p>Python, LLM, Playwright</p>
      </body>
    </html>
    """

    output = clean_scraped_text(html)

    assert "Alice Zhang" in output
    assert "Python, LLM, Playwright" in output
    assert "window.secret" not in output
    assert ".x" not in output


def test_scrape_source_reads_local_text_file(tmp_path):
    source = tmp_path / "candidate.txt"
    source.write_text(" Alice Zhang\n\nPython engineer  ", encoding="utf-8")

    assert scrape_source(str(source)) == "Alice Zhang\nPython engineer"


def test_scrape_source_raises_for_missing_file(tmp_path):
    with pytest.raises(ScrapeError, match="source not found"):
        scrape_source(str(tmp_path / "missing.txt"))


def test_scrape_sources_returns_one_result_per_source(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("Alice\nPython", encoding="utf-8")
    second.write_text("Bob\nLLM", encoding="utf-8")

    results = scrape_sources([str(first), str(second)])

    assert [result["source"] for result in results] == [str(first), str(second)]
    assert [result["status"] for result in results] == ["success", "success"]
    assert results[0]["text"] == "Alice\nPython"
    assert results[1]["text"] == "Bob\nLLM"
    assert results[0]["error"] == ""


def test_scrape_sources_marks_failed_source_without_stopping_batch(tmp_path):
    good = tmp_path / "good.txt"
    missing = tmp_path / "missing.txt"
    good.write_text("Alice Zhang", encoding="utf-8")

    results = scrape_sources([str(good), str(missing)])

    assert results[0]["status"] == "success"
    assert results[0]["text"] == "Alice Zhang"
    assert results[1]["status"] == "error"
    assert results[1]["text"] == ""
    assert "source not found" in results[1]["error"]


def test_scrape_sources_cleans_html_text(tmp_path):
    source = tmp_path / "profile.html"
    source.write_text("<h1>Alice</h1><style>.x{}</style><script>x()</script><p>Python</p>", encoding="utf-8")

    results = scrape_sources([str(source)])

    assert results == [
        {
            "source": str(source),
            "status": "success",
            "text": "Alice\nPython",
            "error": "",
        }
    ]


def test_scrape_sources_keeps_single_scrape_source_compatible(tmp_path):
    source = tmp_path / "candidate.txt"
    source.write_text(" Alice Zhang\n\nPython engineer  ", encoding="utf-8")

    assert scrape_source(str(source)) == "Alice Zhang\nPython engineer"
    assert scrape_sources([str(source)])[0]["text"] == "Alice Zhang\nPython engineer"
