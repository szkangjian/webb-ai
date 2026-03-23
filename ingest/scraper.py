"""
Webb Schools website scraper.
Uses the complete sitemap to fetch all known pages directly.
No recursive crawling needed - the site is ~60 static pages.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urlparse

BASE_URL = "https://www.webb.org"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "scraped")

# Complete URL list from webb.org/page/view-our-sitemap
ALL_URLS = [
    # Home
    "/",
    # Admission
    "/admission",
    "/admission/why-webb",
    "/admission/our-location",
    "/admission/our-location/travel-and-accommodations",
    "/admission/tuition-and-financial-aid",
    "/admission/how-to-apply",
    "/admission/family-guide",
    "/admission/admission-events",
    "/admission/campus-tour",
    "/admission/welcome-from-the-admission-director",
    "/admission/meet-the-admission-fellows",
    "/admission/meet-the-admission-team",
    # About
    "/about",
    "/about/mission",
    "/about/school-leadership",
    "/about/culture-and-community",
    "/about/news",
    "/about/news/press-releases",
    "/about/directory",
    "/about/publications",
    "/about/employment",
    # Academics
    "/academics",
    "/academics/core-program-grades-9-and-10",
    "/academics/grades-11-and-12",
    "/academics/unique-learning-experiences",
    "/academics/math-at-webb",
    "/academics/science-at-webb",
    "/academics/humanities-at-webb",
    "/academics/world-languages-at-webb",
    "/academics/fine-arts-at-webb",
    "/academics/alf-museum",
    "/academics/college-guidance",
    "/academics/meet-our-faculty",
    "/academics/course-catalog",
    # Student Life
    "/student-life",
    "/student-life/dining",
    "/student-life/dorm-life",
    "/student-life/after-school-and-weekends",
    "/student-life/health-and-wellness",
    "/student-life/travel-opportunities",
    "/student-life/chapel-program",
    "/student-life/community-impact",
    "/student-life/clubs-and-affinity-groups",
    "/student-life/student-leadership",
    # Athletics
    "/athletics",
    "/athletics/summer-practices",
    "/athletics/cif-championships",
    "/athletics/league-championships",
    "/athletics/school-records",
    # Summer
    "/summer",
    "/summer/program-tracks",
    "/summer/program-brochure",
    # Giving
    "/giving",
    "/giving/ways-of-giving",
    "/giving/the-webb-fund",
    "/giving/legacy-hall-of-fame",
    "/giving/thompson-and-vivian-webb-society",
    "/giving/endowed-funds",
    "/giving/advancement-team",
    # Alf Museum
    "/alf-museum",
    # Alumni
    "/alumni",
    "/alumni/upcoming-events",
    "/alumni/alumni-weekend",
    "/alumni/alumni-council",
    "/alumni/alumni-awards",
    "/alumni/alumni-athletes",
    # Acceptances
    "/acceptances",
    # Privacy policy
    "/privacy-policy",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; WebbAI-Bot/1.0; educational use)"
}


def clean_text(soup):
    """Remove nav, footer, scripts and return clean page text."""
    for tag in soup(["nav", "footer", "script", "style", "header", "aside", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def scrape_page(url):
    """Fetch and extract content from a single URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"  HTTP {response.status_code} - skipped")
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title else url
        text = clean_text(soup)
        if len(text) < 100:
            print(f"  Too short ({len(text)} chars) - skipped")
            return None
        return {"url": url, "title": title, "content": text}
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def url_to_filename(path):
    clean = path.strip("/").replace("/", "_") or "home"
    return f"web_{clean[:80]}.json"


def scrape_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Clear old web files
    existing = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("web_")]
    if existing:
        print(f"Removing {len(existing)} old web files...")
        for f in existing:
            os.remove(os.path.join(OUTPUT_DIR, f))

    print(f"Fetching {len(ALL_URLS)} pages from webb.org...\n")
    saved = 0

    for i, path in enumerate(ALL_URLS, 1):
        url = BASE_URL + path
        print(f"[{i}/{len(ALL_URLS)}] {path}")
        result = scrape_page(url)

        if result:
            filename = url_to_filename(path)
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            saved += 1
            print(f"  Saved: {result['title'][:60]} ({len(result['content'])} chars)")

        time.sleep(0.3)

    print(f"\nDone. Saved {saved}/{len(ALL_URLS)} pages.")


if __name__ == "__main__":
    scrape_all()
