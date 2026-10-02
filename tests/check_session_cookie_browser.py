"""Optional Edge check for set, refresh/read, and clear session cookies."""
from playwright.sync_api import sync_playwright

ORIGIN = "http://127.0.0.1:8516"


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()

        page.goto(ORIGIN + "/?action=set")
        page.get_by_text("COOKIE=missing", exact=True).wait_for()
        page.wait_for_function(
            "document.cookie.includes('fsdxai_session_fixture=signed-fixture-value')"
        )

        page.goto(ORIGIN + "/?action=read")
        page.get_by_text("COOKIE=signed-fixture-value", exact=True).wait_for()

        page.goto(ORIGIN + "/?action=clear")
        page.wait_for_function(
            "!document.cookie.includes('fsdxai_session_fixture=')"
        )
        page.goto(ORIGIN + "/?action=read")
        page.get_by_text("COOKIE=missing", exact=True).wait_for()

        assert page.get_by_test_id("stException").count() == 0
        browser.close()
    print("session cookie browser check passed")


if __name__ == "__main__":
    main()
