"""
Scrape curriculum-detail pages using Playwright (browser required for Blackbaud CMS).
These pages return 403 with plain HTTP requests but load fine in a real browser.
"""

import json
import os
import time
from playwright.sync_api import sync_playwright

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "scraped")

DEPARTMENTS = [
    {"name": "Humanities", "url": "https://www.webb.org/curriculum-detail?fromId=296692&LevelNum=1273&DepartmentId=27432"},
    {"name": "Mathematics & Computer Science", "url": "https://www.webb.org/curriculum-detail?fromId=297521&LevelNum=1273&DepartmentId=23778"},
    {"name": "Science", "url": "https://www.webb.org/curriculum-detail?fromId=297521&LevelNum=1273&DepartmentId=23779"},
    {"name": "World Languages", "url": "https://www.webb.org/curriculum-detail?fromId=297521&LevelNum=1273&DepartmentId=23780"},
    {"name": "Fine Arts", "url": "https://www.webb.org/curriculum-detail?fromId=297521&LevelNum=1273&DepartmentId=23776"},
    {"name": "Health & Wellness", "url": "https://www.webb.org/curriculum-detail?fromId=297521&LevelNum=1273&DepartmentId=23860"},
]

JS_EXTRACT = """
() => {
    let result = {department: '', courses: [], faculty: []};

    // Department name from h1
    let h1 = document.querySelector('h1');
    if (h1) result.department = h1.textContent.trim();

    // Courses: each is an <li> with an <h2> heading
    document.querySelectorAll('li').forEach(li => {
        let h = li.querySelector('h2');
        if (!h) return;
        let title = h.textContent.trim();
        if (title.length < 5 || title === result.department) return;
        // Skip non-course h2s
        if (['Explore', 'Meet Our Faculty', 'Discover Webb'].some(s => title.startsWith(s))) return;
        let divs = li.querySelectorAll(':scope > div');
        let desc = '';
        divs.forEach(d => {
            let t = d.textContent.trim();
            if (t && t !== title) desc += t + ' ';
        });
        desc = desc.replace(/\\s+/g, ' ').trim();
        if (desc.length > 10) {
            result.courses.push(title + ': ' + desc);
        }
    });

    // Faculty with emails
    document.querySelectorAll('li').forEach(li => {
        let emailEl = Array.from(li.querySelectorAll('a')).find(a => a.textContent.includes('webb.org'));
        if (!emailEl) return;
        let lines = li.innerText.split('\\n').map(s => s.trim()).filter(s => s);
        let email = emailEl.textContent.trim();
        if (lines.length >= 3) {
            result.faculty.push({
                name: lines[0] + ' ' + lines[1],
                role: lines[2],
                education: lines.slice(3, lines.length - 1).join('; '),
                email: email
            });
        }
    });

    return result;
}
"""


def scrape_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for dept in DEPARTMENTS:
            print(f"\nScraping: {dept['name']}...")
            page.goto(dept["url"], wait_until="domcontentloaded")
            time.sleep(3)  # Wait for JS content to render

            data = page.evaluate(JS_EXTRACT)

            # Build text content for the knowledge base
            lines = []
            lines.append(f"Department: {data['department']}")
            lines.append(f"\n{'='*60}")
            lines.append(f"COURSES ({len(data['courses'])})")
            lines.append('='*60)
            for c in data['courses']:
                lines.append(f"\n{c}")

            lines.append(f"\n{'='*60}")
            lines.append(f"FACULTY ({len(data['faculty'])})")
            lines.append('='*60)
            for f in data['faculty']:
                lines.append(f"\n{f['name']} — {f['role']}")
                if f['education']:
                    lines.append(f"  Education: {f['education']}")
                lines.append(f"  Email: {f['email']}")

            content = '\n'.join(lines)

            # Save as JSON in the same format as other scraped pages
            slug = dept['name'].lower().replace(' & ', '_').replace(' ', '_')
            output = {
                "url": dept["url"],
                "title": f"Curriculum Detail — {data['department']}",
                "content": content,
            }
            out_path = os.path.join(OUTPUT_DIR, f"web_curriculum_{slug}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            print(f"  {data['department']}: {len(data['courses'])} courses, {len(data['faculty'])} faculty")
            print(f"  Saved: web_curriculum_{slug}.json ({len(content)} chars)")

        browser.close()

    print(f"\nDone. All departments saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    scrape_all()
