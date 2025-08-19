import re
from playwright.sync_api import Page, expect


def test_example(page: Page) -> None:
    page.goto("https://www.bilibili.com/")
    page.locator("#nav-searchform div").first.click()
    page.get_by_role("textbox", name="凡人修仙传").click()
    page.get_by_role("textbox", name="凡人修仙传").fill("初见悠")
    with page.expect_popup() as page1_info:
        page.locator("#nav-searchform").get_by_role("img").nth(1).click()
    page1 = page1_info.value
    with page1.expect_popup() as page2_info:
        page1.locator(".info-card > a").click()
    page2 = page2_info.value
    page1.get_by_role("textbox", name="输入关键字搜索").click()
    page1.get_by_role("textbox", name="输入关键字搜索").fill("qwen3")
    page1.get_by_role("textbox", name="输入关键字搜索").press("Enter")
    page1.get_by_text("专栏99+").click()
    with page1.expect_popup() as page3_info:
        page1.get_by_role("link", name="Qwen3-Coder 实测：模型快得飞起，但更惊喜的是").click()
    page3 = page3_info.value
    page1.goto("https://search.bilibili.com/article?keyword=qwen3&from_source=webtop_search&spm_id_from=333.1007&search_source=5")
    page2.goto("https://space.bilibili.com/20304249?spm_id_from=333.337.0.0")
