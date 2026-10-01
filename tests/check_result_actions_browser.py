"""Optional Edge/Playwright check; serve the isolated fixture on loopback:8514."""
import json
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright


def main():
    output = Path(tempfile.mkdtemp(prefix='fsd_action_layout_'))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page()
        page.goto('http://127.0.0.1:8514')
        page.get_by_role('button', name='Save case record', exact=True).wait_for()
        buttons = page.locator('.st-key-result_actions .stButton button:visible')
        for width in (1280, 800, 720, 390):
            page.set_viewport_size({'width':width, 'height':700})
            # Wait for layout on the next frame after viewport resize.
            page.evaluate('() => new Promise(requestAnimationFrame)')
            boxes = [buttons.nth(i).bounding_box() for i in range(3)]
            assert max(b['height'] for b in boxes) - min(b['height'] for b in boxes) < 1
            assert max(b['width'] for b in boxes) - min(b['width'] for b in boxes) < 2
            for i in range(3):
                assert buttons.nth(i).evaluate('(e) => e.scrollWidth <= e.clientWidth')
            if width > 760:
                assert max(b['y'] for b in boxes) - min(b['y'] for b in boxes) < 1
            else:
                assert boxes[1]['y'] >= boxes[0]['y'] + boxes[0]['height']
                assert boxes[2]['y'] >= boxes[1]['y'] + boxes[1]['height']
            page.screenshot(path=str(output/f'actions-{width}.png'))
        page.get_by_role('button', name='Save case record', exact=True).click()
        page.get_by_text('Case record saved. Reference: AN-PREVIEW', exact=True).wait_for()
        assert page.get_by_test_id('stException').count() == 0
        browser.close()
    print(json.dumps({'result':'passed', 'screenshots':str(output)}))


if __name__ == '__main__':
    main()
