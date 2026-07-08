"""
vm-03 로컬에서 headless 브라우저(playwright)로 대시보드 화면을 캡처해
docs/screenshots/의 기존 파일들을 덮어쓴다.
brwoser 스크린샷 도구가 vm-03과 별개 환경이라 파일시스템 접근이 안 되기 때문에,
vm-03 안에서 직접 렌더링/캡처하는 방식으로 대체.
"""
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"
OUT_DIR = "docs/screenshots"


def click_dark_mode(page):
    btn = page.get_by_role("button", name="🌙")
    btn.click(force=True)
    time.sleep(2)


def click_tab(page, label_substring):
    tab = page.get_by_role("tab", name=label_substring)
    tab.click()
    time.sleep(1.5)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(2)

        click_dark_mode(page)  # 다크모드로 전환 (기존 스크린샷과 톤 맞춤)

        # ---- 트랙 A ----
        click_tab(page, "Trust Score")
        page.screenshot(path=f"{OUT_DIR}/track_a_dashboard.png")
        print("saved track_a_dashboard.png")

        # ---- 트랙 B: 히트맵(상단) ----
        click_tab(page, "혼잡도 패턴")
        page.screenshot(path=f"{OUT_DIR}/track_b_dashboard.png")
        print("saved track_b_dashboard.png")

        # ---- 트랙 B: 지도 ----
        page.get_by_text("장소별 지도").scroll_into_view_if_needed()
        time.sleep(2)  # folium iframe 로딩 대기
        page.screenshot(path=f"{OUT_DIR}/track_b_map.png")
        print("saved track_b_map.png")

        # ---- 트랙 B: 날씨 ----
        page.get_by_text("날씨 관측 데이터").scroll_into_view_if_needed()
        time.sleep(1)
        page.screenshot(path=f"{OUT_DIR}/track_b_weather.png")
        print("saved track_b_weather.png")

        # ---- 프로젝트 개요 ----
        click_tab(page, "프로젝트 개요")
        page.screenshot(path=f"{OUT_DIR}/project_overview.png")
        print("saved project_overview.png")

        browser.close()


if __name__ == "__main__":
    main()
