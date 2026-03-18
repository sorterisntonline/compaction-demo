"""
Playwright tests for the consensual memory UI.
Run with: pytest tests/test_ui.py -v
Requires: pip install playwright && playwright install chromium
"""

import json
import subprocess
import sys
import time
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

BASE_URL = "http://localhost:18999"
BEINGS_DIR = Path(__file__).parent.parent / "beings"


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    """Start a test server pointing at beings/ dir, no password."""
    tmp = tmp_path_factory.mktemp("beings")
    # Minimal ember.jsonl for testing
    init_event = {"v": 2, "type": "init", "timestamp": 1000, "id": "test-init",
                  "capacity": 10, "model": "test/model", "vote_model": "test/model", "api_key": ""}
    perception = {"v": 2, "type": "perception", "timestamp": 2000, "id": "p1", "content": "hello ember"}
    response_ev = {"v": 2, "type": "response", "timestamp": 3000, "id": "r1", "content": "hello back"}
    (tmp / "ember.jsonl").write_text(
        json.dumps(init_event) + "\n" +
        json.dumps(perception) + "\n" +
        json.dumps(response_ev) + "\n"
    )

    proc = subprocess.Popen(
        [sys.executable, "-m", "app.app", str(tmp), "--port", "18999"],
        cwd=Path(__file__).parent.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for startup
    for _ in range(20):
        time.sleep(0.5)
        try:
            import urllib.request
            urllib.request.urlopen(f"{BASE_URL}/", timeout=1)
            break
        except Exception:
            pass

    yield proc, tmp

    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session")
def browser_ctx(server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        yield ctx
        browser.close()


@pytest.fixture
def page(browser_ctx) -> Page:
    p = browser_ctx.new_page()
    yield p
    p.close()


# === TESTS ===

def test_index_shows_beings(page, server):
    page.goto(BASE_URL)
    expect(page.locator(".being-link")).to_contain_text("ember")


def test_index_has_git_link(page, server):
    page.goto(BASE_URL)
    expect(page.locator("a[href='/git']")).to_be_visible()


def test_being_page_loads(page, server):
    page.goto(f"{BASE_URL}/ember")
    expect(page.locator(".top-bar")).to_contain_text("ember")
    expect(page.locator(".top-bar")).to_contain_text("events")


def test_being_page_shows_events(page, server):
    page.goto(f"{BASE_URL}/ember")
    expect(page.locator(".event")).to_have_count(3)


def test_being_page_has_redact_button(page, server):
    page.goto(f"{BASE_URL}/ember")
    expect(page.locator("button", has_text="↩ redact")).to_be_visible()


def test_being_page_has_push_button(page, server):
    page.goto(f"{BASE_URL}/ember")
    expect(page.locator("button", has_text="⬆ push git")).to_be_visible()


def test_being_page_has_sse_script(page, server):
    page.goto(f"{BASE_URL}/ember")
    content = page.content()
    assert "EventSource" in content
    assert "/sse/ember" in content


def test_sse_endpoint_responds(page, server):
    """SSE endpoint returns text/event-stream."""
    import urllib.request
    resp = urllib.request.urlopen(f"{BASE_URL}/sse/ember", timeout=3)
    assert "text/event-stream" in resp.headers.get("Content-Type", "")
    resp.close()


def test_git_page_loads(page, server):
    page.goto(f"{BASE_URL}/git")
    expect(page.locator(".top-bar")).to_contain_text("git remotes")


def test_git_page_shows_default_remotes(page, server):
    page.goto(f"{BASE_URL}/git")
    content = page.content()
    assert "codeberg.org" in content
    assert "github.com" in content
    assert "gitlab.com" in content


def test_git_page_add_remote(page, server):
    _, tmp = server
    page.goto(f"{BASE_URL}/git")

    # Fill in the "add remote" form (last remote-row, empty fields)
    add_row = page.locator(".remote-row").last
    add_row.locator("input[name='name']").fill("testremote")
    add_row.locator("input[name='url']").fill("https://example.com/test.git")
    add_row.locator("input[name='user']").fill("testuser")
    add_row.locator("input[name='token_var']").fill("TEST_TOKEN")
    add_row.locator("button", has_text="add remote").click()

    # Should redirect back to /git and show the new remote
    page.wait_for_url(f"{BASE_URL}/git")
    expect(page.locator("[data-remote='testremote']")).to_be_visible()


def test_git_page_edit_remote(page, server):
    _, tmp = server
    # Ensure testremote exists from previous test
    page.goto(f"{BASE_URL}/git")

    row = page.locator("[data-remote='testremote']")
    if not row.is_visible():
        pytest.skip("testremote not present (run tests in order)")

    url_input = row.locator("input[name='url']")
    url_input.fill("https://example.com/updated.git")
    row.locator("button", has_text="save").click()

    page.wait_for_url(f"{BASE_URL}/git")
    expect(page.locator("[data-remote='testremote'] input[name='url']")).to_have_value("https://example.com/updated.git")


def test_git_page_delete_remote(page, server):
    page.goto(f"{BASE_URL}/git")
    row = page.locator("[data-remote='testremote']")
    if not row.is_visible():
        pytest.skip("testremote not present")

    page.on("dialog", lambda d: d.accept())
    row.locator("button", has_text="✕").click()

    page.wait_for_url(f"{BASE_URL}/git")
    expect(page.locator("[data-remote='testremote']")).not_to_be_visible()


def test_redact_removes_last_perception(page, server):
    _, tmp = server
    page.goto(f"{BASE_URL}/ember")

    events_before = page.locator(".event").count()

    page.on("dialog", lambda d: d.accept())
    page.locator("button", has_text="↩ redact").click()
    page.wait_for_url(f"{BASE_URL}/ember")

    events_after = page.locator(".event").count()
    # perception + response removed = 2 fewer events
    assert events_after == events_before - 2
