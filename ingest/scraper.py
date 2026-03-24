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
    # --- Pages discovered missing 2026-03-23 ---
    # Head of School, College Guidance Profile, Faculty Awards, Policies
    "/from-the-head-of-school",
    "/college-guidance-profile-202425",
    "/faculty-awards",
    "/welcome-back",
    "/orientation-schedule",
    "/non-discrimination-policy",
    "/game-program",
    # Curriculum detail pages (6 departments)
    "/curriculum-detail?DepartmentId=27432",   # Humanities
    "/curriculum-detail?DepartmentId=23778",   # Mathematics & Computer Science
    "/curriculum-detail?DepartmentId=23779",   # Science
    "/curriculum-detail?DepartmentId=23780",   # World Languages
    "/curriculum-detail?DepartmentId=23776",   # Fine Arts
    "/curriculum-detail?DepartmentId=23860",   # Health & Wellness
    # Athletic team pages (33 teams)
    "/athletic-teams?Team=171408",   # Football Varsity
    "/athletic-teams?Team=171410",   # Cross Country Varsity Boys
    "/athletic-teams?Team=171411",   # Cross Country Varsity Girls
    "/athletic-teams?Team=171416",   # Tennis JV Girls
    "/athletic-teams?Team=171417",   # Tennis Varsity Girls
    "/athletic-teams?Team=171419",   # Golf Varsity Girls
    "/athletic-teams?Team=171420",   # Volleyball Frosh Girls
    "/athletic-teams?Team=171421",   # Volleyball JV Girls
    "/athletic-teams?Team=171422",   # Volleyball Varsity Girls
    "/athletic-teams?Team=171423",   # Water Polo JV Boys
    "/athletic-teams?Team=171424",   # Water Polo Varsity Boys
    "/athletic-teams?Team=171425",   # Triathlon
    "/athletic-teams?Team=171426",   # Basketball JV Girls
    "/athletic-teams?Team=171427",   # Basketball Varsity Girls
    "/athletic-teams?Team=171429",   # Soccer Varsity Girls
    "/athletic-teams?Team=171431",   # Water Polo Varsity Girls
    "/athletic-teams?Team=171432",   # Wrestling
    "/athletic-teams?Team=171433",   # Basketball Frosh Boys
    "/athletic-teams?Team=171434",   # Basketball JV Boys
    "/athletic-teams?Team=171435",   # Basketball Varsity Boys
    "/athletic-teams?Team=171436",   # Soccer JV Boys
    "/athletic-teams?Team=171437",   # Soccer Varsity Boys
    "/athletic-teams?Team=171440",   # Badminton Varsity
    "/athletic-teams?Team=171445",   # Softball Varsity Girls
    "/athletic-teams?Team=171446",   # Baseball Varsity Boys
    "/athletic-teams?Team=171447",   # Golf Varsity Boys
    "/athletic-teams?Team=171448",   # Tennis JV Boys
    "/athletic-teams?Team=171449",   # Tennis Varsity Boys
    "/athletic-teams?Team=171451",   # Volleyball Varsity Boys
    "/athletic-teams?Team=284199",   # Swimming & Diving Varsity Girls
    "/athletic-teams?Team=284202",   # Swimming & Diving Varsity Boys
    "/athletic-teams?Team=312662",   # Track & Field Varsity Girls
    "/athletic-teams?Team=312663",   # Track & Field Varsity Boys
    # Club & affinity group detail pages (full lists)
    "/page/list-detail?pk=218155&fromId=296635",   # 2025 Clubs (82 clubs)
    "/page/list-detail?pk=218156&fromId=296635",   # Affinity & DEIB Groups (18 groups)
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
    content = "\n".join(lines)

    # Remove boilerplate that Blackbaud CMS injects as text (not in semantic tags)
    # 1. Navigation menu block (appears at start of every page)
    import re
    # Cut everything before the cookie notice or main content
    for marker in [
        "This website uses cookies",
        "Skip to Content",
    ]:
        idx = content.find(marker)
        if idx > 0:
            # Find the end of the cookie/nav block
            end = content.find("\n", idx + len(marker))
            if end > 0:
                content = content[end:].strip()
            break

    # 2. Remove remaining nav-like lines at the top (menu, arrow, section names)
    nav_keywords = {
        "menu", "arrow", "myWebb", "X",
        "Admission", "About", "Academics", "Student Life", "Athletics",
        "Summer", "Giving", "Alf Museum", "Alumni",
    }
    cleaned_lines = []
    in_nav = True
    for line in content.split("\n"):
        stripped = line.strip()
        if in_nav:
            # Skip lines that are just nav keywords or very short nav items
            if stripped in nav_keywords or stripped == "Search":
                continue
            # Stop skipping once we hit a substantial line
            if len(stripped) > 60 or (len(stripped) > 20 and stripped not in nav_keywords):
                in_nav = False
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    content = "\n".join(cleaned_lines)

    # 3. Remove footer boilerplate at the end
    footer_markers = [
        "Discover Webb",
        "Contact Us\n",
        "©",
        "Privacy Policy\n",
        "The Webb Schools\n1175 West Baseline",
    ]
    for marker in footer_markers:
        idx = content.find(marker)
        if idx > 0 and idx > len(content) * 0.5:  # only if in bottom 50%
            content = content[:idx].strip()
            break

    return content


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
    # Handle query parameters: /athletic-teams?Team=171408 → athletic-teams_Team-171408
    clean = path.strip("/").replace("/", "_").replace("?", "_").replace("=", "-") or "home"
    return f"web_{clean[:100]}.json"


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
