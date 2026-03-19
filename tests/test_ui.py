"""
Playwright tests for the consensual memory UI.

Run:

  pytest tests/test_ui.py -v

Requires: pip install -e '.[dev]' && playwright install chromium
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import Page, expect

# SSE + unpkg Idiomorph can be slow on cold start
PAINT_MS = 60_000


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    """
    Start app on 127.0.0.1 with a free port. No login gate, mock LLM, isolated beings dir.
    """
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    tmp = tmp_path_factory.mktemp("beings")

    init_event = {
        "v": 2,
        "type": "init",
        "timestamp": 1000,
        "id": "test-init",
        "capacity": 10,
        "model": "test/model",
        "vote_model": "test/vote-model",
        "api_key": "",
    }
    perception = {
        "v": 2,
        "type": "perception",
        "timestamp": 2000,
        "id": "p1",
        "content": "hello ember",
    }
    response_ev = {
        "v": 2,
        "type": "response",
        "timestamp": 3000,
        "id": "r1",
        "content": "hello back",
    }
    thought_ev = {
        "v": 2,
        "type": "thought",
        "timestamp": 4000,
        "id": "t1",
        "content": "I am thinking about things",
    }
    (tmp / "ember.jsonl").write_text(
        json.dumps(init_event)
        + "\n"
        + json.dumps(perception)
        + "\n"
        + json.dumps(response_ev)
        + "\n"
        + json.dumps(thought_ev)
        + "\n"
    )

    env = os.environ.copy()
    env["MOCK_LLM"] = "1"
    env["PASSWORD"] = ""  # do not inherit a real PASSWORD (SSE would loop on login)
    env.pop("OPENROUTER_API_KEY", None)

    proc = subprocess.Popen(
        [sys.executable, "-m", "app.app", str(tmp), "--port", str(port)],
        cwd=Path(__file__).parent.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            import urllib.request

            urllib.request.urlopen(f"{base_url}/", timeout=2)
            break
        except OSError:
            time.sleep(0.3)
            if proc.poll() is not None:
                raise RuntimeError(f"Server exited early (code {proc.returncode})")
    else:
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError("Server did not become ready in time")

    yield SimpleNamespace(base_url=base_url, beings_dir=tmp, proc=proc)

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser_ctx(server):
    from playwright.sync_api import sync_playwright

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


# --- helpers ---


def goto_painted(page: Page, path: str, server: SimpleNamespace, selector: str):
    page.goto(f"{server.base_url}{path}", wait_until="domcontentloaded")
    page.wait_for_selector(selector, timeout=PAINT_MS)


# === INDEX ===


def test_index_shows_beings(page, server):
    goto_painted(page, "/", server, ".being-link")
    expect(page.locator(".being-link")).to_contain_text("ember")


def test_index_has_git_link(page, server):
    goto_painted(page, "/", server, "a[href='/git']")
    expect(page.locator("a[href='/git']")).to_be_visible()


# === BEING PAGE ===


def test_being_page_loads(page, server):
    goto_painted(page, "/ember", server, ".top-bar")
    expect(page.locator(".top-bar")).to_contain_text("ember")
    expect(page.locator(".top-bar")).to_contain_text("events")


def test_being_page_shows_events(page, server):
    goto_painted(page, "/ember", server, ".event")
    expect(page.locator(".event")).to_have_count(4)


def test_being_page_has_controls(page, server):
    goto_painted(page, "/ember", server, "button")
    expect(page.locator("button", has_text="↩ redact")).to_be_visible()
    expect(page.locator("button", has_text="⬆ push git")).to_be_visible()
    expect(page.locator("button", has_text="compact")).to_be_visible()
    expect(page.locator("button", has_text="go")).to_be_visible()


def test_being_page_has_textarea(page, server):
    goto_painted(page, "/ember", server, "textarea")
    expect(page.locator("textarea[name='message']")).to_be_visible()


# === SSE (HTTP) ===


def test_sse_endpoint_responds(server):
    import urllib.request

    req = urllib.request.Request(
        f"{server.base_url}/ember/sse",
        headers={"Accept": "text/event-stream"},
    )
    resp = urllib.request.urlopen(req, timeout=10)
    try:
        ct = resp.headers.get("Content-Type", "")
        assert "text/event-stream" in ct
    finally:
        resp.close()


# === EXPAND / COLLAPSE ===


def test_expand_event_shows_content(page, server):
    goto_painted(page, "/ember", server, "form.event.expandable")
    page.locator("form.event.expandable").first.locator("button.event-row").click()
    page.wait_for_selector(".event.expanded", timeout=PAINT_MS)
    expect(page.locator(".event.expanded .event-content")).to_be_visible()


def test_collapse_expanded_event(page, server):
    goto_painted(page, "/ember", server, "form.event.expandable")
    page.locator("form.event.expandable").first.locator("button.event-row").click()
    page.wait_for_selector(".event.expanded", timeout=PAINT_MS)
    # requestSubmit() fires the submit event (HTMLFormElement.submit() does not)
    page.locator(".event.expanded form.collapse-form").evaluate("f => f.requestSubmit()")
    page.wait_for_selector(".event.expanded", state="detached", timeout=PAINT_MS)
    expect(page.locator("form.event.expandable").first).to_be_visible()


# === SEND MESSAGE (MOCK LLM) ===


def test_send_message_creates_response(page, server):
    goto_painted(page, "/ember", server, ".event")
    events_before = page.locator(".event").count()

    page.locator("textarea[name='message']").fill("test message from playwright")
    page.locator("button", has_text="go").click()

    page.wait_for_function(
        "n => document.querySelectorAll('.event').length > n",
        arg=events_before,
        timeout=PAINT_MS,
    )
    assert page.locator(".event").count() >= events_before + 2


# === GIT PAGE ===


def test_git_page_loads(page, server):
    goto_painted(page, "/git", server, ".top-bar")
    expect(page.locator(".top-bar")).to_contain_text("git")


# === REDACT ===


def test_redact_removes_last_perception(page, server):
    goto_painted(page, "/ember", server, ".event")
    events_before = page.locator(".event").count()

    page.once("dialog", lambda d: d.accept())
    page.locator("button", has_text="↩ redact").click()

    page.wait_for_function(
        "n => document.querySelectorAll('.event').length < n",
        arg=events_before,
        timeout=PAINT_MS,
    )
    assert page.locator(".event").count() < events_before
