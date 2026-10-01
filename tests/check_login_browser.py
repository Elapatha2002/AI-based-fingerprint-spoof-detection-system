"""Optional browser regression check against the isolated login_preview fixture.

Run fixture on loopback port 8513, then this script. Requires playwright and Edge.
Screenshots are generated in a temporary folder, not in the thesis/evidence files.
"""
import json
import re
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    output = Path(tempfile.mkdtemp(prefix='fsd_login_preview_'))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width':1280, 'height':900})
        page.goto('http://127.0.0.1:8513')
        username = page.get_by_label('Username', exact=True)
        password = page.get_by_label('Password', exact=True)
        username.wait_for()
        assert username.get_attribute('autocomplete') == 'username'
        assert password.get_attribute('autocomplete') == 'current-password'
        assert not username.get_attribute('placeholder')
        assert not password.get_attribute('placeholder')
        username.fill('examiner')
        password.fill('fixture-password')
        assert password.evaluate('(e) => getComputedStyle(e).outlineStyle') == 'none'
        outer = page.locator('[data-baseweb="input"]').nth(1)
        assert outer.evaluate('(e) => getComputedStyle(e).outlineStyle') == 'solid'
        hint = page.get_by_text(re.compile('Press Enter to submit'))
        assert not hint.count() or not hint.first.is_visible()
        toggle = outer.get_by_role('button')
        toggle.click()
        assert password.get_attribute('type') == 'text'
        toggle.click()
        assert password.get_attribute('type') == 'password'
        password.focus()
        password.press('Tab')
        assert toggle.evaluate('(e) => document.activeElement === e')
        assert toggle.evaluate('(e) => getComputedStyle(e).outlineStyle') == 'solid'
        password.focus()
        page.screenshot(path=str(output/'desktop.png'), full_page=True)
        password.press('Enter')
        page.get_by_text('Invalid username or password.', exact=True).wait_for()
        page.set_viewport_size({'width':390, 'height':844})
        password.focus()
        page.screenshot(path=str(output/'mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        box = page.locator('.st-key-login_panel').bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 390
        browser.close()
    print(json.dumps({'result':'passed', 'screenshots':str(output)}))


if __name__ == '__main__':
    main()
