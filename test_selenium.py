"""
Selenium test suite – Event Registration System
TC1: Valid student login
TC2: Invalid login (wrong password)
TC3: Event listing + register for an event
TC4: Admin login
TC5: Admin views participants

Key design decisions:
  - do_login() navigates to /logout (not delete_all_cookies) to clear Flask session.
  - Login is performed by setting field values AND clicking the button via a
    single JS execute_script call. This is atomic, avoids send_keys race
    conditions, and uses JS .click() (not form.submit()) so Chrome fires the
    full form-submit event chain.
  - TC3 does an explicit driver.get("/events") after login to confirm the
    session cookie is valid before attempting registration.
  - Registration button is clicked via JS arguments[0].click() to stay in the
    Chrome renderer's normal event path.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE = "http://localhost:5000"

driver = webdriver.Chrome()
driver.maximize_window()
wait = WebDriverWait(driver, 10)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def do_login(user, pwd):
    """
    Clear Flask session via /logout, then atomically fill the login form
    and JS-click the submit button in a single execute_script call.
    Does NOT assert the outcome – callers decide what to wait for.
    """
    driver.get(BASE + "/logout")          # server-side session.clear()
    wait.until(EC.url_contains("/login"))  # confirm we're on login page
    wait.until(EC.presence_of_element_located((By.NAME, "username")))

    # Atomic: set both field values and click the button in one JS call.
    # Using .click() (not form.submit()) so the browser fires the full
    # submit event chain and properly stores the response Set-Cookie.
    driver.execute_script("""
        document.querySelector('input[name="username"]').value = arguments[0];
        document.querySelector('input[name="password"]').value = arguments[1];
        document.getElementById('loginBtn').click();
    """, user, pwd)


def login_as(user, pwd, url_fragment):
    """Submit login and wait for a successful URL change."""
    do_login(user, pwd)
    wait.until(EC.url_contains(url_fragment))


def report(name, ok):
    print(f"{name}: {'PASSED' if ok else 'FAILED'}")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

passed = []
failed = []

# ── TC1: Valid student login ─────────────────────────────────────────────────
try:
    login_as("student1", "pass123", "/events")
    ok = "Upcoming Events" in driver.page_source
    report("TC1 Student login", ok)
    (passed if ok else failed).append("TC1")
except Exception as e:
    print(f"TC1 Student login: FAILED ({e})")
    failed.append("TC1")

# ── TC2: Invalid login ───────────────────────────────────────────────────────
try:
    do_login("student1", "wrongpass")

    # Wait for EITHER: flash message stays on /login  OR  unexpected redirect.
    # We deliberately do NOT use find_element here (crashes Chrome 156 renderer).
    wait.until(lambda d:
        "Invalid username or password" in d.page_source
        or "/events" in d.current_url
        or "/admin" in d.current_url
    )

    still_on_login = "/login" in driver.current_url
    has_flash      = "Invalid username or password" in driver.page_source
    ok = still_on_login and has_flash

    print("\n--- TC2 DEBUG ---")
    print("Current URL:", driver.current_url)
    print("Flash in source:", has_flash)
    print("--- END TC2 DEBUG ---\n")

    report("TC2 Invalid login", ok)
    (passed if ok else failed).append("TC2")
except Exception as e:
    print(f"TC2 Invalid login: FAILED ({e})")
    failed.append("TC2")

# ── TC3: Event listing + registration ────────────────────────────────────────
try:
    login_as("student1", "pass123", "/events")

    # --- explicit session-validity check ---
    # Navigate to /events directly so we know the session cookie is active.
    # If it isn't, Flask redirects to /login and "Upcoming Events" won't appear,
    # surfacing the bug immediately rather than failing silently later.
    driver.get(BASE + "/events")
    wait.until(lambda d: "Upcoming Events" in d.page_source)
    print(f"TC3: events page confirmed — URL: {driver.current_url}")

    # Debug: show session cookie state
    cookies = driver.get_cookies()
    session_cookie = next((c for c in cookies if c.get("name") == "session"), None)
    print(f"TC3: session cookie present: {session_cookie is not None}")

    # Wait for all three register buttons
    wait.until(lambda d:
        len(d.find_elements(By.CSS_SELECTOR, "button[id^='reg-']")) == 3)
    buttons = driver.find_elements(By.CSS_SELECTOR, "button[id^='reg-']")
    print(f"TC3: found {len(buttons)} register buttons")

    btn = buttons[0]
    btn_id = btn.get_attribute("id")
    print(f"TC3: clicking button {btn_id}")

    # JS click on the button element (passes element as argument — no form.submit() quirks)
    driver.execute_script("arguments[0].click()", btn)

    # Flask handles duplicate registration gracefully (flashes message but
    # still redirects to confirmation page)
    wait.until(EC.url_contains("/confirmation/"))
    ok = "Registration Confirmed" in driver.page_source

    if not ok:
        print("TC3 DEBUG — URL:", driver.current_url)
        print("TC3 DEBUG — Source:", driver.page_source[:600])

    report("TC3 Event registration", ok)
    (passed if ok else failed).append("TC3")
    driver.save_screenshot("confirmation.png")

except Exception as e:
    print(f"TC3 DEBUG — URL: {driver.current_url}")
    print(f"TC3 DEBUG — Source: {driver.page_source[:600]}")
    print(f"TC3 Event registration: FAILED ({e})")
    failed.append("TC3")

# ── TC4: Admin login ─────────────────────────────────────────────────────────
try:
    login_as("admin", "admin123", "/admin")
    ok = "Admin Dashboard" in driver.page_source
    report("TC4 Admin login", ok)
    (passed if ok else failed).append("TC4")
except Exception as e:
    print(f"TC4 Admin login: FAILED ({e})")
    failed.append("TC4")

# ── TC5: Admin views participants ────────────────────────────────────────────
try:
    # Should be on /admin already from TC4
    wait.until(lambda d: "Admin Dashboard" in d.page_source)
    link = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "a[id^='view-']")))
    print(f"TC5: clicking link {link.get_attribute('id')}")
    driver.execute_script("arguments[0].click()", link)

    wait.until(EC.url_contains("/participants/"))
    ok = "Participants" in driver.page_source
    report("TC5 View participants", ok)
    (passed if ok else failed).append("TC5")
    driver.save_screenshot("participants.png")

except Exception as e:
    print(f"TC5 View participants: FAILED ({e})")
    failed.append("TC5")

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n========== RESULTS ==========")
print(f"PASSED ({len(passed)}): {', '.join(passed) if passed else 'none'}")
print(f"FAILED ({len(failed)}): {', '.join(failed) if failed else 'none'}")
print("=============================")

driver.quit()
