"""The page itself, in a real browser (Playwright, Chromium): what a phone shows after a tap,
and the handwritten note never sitting on the savings line between 821 and 1440 px.
Needs: pip install playwright && python -m playwright install chromium; reads site/index.html."""
import pathlib
import pytest
pw = pytest.importorskip("playwright.sync_api")
ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = (ROOT / "site" / "index.html").as_uri()

@pytest.fixture(scope="module")
def browser():
    if not (ROOT / "site" / "index.html").exists():
        pytest.skip("no site/index.html: run scripts/build_site.py first")
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()

def open_page(browser, width, height, **kw):
    page = browser.new_page(viewport={"width": width, "height": height}, **kw)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(PAGE)
    page.evaluate("document.fonts.ready")
    return page, errors

IN_VIEW = """() => { const h = document.querySelector('#ticket h2').getBoundingClientRect(),
                      g = document.querySelector('#ticket .gapcell').getBoundingClientRect();
                      return h.top >= 0 && g.bottom <= window.innerHeight; }"""

def test_phone_first_screen_holds_the_italian_sum(browser):
    page, errors = open_page(browser, 390, 844, is_mobile=True, has_touch=True)
    assert page.inner_text("#ticket h2") == "Prurito & Stress"
    for sel in ("#ticket table.tk tbody tr:first-child", "#ticket .tot", "#ticket .strike", "#ticket .gapcell"):
        box = page.locator(sel).bounding_box()
        assert box["y"] >= 0 and box["y"] + box["height"] <= 844, sel
    assert page.evaluate("document.documentElement.scrollWidth") == 390
    assert errors == []
    page.close()

def settle(page):
    last = None
    for _ in range(40):
        y = page.evaluate("window.scrollY")
        if y == last:
            return
        last = y
        page.wait_for_timeout(80)

def test_phone_tapping_each_bundle_puts_its_ticket_on_screen(browser):
    page, errors = open_page(browser, 390, 844, is_mobile=True, has_touch=True)
    picks = page.locator(".pick")
    assert picks.count() == 19
    for i in range(picks.count()):
        pick = picks.nth(i)
        name = pick.locator(".nm").inner_text()
        pick.evaluate("p => p.scrollIntoView({block: 'start'})")   # reading the list, the ticket above the screen
        assert not page.evaluate(IN_VIEW), f"{name}: ticket already on screen before the tap, the test proves nothing"
        pick.tap()
        page.wait_for_function(IN_VIEW, timeout=6000)
        settle(page)                      # let the smooth scroll finish before the next tap
        assert page.inner_text("#ticket h2") == name
        assert pick.get_attribute("aria-pressed") == "true"
    assert errors == []
    page.close()

OVERLAPS = """() => {
  const out = [];
  document.querySelectorAll('.pick').forEach(p => {
    p.click();
    const n = document.querySelector('#ticket .note').getBoundingClientRect(),
          s = document.querySelector('#ticket .savings').getBoundingClientRect();
    if (n.left < s.right && s.left < n.right && n.top < s.bottom && s.top < n.bottom) out.push(p.dataset.k);
  });
  return out;
}"""

def test_note_never_overlaps_the_savings_from_821_to_1440(browser):
    page, errors = open_page(browser, 1440, 900)
    widths = sorted(set(list(range(821, 1441, 23)) + [821, 900, 1000, 1080, 1440]))
    for w in widths:                      # resized in place: the layout must hold without a reload
        page.set_viewport_size({"width": w, "height": 900})
        assert page.evaluate(OVERLAPS) == [], w
    assert errors == []
    page.close()

def test_hash_change_shows_that_bundle(browser):
    page, errors = open_page(browser, 1440, 900)
    page.evaluate("location.hash = 'bun-senior-support'")
    page.wait_for_function("document.querySelector('#ticket h2').textContent === 'Senior support'", timeout=2000)
    page.evaluate("location.hash = 'no-such-bundle'")
    assert page.inner_text("#ticket h2") == "Senior support"
    page.goto(PAGE + "#bun-denti-totale")
    assert page.inner_text("#ticket h2") == "Denti Totale"
    assert errors == []
    page.close()
