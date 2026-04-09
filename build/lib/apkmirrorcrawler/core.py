from bs4 import BeautifulSoup

BASE_URL = "https://www.apkmirror.com"
HTML_FILE = "gemini_variant.html"


def find_intermediate_download_link(soup):
    links = soup.find_all("a", href=True)

    for link in links:
        href = link["href"]

        if "/download/" in href:
            if href.startswith("/"):
                return BASE_URL + href
            return href

    return None


def run_crawler():
    print("[*] Reading local HTML file...")

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    if title_tag:
        print("\n[+] Title:")
        print(title_tag.get_text(strip=True))
    else:
        print("\n[-] Could not find h1 title")

    download_link = find_intermediate_download_link(soup)

    if download_link:
        print("\n[+] Intermediate download link found:")
        print(download_link)
    else:
        print("\n[-] No intermediate download link found")