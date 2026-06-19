import pytest

from evohunter.data_scraper import ScrapeError, clean_scraped_text, scrape_source


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
