"""
LinkedIn Easy Apply Bot (Selenium)
==================================
Features:
- Semi-automated safe login: Log in manually once with your credentials / 2FA / OTP.
  Your Chrome profile is saved locally in 'chrome_profile', keeping you logged in.
- Anti-detection flags: Disables automation banners & masks navigator.webdriver.
- Easy Apply filter: Automatically searches with 'f_AL=true' for 1-click Easy Apply jobs.
- Title matching: Filters jobs by keywords in TITLE_INCLUDE and skips TITLE_EXCLUDE.
- Multi-step modal navigation:
    * Automatically advances through standard Next -> Review -> Submit steps.
    * If custom required questions or assessments appear, cleanly discards the modal
      and logs the job as 'needs_manual_review' so you can finish it manually later.
- Duplicate prevention: Tracks applied job URLs in applied_jobs.csv across runs.
- Rate limiting: Configurable max applications per run + random human-like delays.
"""

import csv
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ==============================================================================
# CONFIGURATION - Customize your job search preferences here
# ==============================================================================
KEYWORDS = [
    "python developer",
    "software engineer fresher",
    "junior software engineer",
    "full stack developer",
    "backend developer",
    "machine learning engineer",
]

LOCATION = "India"              # e.g., "India", "Bengaluru", "Hyderabad", "Remote", or ""
MAX_APPLIES_PER_RUN = 20        # Daily limit (recommended: 15-25 to keep LinkedIn account safe)
PAGES_PER_KEYWORD = 2           # Number of search result pages to scan per keyword (25 jobs/page)

# Title Filtering (lowercase):
# The job title MUST contain at least one of these words:
TITLE_INCLUDE = [
    "python", "java", "software", "developer", "engineer", "full stack",
    "fullstack", "backend", "frontend", "machine learning", "ml", "ai",
    "fresher", "junior", "associate", "intern"
]

# Skip any job whose title contains any of these words:
TITLE_EXCLUDE = [
    "senior", "sr.", "sr ", "lead", "manager", "architect", "principal",
    "director", "head of", "vp", "vice president", "staff", "sales", "hr"
]

# Delay between actions in seconds (randomized to mimic human browsing behavior)
DELAY_RANGE = (5, 9)

# Output files & local Chrome profile directory
LOG_FILE = Path("applied_jobs.csv")
PROFILE_DIR = str(Path.cwd() / "chrome_profile")
# ==============================================================================

# ==============================================================================
# XPATH / SELECTORS (Updated for LinkedIn's layout)
# ==============================================================================
EASY_APPLY_BTN_XPATH = (
    "//button[contains(@class, 'jobs-apply-button') and contains(., 'Easy Apply')] | "
    "//button[contains(@aria-label, 'Easy Apply')] | "
    "//button[normalize-space()='Easy Apply']"
)

ALREADY_APPLIED_XPATH = (
    "//*[contains(@class, 'artdeco-inline-feedback') and contains(., 'Applied')] | "
    "//span[normalize-space()='Applied'] | "
    "//span[contains(text(), 'Applied on') or contains(text(), 'Applied ')]"
)

MODAL_DIALOG_XPATH = "//div[@role='dialog' or contains(@class, 'jobs-easy-apply-modal')]"

SUBMIT_BTN_XPATH = (
    "//button[contains(normalize-space(), 'Submit application') or "
    "contains(@aria-label, 'Submit application')]"
)

REVIEW_BTN_XPATH = (
    "//button[contains(normalize-space(), 'Review') or "
    "contains(@aria-label, 'Review your application')]"
)

NEXT_BTN_XPATH = (
    "//button[contains(normalize-space(), 'Next') or "
    "contains(@aria-label, 'Continue to next step')]"
)

DISMISS_MODAL_XPATH = (
    "//button[@aria-label='Dismiss' or contains(@class, 'artdeco-modal__dismiss')]"
)

DISCARD_CONFIRM_XPATH = (
    "//button[contains(., 'Discard') or @data-control-name='discard_application_confirm_btn']"
)

APPLICATION_SENT_XPATH = (
    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'application sent') or "
    "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'your application was sent')]"
)

DONE_BTN_XPATH = "//button[contains(normalize-space(), 'Done') or @aria-label='Dismiss']"
# ==============================================================================


def pause(min_sec=None, max_sec=None):
    """Sleep for a random float interval within range."""
    lo, hi = (min_sec, max_sec) if min_sec is not None else DELAY_RANGE
    time.sleep(random.uniform(lo, hi))


def load_log():
    """Load previously applied URLs from CSV to avoid duplicate applications."""
    done = set()
    if LOG_FILE.exists():
        with LOG_FILE.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("url")
                if url:
                    done.add(url.strip())
    return done


def write_log(title, url, status):
    """Append application record to CSV file."""
    is_new = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["time", "title", "url", "status"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            title,
            url,
            status
        ])


def title_ok(title):
    """Check if the job title satisfies inclusion and exclusion rules."""
    t = title.lower()
    matches_include = any(k in t for k in TITLE_INCLUDE)
    matches_exclude = any(k in t for k in TITLE_EXCLUDE)
    return matches_include and not matches_exclude


def make_driver():
    """Configure and launch Chrome with anti-detection flags and persistent profile."""
    opts = webdriver.ChromeOptions()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    try:
        driver = webdriver.Chrome(options=opts)
    except WebDriverException as e:
        if "user data directory is already in use" in str(e).lower():
            print("\n[ERROR] Chrome profile is currently in use.")
            print("Please close any Chrome browser windows opened by this script previously and try again.\n")
        raise e

    # Mask navigator.webdriver in CDP
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            }
        )
    except Exception:
        pass

    return driver


def search_url(keyword, page):
    """Generate LinkedIn job search URL with Easy Apply filter enabled."""
    start = (page - 1) * 25
    params = {
        "keywords": keyword,
        "f_AL": "true",       # Easy Apply filter
        "sortBy": "R",        # Most relevant
        "start": str(start),
    }
    if LOCATION and LOCATION.strip():
        params["location"] = LOCATION.strip()
    query_string = "&".join(f"{k}={quote_plus(v)}" for k, v in params.items())
    return f"https://www.linkedin.com/jobs/search/?{query_string}"


def dismiss_modal_safely(driver):
    """Safely close and discard any open Easy Apply modal."""
    try:
        dismiss_btns = driver.find_elements(By.XPATH, DISMISS_MODAL_XPATH)
        if dismiss_btns:
            driver.execute_script("arguments[0].click();", dismiss_btns[0])
            time.sleep(1.5)

            # Look for 'Discard' confirmation button
            discard_btns = driver.find_elements(By.XPATH, DISCARD_CONFIRM_XPATH)
            if discard_btns:
                driver.execute_script("arguments[0].click();", discard_btns[0])
                time.sleep(1.5)
    except Exception:
        pass


def collect_jobs(driver, keyword, page):
    """Extract job titles and direct URLs from search results page."""
    url = search_url(keyword, page)
    driver.get(url)
    pause(3, 5)

    # Scroll through the jobs list container to trigger lazy loading of 25 cards
    try:
        for offset in [500, 1200, 2000, 2800]:
            driver.execute_script(f"window.scrollTo(0, {offset});")
            time.sleep(1)
            # Try scrolling inside the inner jobs list container if present
            driver.execute_script("""
                var container = document.querySelector('.jobs-search-results-list, .scaffold-layout__list');
                if (container) { container.scrollTop = container.scrollTop + 600; }
            """)
            time.sleep(0.5)
    except Exception:
        pass

    pause(1, 2)

    # Select all potential job link anchors
    link_selectors = [
        "a.job-card-list__title--link",
        "a.job-card-container__link",
        "a[data-control-name='job_card_click']",
        "li.jobs-search-results__list-item a[href*='/jobs/view/']",
        "a[href*='/jobs/view/']"
    ]

    elements = []
    for sel in link_selectors:
        found = driver.find_elements(By.CSS_SELECTOR, sel)
        if found:
            elements = found
            break

    jobs = []
    seen_ids = set()

    for el in elements:
        try:
            href = el.get_attribute("href")
            title = el.text.strip()
            if not title:
                title = el.get_attribute("aria-label") or el.get_attribute("title") or ""

            if href and "/jobs/view/" in href:
                # Extract clean job ID: /jobs/view/1234567890/
                match = re.search(r"/jobs/view/(\d+)", href)
                if match:
                    job_id = match.group(1)
                    if job_id not in seen_ids:
                        seen_ids.add(job_id)
                        clean_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                        clean_title = title.split("\n")[0].strip()
                        jobs.append((clean_title, clean_url))
        except Exception:
            continue

    return jobs


def apply_to_job(driver, title, url):
    """
    Open job URL, locate Easy Apply, and step through application modal.
    Returns status:
      - 'already_applied'
      - 'no_easy_apply_button'
      - 'applied'
      - 'needs_manual_review'
      - 'click_failed'
    """
    try:
        driver.get(url)
    except Exception:
        return "failed_opening_job"

    pause(3, 5)

    # 1. Check if already applied
    if driver.find_elements(By.XPATH, ALREADY_APPLIED_XPATH):
        return "already_applied"

    # 2. Locate Easy Apply button
    easy_apply_btns = driver.find_elements(By.XPATH, EASY_APPLY_BTN_XPATH)
    if not easy_apply_btns:
        return "no_easy_apply_button"

    # Click Easy Apply
    btn = easy_apply_btns[0]
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        pause(1, 2)
        btn.click()
    except WebDriverException:
        try:
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            return "click_failed"

    pause(2, 4)

    # 3. Handle modal wizard steps
    # We step through at most 6 iterations to prevent loops
    max_steps = 6
    step = 0

    while step < max_steps:
        step += 1
        pause(1.5, 3)

        # Check if already completed (Application sent)
        if driver.find_elements(By.XPATH, APPLICATION_SENT_XPATH):
            done_btns = driver.find_elements(By.XPATH, DONE_BTN_XPATH)
            if done_btns:
                driver.execute_script("arguments[0].click();", done_btns[0])
            return "applied"

        # Check for Submit application button
        submit_btns = driver.find_elements(By.XPATH, SUBMIT_BTN_XPATH)
        if submit_btns:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", submit_btns[0])
                pause(1, 2)
                submit_btns[0].click()
            except Exception:
                driver.execute_script("arguments[0].click();", submit_btns[0])

            pause(3, 5)
            # Close confirmation dialog if displayed
            done_btns = driver.find_elements(By.XPATH, DONE_BTN_XPATH)
            if done_btns:
                try:
                    driver.execute_script("arguments[0].click();", done_btns[0])
                except Exception:
                    pass
            return "applied"

        # Check for Review button
        review_btns = driver.find_elements(By.XPATH, REVIEW_BTN_XPATH)
        if review_btns:
            try:
                driver.execute_script("arguments[0].click();", review_btns[0])
                continue
            except Exception:
                pass

        # Check for Next button
        next_btns = driver.find_elements(By.XPATH, NEXT_BTN_XPATH)
        if next_btns:
            try:
                driver.execute_script("arguments[0].click();", next_btns[0])
                continue
            except Exception:
                pass

        # If neither Submit, Review, nor Next worked, there are required questions / file uploads
        break

    # If we reached here, custom questions or assessments are required.
    # Safely discard modal and mark for manual follow-up.
    dismiss_modal_safely(driver)
    return "needs_manual_review"


def main():
    print("=" * 65)
    print("           LINKEDIN EASY APPLY HELPER BOT            ")
    print("=" * 65)
    print(f"Keywords: {', '.join(KEYWORDS)}")
    print(f"Location: {LOCATION or 'Worldwide'}")
    print(f"Daily Limit: {MAX_APPLIES_PER_RUN} applications")
    print("=" * 65)

    done_urls = load_log()
    print(f"Loaded {len(done_urls)} previously processed jobs from {LOG_FILE.name}.")

    print("\nLaunching Chrome browser...")
    driver = make_driver()

    try:
        # Navigate to LinkedIn login
        driver.get("https://www.linkedin.com/login")

        print("\n" + "=" * 65)
        print("ACTION REQUIRED:")
        print("1. In the Chrome window that just opened, log in to your LinkedIn account.")
        print("2. Complete 2FA / OTP / Captcha verification if prompted.")
        print("3. Once you see your LinkedIn feed or profile, return here.")
        print("=" * 65)
        input("--> Press [ENTER] in this terminal when logged in to begin applying: ")

        applied_count = 0

        for keyword in KEYWORDS:
            if applied_count >= MAX_APPLIES_PER_RUN:
                print("\n[INFO] Reached max applications limit for this run.")
                break

            print(f"\n>>> Searching keyword: '{keyword}'")

            for page in range(1, PAGES_PER_KEYWORD + 1):
                if applied_count >= MAX_APPLIES_PER_RUN:
                    break

                jobs = collect_jobs(driver, keyword, page)
                print(f"  [Page {page}] Found {len(jobs)} Easy Apply jobs")

                if not jobs:
                    continue

                for title, url in jobs:
                    if applied_count >= MAX_APPLIES_PER_RUN:
                        break

                    if url in done_urls:
                        continue

                    # Filter title against include/exclude
                    if title and not title_ok(title):
                        continue

                    status = apply_to_job(driver, title, url)
                    done_urls.add(url)
                    write_log(title, url, status)

                    symbol = "✔" if status == "applied" else "ℹ"
                    print(f"    [{symbol}] {status:24} | {title[:45] if title else url}")

                    if status == "applied":
                        applied_count += 1
                        print(f"        (Total applied in this run: {applied_count}/{MAX_APPLIES_PER_RUN})")

                    pause()

    except KeyboardInterrupt:
        print("\n[STOPPED] Stopped by user (Ctrl+C).")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
    finally:
        print("\n" + "=" * 65)
        print("Execution finished.")
        print(f"Total new applications sent in this run: {applied_count}")
        print(f"Full history saved to: {LOG_FILE.resolve()}")
        print("=" * 65)
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
