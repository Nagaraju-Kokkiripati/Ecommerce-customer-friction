"""Optional real-browser smoke test: pip install playwright, then run this file.

Uses installed Edge headlessly and an isolated SQLite database.
"""
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8766"

with tempfile.TemporaryDirectory() as directory:
    env = os.environ.copy()
    env.update(DEBUG="false", DATA_DIR=directory)
    process = subprocess.Popen([str(ROOT / "venv/Scripts/python.exe"), "-m", "uvicorn", "api.main:app", "--port", "8766"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if requests.get(BASE + "/api/health", timeout=1).ok:
                    break
            except requests.RequestException:
                time.sleep(.1)
        else:
            raise RuntimeError("Test server did not start")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", headless=True)
            page = browser.new_page(viewport={"width": 1360, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/shop")
            expect(page.locator(".product")).to_have_count(6)
            page.get_by_role("button", name="Sign in", exact=True).first.click()
            form = page.locator("#signup-form")
            form.locator('[name="name"]').fill("Browser Customer")
            form.locator('[name="email"]').fill("browser@example.com")
            form.locator('[name="password"]').fill("browser-password")
            form.locator('[name="consent"]').check()
            form.get_by_role("button", name="Create account").click()
            expect(page.locator("#account-button")).to_have_text("Browser Customer")
            page.locator('[data-view="p1"]').click()
            expect(page.locator("#product-dialog")).to_be_visible()
            page.locator("#close-product").click()
            page.locator('[data-add="p1"]').click()
            expect(page.locator("#cart-count")).to_have_text("1")
            page.locator("#cart-button").click()
            page.locator("#checkout-button").click()
            page.locator("#address").fill("123 Browser Demo Street")
            page.locator("#outcome").select_option("failure")
            for _ in range(2):
                with page.expect_response(lambda r: r.url.endswith('/api/shop/payment')) as response:
                    page.get_by_role("button", name="Simulate payment").click()
                assert response.value.ok
            admin = browser.new_page()
            admin.on("pageerror", lambda error: errors.append(str(error)))
            admin.goto(BASE + "/admin/journeys")
            admin.locator('[name="username"]').fill("admin")
            admin.locator('[name="password"]').fill("admin123")
            admin.get_by_role("button", name="Sign in", exact=True).click()
            admin.get_by_role("button", name="Inspect").first.click()
            expect(admin.locator("#facts")).to_contain_text("2 simulated payment failures")
            admin.locator("#record-recovery").click()
            expect(admin.locator("#recovery-history")).to_contain_text("1 simulated recovery actions")
            page.locator("#outcome").select_option("success")
            page.get_by_role("button", name="Simulate payment").click()
            expect(page.locator("#orders")).to_contain_text("Confirmed (demo)")
            admin.locator("#refresh").click()
            expect(admin.locator("#recovery-history")).to_contain_text("purchase after simulated action")
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            browser.close()
            print("Browser journey passed: signup, view, cart, two failures, recovery, order, mobile layout.")
    finally:
        process.terminate()
        process.wait(timeout=10)
