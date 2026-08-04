from typer.testing import CliRunner
from capture_help.cli import app

runner = CliRunner()

SAMPLE_LITE_HTML = """<html>
<a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs&amp;rut=abc" class='result-link'>Example Docs</a>
<td class='result-snippet'>A great &amp; useful <b>guide</b></td>
<a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fsecond.example.org&amp;rut=def" class='result-link'>Second Result</a>
<td class='result-snippet'>More content</td>
</html>"""

def test_web_search_parser(monkeypatch):
    from capture_help.commands import web as web_mod

    class FakeResponse:
        def raise_for_status(self):
            pass
        text = SAMPLE_LITE_HTML

    class FakeGet:
        def __call__(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(web_mod.httpx, "get", FakeGet())
    results = web_mod._fetch_search_results("example query")
    assert len(results) == 2
    assert results[0]["title"] == "Example Docs"
    assert results[0]["url"] == "https://example.com/docs"
    assert "useful" in results[0]["snippet"]

def test_web_command_help():
    res = runner.invoke(app, ["web", "--help"])
    assert res.exit_code == 0
    assert "web" in res.output

def test_arch_subcommands():
    res_info = runner.invoke(app, ["arch", "info"])
    assert res_info.exit_code == 0

    res_clean = runner.invoke(app, ["arch", "clean"])
    assert res_clean.exit_code == 0

def test_gpu_command():
    res = runner.invoke(app, ["gpu"])
    assert res.exit_code == 0

def test_scan_command():
    res = runner.invoke(app, ["scan"])
    assert res.exit_code == 0

def test_redact_command():
    res = runner.invoke(app, ["redact", "sk-proj-12345678901234567890"])
    assert res.exit_code == 0
    assert "[REDACTED_API_KEY]" in res.output

def test_disk_command():
    res = runner.invoke(app, ["disk"])
    assert res.exit_code == 0

def test_firewall_command():
    res = runner.invoke(app, ["firewall"])
    assert res.exit_code == 0
