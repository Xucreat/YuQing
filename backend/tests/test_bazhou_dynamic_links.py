from bs4 import BeautifulSoup

from app.collectors.generic_site import GenericSiteCollector


def test_bazhou_dynamic_link_rule_excludes_homepage_navigation():
    html = """
    <html><body>
      <a href="/xwzx/bzdt">霸州动态</a>
      <a href="http://xxgk.bazhou.gov.cn/index.do?templet=xzsp&flag=293">政务服务大厅</a>
      <a href="http://www.hbzwfw.gov.cn/hbzw/sxcx/itemList/fr_index.do">法人办事（按主题）</a>
      <a href="/xwzx/bzdt/content_34802">正常动态文章</a>
    </body></html>
    """
    collector = GenericSiteCollector(
        {
            "list_urls": ["https://www.bazhou.gov.cn/xwzx/bzdt"],
            "link_rule": {
                "href_regex": r"(?i)^/?xwzx/bzdt/content_\d+(?:\.html)?(?:\?.*)?$",
            },
        }
    )
    collector._get = lambda _url: html

    links = collector._collect_links()

    assert [item["title"] for item in links] == ["正常动态文章"]
    assert BeautifulSoup(html, "html.parser").find(string="政务服务大厅")
