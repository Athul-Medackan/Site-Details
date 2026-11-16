"""
Website Summarizer
Usage:  python site_summarizer.py            (then type a site, e.g. abc.com)
        python site_summarizer.py abc.com
Install: pip install requests beautifulsoup4
"""

import re
import sys
from collections import Counter
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SiteSummarizer/1.0)"}

STOPWORDS = set("""
a an the and or but if then else for of to in on at by with from as is are was were be been being it its this that
these those i you he she we they them his her our your their my me us not no yes do does did done have has had having
will would can could should may might must about into over after before so than too very just also more most other some
such only own same up down out off again further once here there when where why how all any both each few
""".split())


def normalize_url(site: str) -> str:
    site = site.strip()
    if not site:
        raise ValueError("Please enter a site name.")
    if not re.match(r"^https?://", site, re.I):
        site = "https://" + site
    parsed = urlparse(site)
    if "." not in parsed.netloc:
        raise ValueError(f"'{site}' doesn't look like a valid site name.")
    return site


def fetch_html(url: str) -> tuple[str, str]:
    """Fetch the page; try https first, fall back to http."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.exceptions.SSLError:
        url = url.replace("https://", "http://", 1)
        resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text, resp.url


def get_meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def extract_content(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else ""
    description = get_meta(soup, "description", "og:description", "twitter:description")
    keywords = get_meta(soup, "keywords")
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])]
    headings = [h for h in headings if h][:8]

    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "aside", "svg"]):
        tag.decompose()

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "li"])]
    paragraphs = [p for p in paragraphs if len(p.split()) >= 6]
    body_text = " ".join(paragraphs)

    return {
        "title": title,
        "description": description,
        "keywords": keywords,
        "headings": headings,
        "text": body_text,
    }


def summarize_text(text: str, max_sentences: int = 5) -> list[str]:
    """Simple extractive summary: pick the highest-scoring sentences."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if 40 <= len(s.strip()) <= 400]
    if not sentences:
        return []

    words = re.findall(r"[a-zA-Z']+", text.lower())
    freq = Counter(w for w in words if w not in STOPWORDS and len(w) > 2)
    if not freq:
        return sentences[:max_sentences]

    scores = []
    for i, s in enumerate(sentences):
        tokens = [w for w in re.findall(r"[a-zA-Z']+", s.lower()) if w not in STOPWORDS]
        if not tokens:
            continue
        score = sum(freq[w] for w in tokens) / len(tokens)
        score *= 1.2 if i < 5 else 1.0  # slight boost for early sentences
        scores.append((score, i))

    top = sorted(scores, reverse=True)[:max_sentences]
    return [sentences[i] for _, i in sorted(top, key=lambda x: x[1])]


def summarize_site(site: str) -> str:
    url = normalize_url(site)
    html, final_url = fetch_html(url)
    data = extract_content(html)
    key_sentences = summarize_text(data["text"])

    lines = [f"Site:  {final_url}", f"Title: {data['title'] or 'N/A'}", ""]
    if data["description"]:
        lines += ["About:", f"  {data['description']}", ""]
    if data["headings"]:
        lines += ["Main topics:"] + [f"  - {h}" for h in data["headings"]] + [""]
    if key_sentences:
        lines += ["Summary:"] + [f"  * {s}" for s in key_sentences] + [""]
    if data["keywords"]:
        lines += [f"Keywords: {data['keywords']}"]
    if not (data["description"] or key_sentences):
        lines += ["Not enough readable text found (the site may load its content with JavaScript)."]
    return "\n".join(lines)


def main():
    site = sys.argv[1] if len(sys.argv) > 1 else input("Enter a site name (e.g. abc.com): ")
    try:
        print("\n" + summarize_site(site))
    except ValueError as e:
        print(f"Input error: {e}")
    except requests.exceptions.HTTPError as e:
        print(f"The site returned an error: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Could not reach the site: {e}")


if __name__ == "__main__":
    main()
