import os
import re
import html
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

BASE_URL = "https://www.apkmirror.com"
RELEASE_HTML_FILE = "playstore_release.html"

# Fallback local variant HTML file
# Save the chosen variant page source from your browser with this name
FALLBACK_VARIANT_HTML_FILE = "playstore_variant.html"

client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["apkmirror"]
collection = db["apps"]


def load_view_source_html(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    matches = re.findall(r'<td class="line-content">(.*?)</td>', raw, flags=re.DOTALL)
    joined = "\n".join(matches)
    joined = re.sub(r"<[^>]+>", "", joined)
    joined = html.unescape(joined)

    return joined


def extract_title(clean_html):
    match = re.search(r"<title>(.*?)</title>", clean_html, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return "unknown"


def extract_variant_links(clean_html):
    links = re.findall(r'href="([^"]+android-apk-download[^"]*)"', clean_html, flags=re.IGNORECASE)

    cleaned = []
    seen = set()

    for link in links:
        full_link = link

        if full_link.startswith("/"):
            full_link = BASE_URL + full_link

        full_link = full_link.split("#")[0]

        if full_link not in seen:
            seen.add(full_link)
            cleaned.append(full_link)

    return cleaned


def choose_variant(variant_links):
    for link in variant_links:
        if "universal" in link.lower():
            return link

    if variant_links:
        return variant_links[0]

    return None


def fetch_live_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.apkmirror.com/"
    }

    response = requests.get(url, headers=headers, timeout=30)

    print("\n[*] Fetching variant page...")
    print("URL:", url)
    print("Status:", response.status_code)

    return response.status_code, response.text


def extract_metadata_from_live_html(page_html, url):
    soup = BeautifulSoup(page_html, "html.parser")
    text = soup.get_text("\n", strip=True)

    metadata = {}

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "unknown"

    package_match = re.search(r"Package:\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    if package_match:
        metadata["Package Name"] = package_match.group(1).strip()

    version_match = re.search(r"Version:\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    if version_match:
        metadata["Version"] = version_match.group(1).strip()

    android_match = re.search(r"Min:\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    if android_match:
        metadata["Requires Android"] = android_match.group(1).strip()

    arch_match = re.search(r"Architecture:\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    if arch_match:
        metadata["Architecture"] = arch_match.group(1).strip()

    dpi_match = re.search(r"Screen DPI:\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    if dpi_match:
        metadata["DPI"] = dpi_match.group(1).strip()

    sha1_match = re.search(r"SHA1:\s*([A-Fa-f0-9]{8,})", text, flags=re.IGNORECASE)
    if sha1_match:
        metadata["File SHA1"] = sha1_match.group(1).strip()

    uploaded_match = re.search(r"Uploaded:\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    if uploaded_match:
        metadata["Uploaded"] = uploaded_match.group(1).strip()

    bundle_match = re.search(r"([A-Za-z0-9._\-]+_apkmirror\.com\.apkm)", text, flags=re.IGNORECASE)
    if bundle_match:
        metadata["Bundle Filename"] = bundle_match.group(1).strip()
        metadata["File Type"] = "apkm"
    else:
        metadata["File Type"] = "apk"

    if "Package Name" not in metadata:
        slug_match = re.search(r"/apk/([^/]+)/([^/]+)/", url)
        if slug_match:
            metadata["Developer Slug"] = slug_match.group(1)
            metadata["App Slug"] = slug_match.group(2)

    return title, metadata


def extract_metadata_from_saved_variant_file(filepath):
    clean_html = load_view_source_html(filepath)

    title = extract_title(clean_html)
    metadata = {}

    patterns = {
        "Package Name": r"Package:\s*([^\n\r<]+)",
        "Version": r"Version:\s*([A-Za-z0-9._\-()+ ]+)",
        "Requires Android": r"(?:Min:|Requires Android:)\s*([^\n\r<]+)",
        "Architecture": r"Architecture:\s*([^\n\r<]+)",
        "DPI": r"Screen DPI:\s*([^\n\r<]+)",
        "File SHA1": r"SHA1:\s*([A-Fa-f0-9]{8,})",
        "Uploaded": r"Uploaded:\s*([^\n\r<]+)"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, clean_html, flags=re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()

    bundle_match = re.search(
        r"([A-Za-z0-9._\-]+_apkmirror\.com\.apkm)",
        clean_html,
        flags=re.IGNORECASE
    )
    if bundle_match:
        metadata["Bundle Filename"] = bundle_match.group(1).strip()
        metadata["File Type"] = "apkm"
    else:
        metadata["File Type"] = "apk"

    if title != "unknown":
        version_from_title = re.match(r"^(.*?)\s+APK Download", title, flags=re.IGNORECASE)
        if version_from_title:
            metadata["Version"] = version_from_title.group(1).strip()

    return title, metadata


def build_document(title, metadata, chosen_variant):
    package_name = metadata.get("Package Name", "unknown")
    version = metadata.get("Version", "unknown")
    variant = chosen_variant

    doc = {
        "title": title,
        "version": version,
        "variant": variant,
        "package_name": package_name,
        "file_path": "",
        "added_at": datetime.utcnow(),
        "metadata": metadata
    }

    return doc


def insert_if_new(doc):
    existing = collection.find_one({
        "package_name": doc["package_name"],
        "version": doc["version"],
        "variant": doc["variant"]
    })

    if existing:
        print("\n[-] Document already exists in MongoDB")
        return

    collection.insert_one(doc)
    print("\n[+] Inserted MongoDB document")


def run_crawler():
    print("[*] Reading local release HTML file...")

    clean_html = load_view_source_html(RELEASE_HTML_FILE)

    title = extract_title(clean_html)
    variant_links = extract_variant_links(clean_html)

    print("\n[+] Release Title:")
    print(title)

    print("\n[+] Variant links found:")
    if variant_links:
        for i, link in enumerate(variant_links, start=1):
            print("{}: {}".format(i, link))
    else:
        print("No variant links found.")
        return

    chosen = choose_variant(variant_links)

    print("\n[+] Chosen variant:")
    print(chosen if chosen else "None")

    if not chosen:
        return

    status_code, variant_html = fetch_live_html(chosen)

    if status_code == 200:
        print("\n[+] Using live variant page")
        parsed_title, metadata = extract_metadata_from_live_html(variant_html, chosen)
    else:
        print("\n[-] Live fetch failed, trying local fallback file...")

        if not os.path.exists(FALLBACK_VARIANT_HTML_FILE):
            print("[-] Fallback file not found:", FALLBACK_VARIANT_HTML_FILE)
            print("[-] Save the chosen variant page source locally with that filename and run again.")
            return

        print("[+] Using local fallback file:", FALLBACK_VARIANT_HTML_FILE)
        parsed_title, metadata = extract_metadata_from_saved_variant_file(FALLBACK_VARIANT_HTML_FILE)

    print("\n[+] Parsed Title:")
    print(parsed_title)

    print("\n[+] Parsed Metadata:")
    if metadata:
        for k, v in metadata.items():
            print("{}: {}".format(k, v))
    else:
        print("No metadata found.")

    doc = build_document(parsed_title, metadata, chosen)
    insert_if_new(doc)