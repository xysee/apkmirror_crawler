from bs4 import BeautifulSoup

HTML_FILE = "gemini_variant.html"

def run_crawler():
    print("[*] Reading local HTML file...")

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    if title_tag:
        print("[+] Title:")
        print(title_tag.get_text(strip=True))
    else:
        print("[-] Could not find h1 title")

    print("\n[+] First 10 links on page:")
    links = soup.find_all("a", href=True)

    for i, link in enumerate(links[:10], start=1):
        print("{}: {}".format(i, link["href"]))