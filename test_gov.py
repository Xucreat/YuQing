import requests
from bs4 import BeautifulSoup

url = "https://www.lfdc.gov.cn/jrdc.jhtml"
r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
r.encoding = r.apparent_encoding
print(f"Status: {r.status_code}, Length: {len(r.text)}")

soup = BeautifulSoup(r.text, "html.parser")
links = soup.select("a[href*='.jhtml']")
print(f"Links with .jhtml: {len(links)}")
for a in links[:5]:
    href = a.get("href", "")[:80]
    title = (a.get("title") or a.get_text(strip=True))[:50]
    print(f"  {title} | {href}")
