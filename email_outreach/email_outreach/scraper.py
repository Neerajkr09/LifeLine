"""
Website contact-email scraper.

Given a website URL, opens the homepage (and any contact/enquiry pages it can
find) in a headless Chrome session and extracts business-looking contact
email addresses, filtering out automated/system addresses and infrastructure
domains. Backs off cleanly ("HIGH_SECURITY") instead of trying to defeat a
CAPTCHA or bot-detection wall when a site is actively blocking automated
traffic.

This module is a straight port of the original Scraper.py, split out as an
importable package for use by pipeline.py, with the interactive CLI kept for
standalone/manual use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


# ============================================================
# CONFIGURATION
# ============================================================

class ScraperConfig:

    PAGE_LOAD_TIMEOUT = 20
    SCRIPT_TIMEOUT = 10

    CONTACT_KEYWORDS = (
        "contact us",
        "contact",
        "get in touch",
        "enquire now",
        "enquire",
        "enquiry",
        "get a quote",
        "request a quote",
        "contact-us",
        "contactus",
    )

    # Used to identify genuine block/challenge pages.
    SECURITY_PAGE_KEYWORDS = (
        "access denied",
        "request blocked",
        "verify you are human",
        "verify you're human",
        "checking your browser",
        "unusual traffic",
        "attention required",
        "security verification",
    )

    EMAIL_PATTERN = re.compile(
        r"[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    )


# ============================================================
# RESULT MODEL
# ============================================================

@dataclass
class ScrapeResult:
    status: str
    emails: List[str]
    contact_pages: List[str]
    message: str


# ============================================================
# BROWSER
# ============================================================

class BrowserFactory:

    @staticmethod
    def create():
        options = Options()

        # Run Chrome without opening a visible browser window.
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(ScraperConfig.PAGE_LOAD_TIMEOUT)
        driver.set_script_timeout(ScraperConfig.SCRIPT_TIMEOUT)
        return driver


# ============================================================
# URL UTILITIES
# ============================================================

class UrlUtils:

    @staticmethod
    def normalize(url: str) -> str:
        url = url.strip()
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    @staticmethod
    def is_same_domain(base_url: str, target_url: str) -> bool:
        base_domain = urlparse(base_url).netloc.lower().replace("www.", "")
        target_domain = urlparse(target_url).netloc.lower().replace("www.", "")
        return base_domain == target_domain


# ============================================================
# SECURITY DETECTOR
# ============================================================

class SecurityDetector:

    @staticmethod
    def is_security_block(driver) -> bool:
        title = (driver.title or "").lower()
        source = (driver.page_source or "").lower()  # noqa: F841 (kept for future use)

        for keyword in ScraperConfig.SECURITY_PAGE_KEYWORDS:
            if keyword in title:
                return True

        # Only inspect a limited amount of visible/page text. This prevents
        # normal JavaScript source containing "captcha" etc. from causing
        # false positives.
        try:
            visible_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        except WebDriverException:
            visible_text = ""

        combined_text = title + " " + visible_text

        matches = sum(
            1 for keyword in ScraperConfig.SECURITY_PAGE_KEYWORDS if keyword in combined_text
        )

        # Require multiple strong indicators rather than one random keyword.
        if matches >= 2:
            return True

        # Extremely short page + strong security wording.
        if len(visible_text) < 1000 and any(
            keyword in combined_text
            for keyword in (
                "access denied",
                "request blocked",
                "verify you are human",
                "checking your browser",
            )
        ):
            return True

        return False


# ============================================================
# EMAIL EXTRACTOR
# ============================================================

class EmailExtractor:

    EXCLUDED_DOMAINS = {
        "sentry.wixpress.com",
        "sentry-next.wixpress.com",
        "wixpress.com",
        "sentry.io",
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "localhost",
        "amazonses.com",
        "sendgrid.net",
        "mailgun.org",
        "mailgun.com",
    }

    EXCLUDED_LOCAL_PARTS = {
        "noreply",
        "no-reply",
        "no_reply",
        "donotreply",
        "do-not-reply",
        "do_not_reply",
        "mailer-daemon",
        "postmaster",
        "root",
        "test",
        "testing",
        "example",
        "user",
        "username",
        "yourname",
    }

    EXCLUDED_LOCAL_PART_KEYWORDS = {
        "sentry",
        "bounce",
        "mailer-daemon",
        "notification",
        "notifications",
        "automated",
        "automation",
        "tracking",
        "tracker",
        "analytics",
        "monitor",
        "monitoring",
        "error",
        "errors",
    }

    @staticmethod
    def extract_from_text(text: str) -> Set[str]:
        if not text:
            return set()

        matches = ScraperConfig.EMAIL_PATTERN.findall(text)
        emails = set()
        for email in matches:
            email = email.lower().strip().rstrip(".,;:!?)]}")
            if EmailExtractor.is_valid_business_email(email):
                emails.add(email)
        return emails

    @staticmethod
    def extract_from_mailto(driver) -> Set[str]:
        emails = set()
        try:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']")
            for link in links:
                href = link.get_attribute("href")
                if not href:
                    continue
                email = href.replace("mailto:", "", 1).split("?")[0].strip().lower()
                if EmailExtractor.is_valid_business_email(email):
                    emails.add(email)
        except WebDriverException:
            pass
        return emails

    @staticmethod
    def is_valid_business_email(email: str) -> bool:
        if not email:
            return False

        email = email.lower().strip()

        if "@" not in email:
            return False

        try:
            local_part, domain = email.rsplit("@", 1)
        except ValueError:
            return False

        if not local_part or not domain:
            return False

        if "." not in domain:
            return False

        if domain.startswith(".") or domain.endswith(".") or ".." in domain:
            return False

        if EmailExtractor.is_excluded_domain(domain):
            return False

        if local_part in EmailExtractor.EXCLUDED_LOCAL_PARTS:
            return False

        for keyword in EmailExtractor.EXCLUDED_LOCAL_PART_KEYWORDS:
            if keyword in local_part:
                return False

        placeholder_patterns = (
            "example@",
            "test@",
            "testing@",
            "sample@",
            "demo@",
            "fake@",
            "yourname@",
            "youremail@",
        )
        for pattern in placeholder_patterns:
            if email.startswith(pattern):
                return False

        if not ScraperConfig.EMAIL_PATTERN.fullmatch(email):
            return False

        return True

    @staticmethod
    def is_excluded_domain(domain: str) -> bool:
        domain = domain.lower().strip()

        if domain in EmailExtractor.EXCLUDED_DOMAINS:
            return True

        for excluded_domain in EmailExtractor.EXCLUDED_DOMAINS:
            if domain.endswith("." + excluded_domain):
                return True

        return False


# ============================================================
# CONTACT PAGE FINDER
# ============================================================

class ContactPageFinder:

    @staticmethod
    def find_pages(driver, base_url: str) -> List[str]:
        pages: List[str] = []

        try:
            links = driver.find_elements(By.TAG_NAME, "a")
        except WebDriverException:
            return pages

        for link in links:
            try:
                text = (link.text or "").strip().lower()
                href = link.get_attribute("href")
                if not href:
                    continue

                absolute_url = urljoin(base_url, href)

                if not UrlUtils.is_same_domain(base_url, absolute_url):
                    continue

                href_lower = absolute_url.lower()
                searchable_text = text + " " + href_lower

                matched = any(
                    keyword in searchable_text for keyword in ScraperConfig.CONTACT_KEYWORDS
                )

                if matched and absolute_url not in pages:
                    pages.append(absolute_url)

                if len(pages) >= 5:
                    break

            except WebDriverException:
                continue

        return pages


# ============================================================
# WEBSITE SCRAPER
# ============================================================

class WebsiteEmailScraper:

    def __init__(self):
        self.driver = None

    def scrape(self, url: str) -> ScrapeResult:
        url = UrlUtils.normalize(url)

        if not url:
            return ScrapeResult(
                status="INVALID_URL", emails=[], contact_pages=[], message="Invalid website URL."
            )

        try:
            self.driver = BrowserFactory.create()

            try:
                self.driver.get(url)
            except TimeoutException:
                pass  # a page-load timeout doesn't automatically mean blocked

            page_source = self.driver.page_source or ""
            if not page_source:
                return ScrapeResult(
                    status="UNAVAILABLE", emails=[], contact_pages=[], message="Website unavailable."
                )

            if SecurityDetector.is_security_block(self.driver):
                return ScrapeResult(
                    status="HIGH_SECURITY",
                    emails=[],
                    contact_pages=[],
                    message="High Security scrape not possible!",
                )

            emails = set()
            emails.update(EmailExtractor.extract_from_text(self.driver.page_source))
            emails.update(EmailExtractor.extract_from_mailto(self.driver))

            contact_pages = ContactPageFinder.find_pages(self.driver, url)

            for contact_url in contact_pages:
                try:
                    self.driver.get(contact_url)
                except TimeoutException:
                    pass

                if SecurityDetector.is_security_block(self.driver):
                    continue

                emails.update(EmailExtractor.extract_from_text(self.driver.page_source))
                emails.update(EmailExtractor.extract_from_mailto(self.driver))

            if emails:
                return ScrapeResult(
                    status="SUCCESS",
                    emails=sorted(emails),
                    contact_pages=contact_pages,
                    message="Scrape completed successfully.",
                )

            return ScrapeResult(
                status="NO_EMAIL", emails=[], contact_pages=contact_pages, message="No email address found."
            )

        except (WebDriverException, Exception) as error:  # noqa: BLE001
            return ScrapeResult(
                status="SCRAPE_ERROR", emails=[], contact_pages=[], message=f"Website could not be scraped: {error}"
            )

        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None


# ============================================================
# STANDALONE CLI (manual/debug use)
# ============================================================

def _display_result(result: ScrapeResult) -> None:
    print("\n" + "=" * 60)
    print(f"STATUS: {result.status}")
    print(f"MESSAGE: {result.message}")
    if result.contact_pages:
        print("\nContact / Enquiry pages:")
        for page in result.contact_pages:
            print(f" - {page}")
    if result.emails:
        print("\nEmails:")
        for email in result.emails:
            print(f" - {email}")
    print("=" * 60)


def main() -> None:
    website = input("\nEnter website URL: ").strip()
    scraper = WebsiteEmailScraper()
    result = scraper.scrape(website)
    _display_result(result)


if __name__ == "__main__":
    main()
