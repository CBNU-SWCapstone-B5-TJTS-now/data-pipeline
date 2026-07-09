"""
vm-03 로컬에서 headless 브라우저(playwright)로 대시보드 화면을 캡처해
docs/screenshots/의 기존 파일들을 덮어쓴다.
브라우저 스크린샷 도구가 vm-03과 별개 환경이라 파일시스템 접근이 안 되기 때문에,
vm-03 안에서 직접 렌더링/캡처하는 방식으로 대체.

주의:
- 뷰포트 크기 그대로 찍으면 카드/차트가 중간에 잘린다. chrome-headless-shell 빌드는
  page.screenshot(full_page=True)도 실제로는 뷰포트 크기 그대로 찍혀서(스크롤 전체를
  담지 못함) 소용이 없었다 -> 대신 문서 실제 높이(scrollHeight)만큼 뷰포트 자체를
  늘려서(resize_to_full_height) 스크롤 없이 한 번에 담는 방식을 쓴다.
- "탭 전체" 샷(track_a_dashboard, project_overview)은 늘어난 뷰포트 그대로 캡처.
- "특정 섹션만" 샷(track_b_dashboard, track_b_map, track_b_weather)은 늘어난
  뷰포트 안에서 대상 카드의 실제 bounding box를 계산해 clip으로 잘라낸다
  (뷰포트를 이미 늘려놨기 때문에 스크롤 위치와 무관하게 좌표가 안정적이다).
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


def resize_to_full_height(page, min_height=1000, padding=40):
    """문서 실제 높이만큼 뷰포트 자체를 늘려서 스크롤 없이 전체를 한 화면에 담는다.
    document.body.scrollHeight는 Streamlit 앱에서 0을 반환한다 — 실제 스크롤 컨테이너인
    [data-testid="stMain"]의 scrollHeight를 써야 한다."""
    height = page.evaluate('document.querySelector("[data-testid=stMain]").scrollHeight')
    page.set_viewport_size({"width": 1600, "height": max(height + padding, min_height)})
    time.sleep(1)


def clip_from_top_of(start_locator, end_locator, padding=16):
    """start_locator 상단부터 end_locator 하단까지를 clip 영역으로 계산 (뷰포트 기준 좌표)"""
    start_box = start_locator.bounding_box()
    end_box = end_locator.bounding_box()
    x = min(start_box["x"], end_box["x"]) - padding
    y = start_box["y"] - padding
    right = max(start_box["x"] + start_box["width"], end_box["x"] + end_box["width"]) + padding
    bottom = end_box["y"] + end_box["height"] + padding
    return {"x": max(x, 0), "y": max(y, 0), "width": right - x, "height": bottom - y}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(2)

        click_dark_mode(page)  # 다크모드로 전환 (기존 스크린샷과 톤 맞춤)

        # ---- 트랙 A: 탭 전체 (잘림 없이 끝까지) ----
        click_tab(page, "Trust Score")
        resize_to_full_height(page)
        page.screenshot(path=f"{OUT_DIR}/track_a_dashboard.png")
        print("saved track_a_dashboard.png")

        # ---- 트랙 B ----
        click_tab(page, "혼잡도 패턴")
        time.sleep(3)  # folium iframe 로딩 대기 (뷰포트 늘리기 전에 충분히 기다려야 scrollHeight가 정확함)
        resize_to_full_height(page, padding=120)
        time.sleep(1)

        # 상단(히어로+통계+히트맵)만: 페이지 최상단부터 히트맵 카드 하단까지
        top_anchor = page.get_by_text("NOWHERE DATA PIPELINE")
        heatmap_card = page.get_by_text("언제 어디가 가장 붐빌까요").locator(
            "xpath=ancestor::div[contains(@class,'section-card')]"
        ).first
        clip = clip_from_top_of(top_anchor, heatmap_card)
        page.screenshot(path=f"{OUT_DIR}/track_b_dashboard.png", clip=clip)
        print("saved track_b_dashboard.png")

        # 지도 섹션만: 카드 제목부터 지도 하단까지
        map_title = page.get_by_text("장소별 지도")
        map_iframe = page.locator('iframe[title="streamlit_folium.st_folium"]')
        clip = clip_from_top_of(map_title, map_iframe)
        page.screenshot(path=f"{OUT_DIR}/track_b_map.png", clip=clip)
        print("saved track_b_map.png")

        # 날씨 섹션만: 카드 제목부터 표 하단까지
        weather_title = page.get_by_text("날씨 관측 데이터")
        weather_table = page.locator('div[data-testid="stDataFrame"]').last
        clip = clip_from_top_of(weather_title, weather_table)
        page.screenshot(path=f"{OUT_DIR}/track_b_weather.png", clip=clip)
        print("saved track_b_weather.png")

        # ---- 프로젝트 개요: 탭 전체 (잘림 없이 끝까지) ----
        click_tab(page, "프로젝트 개요")
        resize_to_full_height(page)
        page.screenshot(path=f"{OUT_DIR}/project_overview.png")
        print("saved project_overview.png")

        browser.close()


if __name__ == "__main__":
    main()
