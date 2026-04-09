import re
import html
from bs4 import BeautifulSoup
from datetime import datetime
from pymongo import MongoClient

client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["apkmirror"]
collection = db["apps"]

HTML_FILE = "gemini_variant.html"


def load_view_source_html(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    # Pull visible code lines out of the browser's "view source" wrapper
    matches = re.findall(r'<td class="line-content">(.*?)</td>', raw, flags=re.DOTALL)
    joined = "\n".join(matches)

    # Remove the viewer's span tags but keep their text
    joined = re.sub(r"<[^>]+>", "", joined)

    # Convert &lt;title&gt; back into <title>
    joined = html.unescape(joined)

    return joined


def extract_title(clean_html):
    match = re.search(r"<title>(.*?)</title>", clean_html, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return "unknown"
    
def extract_version_from_title(title):
    match = re.match(r"^(.*?)\s+APK Download", title, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_metadata(clean_html):
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

    return metadata


def run_crawler():
    print("[*] Reading local variant HTML file...")

    clean_html = load_view_source_html(HTML_FILE)

    title = extract_title(clean_html)
    metadata = extract_metadata(clean_html)

    version_from_title = extract_version_from_title(title)
    if version_from_title:
        metadata["Version"] = version_from_title

    print("\n[+] Title:")
    print(title)

    print("\n[+] Metadata found:")
    for k, v in metadata.items():
        print("{}: {}".format(k, v))
    
    package_name = metadata.get("Package Name", "unknown")
    version = metadata.get("Version", "unknown")
    variant = title

    doc = {
        "title": title,
        "version": version,
        "variant": variant,
        "package_name": package_name,
        "file_path": "",
        "added_at": datetime.utcnow(),
        "metadata": metadata
}

    existing = collection.find_one({
        "package_name": package_name,
        "version": version,
        "variant": variant
})

    if existing:
        print("\n[-] Document already exists in MongoDB")
    else:
        collection.insert_one(doc)
        print("\n[+] Inserted MongoDB document")