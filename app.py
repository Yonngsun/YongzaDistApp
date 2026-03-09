#streamlit run C:\Users\Administrator\PycharmProjects\PythonProject\app.py
import streamlit as st
import requests
import pandas as pd
import time
import sqlite3
import re
import folium
from streamlit_folium import st_folium

# ==============================
# 🔐 API KEY
# ==============================

CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]

GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
DIRECTION_URL = "https://maps.apigw.ntruss.com/map-direction/v1/driving"

HEADERS = {
    "x-ncp-apigw-api-key-id": CLIENT_ID,
    "x-ncp-apigw-api-key": CLIENT_SECRET
}

# API Key 네이버 Open API 추가
NAVER_OPEN_CLIENT_ID = st.secrets["NAVER_OPEN_CLIENT_ID"]
NAVER_OPEN_CLIENT_SECRET = st.secrets["NAVER_OPEN_CLIENT_SECRET"]

LOCAL_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"

# A이거는 헤더 추가 안해도 되나?>>>
# ==============================
# 📘 주소록 DB
# ==============================

def init_db():
    conn = sqlite3.connect("address.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            name TEXT PRIMARY KEY,
            road_address TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_all_addresses():
    conn = sqlite3.connect("address.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, road_address FROM addresses")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_saved_address(name):
    conn = sqlite3.connect("address.db")
    cursor = conn.cursor()
    cursor.execute("SELECT road_address FROM addresses WHERE name = ?", (name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_address(name, address):
    conn = sqlite3.connect("address.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO addresses VALUES (?, ?)", (name, address))
    conn.commit()
    conn.close()

def delete_address(name):
    conn = sqlite3.connect("address.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM addresses WHERE name = ?", (name,))
    conn.commit()
    conn.close()

init_db()


# =========================================================================
# 네이버 로컬서치를 활용한 주소 후보리스트 반환 함수(1.local search)
# ========================================================================


def search_place_candidates(query):

    headers = {
        "X-Naver-Client-Id": NAVER_OPEN_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_OPEN_CLIENT_SECRET
    }

    params = {
        "query": query.strip(),
        "display": 5,
        "sort": "random"
    }

    res = requests.get(LOCAL_SEARCH_URL, headers=headers, params=params)

    if res.status_code != 200:
        st.error(f"Open API 오류: {res.status_code}")
        return []

    data = res.json()
    results = []

    for item in data.get("items", []):

        # HTML 태그 제거
        title = re.sub('<.*?>', '', item["title"])

        road = item.get("roadAddress")
        jibun = item.get("address")

        # 도로명 우선
        address = road if road else jibun

        if address:
            results.append({
                "title": title,
                "road": road,
                "jibun": jibun,
                "address": address,
                "mapx": float(item["mapx"]) / 10000000,
                "mapy": float(item["mapy"]) / 10000000
            })

    return results
# =========================================================================
# 네이버 GEOCODE 활용한 주소 후보리스트 반환 함수(2.CEOCODE -> 주소검색)
# ========================================================================

def search_address_candidates(query):

    params = {
        "query": query
    }

    res = requests.get(GEOCODE_URL, headers=HEADERS, params=params)

    if res.status_code != 200:
        return []

    data = res.json()

    results = []

    for item in data.get("addresses", []):

        road = item.get("roadAddress")
        jibun = item.get("jibunAddress")

        address = road if road else jibun

        if address:
            results.append({
                "title": address,
                "address": address,
                "mapx": item["x"],
                "mapy": item["y"]
            })

    return results

# =========================================================================
# 네이버 Place_candidates + address = Location 합친 함수
# ========================================================================

def search_location_candidates(query):

    # 1️⃣ Local Search 먼저
    place_results = search_place_candidates(query)

    # 결과 있으면 그대로 사용
    if place_results:
        return place_results

    # 2️⃣ 없으면 Geocode 실행
    #st.title("나오네")
    address_results = search_address_candidates(query)

    return address_results






# ====================================================================
# 주소추천/입력 공통합수 (목적지,도착지) 렌더함수
# ======================================================================

def render_location_section(section_type, label_prefix, count, name_options):

    result_dict = {}

    for i in range(1, count + 1):

        base_key = f"{section_type}_{i}"

        if i > 1:
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

        #st.markdown(
        #    f"<div style='font-size:18px; font-weight:600; margin-bottom:5px;'>{label_prefix}{i}</div>",
        #    unsafe_allow_html=True
        #)

        col1, col2 = st.columns([3, 7])

        # ==========================
        # 🔹 왼쪽: 장소 선택
        # ==========================
        with col1:
            selected = st.selectbox(
                f"{label_prefix}{i} 선택",
                name_options,
                key=f"{base_key}_select"
            )

        if selected == "선택하세요":
            continue

        is_direct = selected == "네이버검색🔍"

        # ==========================
        # 🔹 오른쪽 영역
        # ==========================
        with col2:

            # 🔥 1️⃣ 네이버 검색 모드
            if is_direct:

                name = st.text_input(
                    "검색어 입력",
                    key=f"{base_key}_name"
                )

                addr = None

                if name and len(name) >= 2:

                    candidates = search_location_candidates(name)

                    if candidates:

                        option_labels = [
                            f"{item['title']} | {item['address']}"
                            for item in candidates
                        ]

                        sel_col, btn_col = st.columns(
                            [7, 1],
                            vertical_alignment="bottom"
                        )

                        with sel_col:
                            selected_label = st.selectbox(
                                "검색 결과 선택",
                                option_labels,
                                key=f"{base_key}_candidate"
                            )

                        selected_index = option_labels.index(selected_label)
                        selected_item = candidates[selected_index]
                        addr = selected_item["address"]

                        with btn_col:
                            save_clicked = st.button(
                                "💾",
                                key=f"{base_key}_save",
                                use_container_width=True
                            )

                        if save_clicked:
                            save_address(name, addr)
                            st.toast("💾 저장 완료!", icon="✅")
                            #st.write("✅")

                    else:
                        st.warning("검색 결과가 없습니다.")

            # 🔥 2️⃣ 저장된 주소 선택 모드
            else:

                name = selected
                addr = get_saved_address(name)

                st.text_input(
                    "주소",
                    value=addr,
                    disabled=True,
                    key=f"{base_key}_saved_addr"
                )

        # ==========================
        # 🔹 결과 dict 저장
        # ==========================
        if name and addr:
            result_dict[name] = addr

    return result_dict# 주소추천 공통합수 (목적지,도착지)


# ==============================
# 📌 주소 → 좌표
# ==============================

@st.cache_data(ttl=1800)
def geocode(address):
    params = {"query": address}
    res = requests.get(GEOCODE_URL, headers=HEADERS, params=params)

    if res.status_code != 200:
        return None

    data = res.json()

    if data['meta']['totalCount'] == 0:
        return None

    x = data['addresses'][0]['x']
    y = data['addresses'][0]['y']
    return f"{x},{y}"

# ==============================
# 📌 거리 계산
# ==============================

def get_distance(start, goal, departure_timestamp):

    params = {
        "start": start,
        "goal": goal,
        "option": "trafast",
        "departureTime": departure_timestamp
    }

    res = requests.get(DIRECTION_URL, headers=HEADERS, params=params)

    if res.status_code != 200:
        return None, None, None, None

    try:
        route = res.json()['route']['trafast'][0]
        summary = route['summary']
        path = route['path']  # 🔥 경로 좌표 추가

        distance_km = round(summary['distance'] / 1000, 1)
        duration_min = round(summary['duration'] / 60000, 1)
        duration_ms = summary['duration']

        return distance_km, duration_min, duration_ms, path

    except:
        return None, None, None, None

# ===================================================================
# 🎨 UI
# ==================================================================+

st.title("🚗 거리 비교 서비스")

tab1, tab2 = st.tabs(["🚀 거리 계산", "📘 주소록 관리"])

# =====================================================
# 🚀 거리 계산 탭
# =====================================================

with tab1:
    all_names = [row[0] for row in get_all_addresses()]
    #name_options = ["선택하세요"] + ["네이버검색🔍"] + all_names
    name_options = ["네이버검색🔍"] + all_names


#================= UI입력창 시작 =================
    st.header("📍 출발지 (최대 4곳)")

    origins = render_location_section(
        "origin",
        "출발지",
        4,
        name_options
    )

    st.header("🎯 목적지")

    dest_count = st.number_input("목적지 개수", 1, 10, 2)

    destinations = render_location_section(
        "destination",
        "목적지",
        int(dest_count),
        name_options
    )
#================= UI입력창 종료 =================
    import datetime

    st.subheader("🕒 출발 시간 설정")

    departure_datetime = st.datetime_input(
        "출발 일시 선택",
        value=datetime.datetime.now()
    )

    departure_timestamp = int(departure_datetime.timestamp() * 1000)

    # --------------------------------------------------
    # 상태 변수 초기화
    # --------------------------------------------------

    if "calculated" not in st.session_state:
        st.session_state.calculated = False

    # --------------------------------------------------
    # 🚀 버튼 = 계산 전용
    # --------------------------------------------------

    if st.button("🚀 거리 계산 시작"):

        all_paths = []
        result_rows = []
        summary_rows = []

        with st.spinner("거리 계산 중..."):

            for dest_name, dest_addr in destinations.items():

                dest_coord = geocode(dest_addr)

                if not dest_coord:
                    st.error(f"{dest_name} 주소 변환 실패")
                    continue

                total_d = 0
                total_t = 0
                total_duration_ms = 0

                for origin_name, origin_addr in origins.items():

                    start_coord = geocode(origin_addr)

                    if not start_coord:
                        continue

                    dist, dur, dur_ms, path = get_distance(
                        start_coord,
                        dest_coord,
                        departure_timestamp
                    )

                    if dist is not None:
                        all_paths.append({
                            "path": path,
                            "origin": origin_name,
                            "destination": dest_name
                        })

                        arrival_time = departure_datetime + datetime.timedelta(milliseconds=dur_ms)

                        result_rows.append({
                            "목적지": dest_name,
                            "출발지": origin_name,
                            "거리(km)": dist,
                            "소요시간(분)": dur,
                            "도착예상시간": arrival_time.strftime("%Y-%m-%d %H:%M")
                        })

                        total_d += dist
                        total_t += dur
                        total_duration_ms += dur_ms

                    time.sleep(0.2)

                arrival_time = departure_datetime + datetime.timedelta(milliseconds=total_t)

                summary_rows.append({
                    "목적지": dest_name,
                    "총 거리(km)": round(total_d, 1),
                    "총 소요시간(분)": round(total_t, 1),
                    "기준출발시간": arrival_time.strftime("%Y-%m-%d %H:%M")
                })

        # 🔥 여기 중요 — 계산 끝나면 저장
        st.session_state.all_paths = all_paths
        st.session_state.result_rows = result_rows
        st.session_state.summary_rows = summary_rows
        st.session_state.calculated = True


    # =================================================
    # 🔥 출력 전용 블록 (여기 하나만 있어야 함)
    # =================================================

    if st.session_state.get("calculated", False):

        result_rows = st.session_state.result_rows
        summary_rows = st.session_state.summary_rows
        all_paths = st.session_state.all_paths

        # ------------------------
        # 📋 상세 결과
        # ------------------------
        if result_rows:
            st.subheader("📋 상세 결과")
            st.dataframe(pd.DataFrame(result_rows), use_container_width=True)

        # ------------------------
        # 📊 요약 결과
        # ------------------------
        if summary_rows:
            df = pd.DataFrame(summary_rows).sort_values("총 거리(km)")
            st.subheader("📊 목적지 총합 비교")
            st.dataframe(df, use_container_width=True)
            st.success(f"🏆 최적 목적지: {df.iloc[0]['목적지']}")

        # -----------------------------
        # 🗺 지도 생성
        # -----------------------------

        if all_paths:

            colors = ["blue", "red", "green", "purple", "orange"]

            m = folium.Map()

            bounds_points = []  # 👈 이 리스트가 핵심

            for idx, route_info in enumerate(all_paths):
                raw_path = route_info["path"]
                origin_name = route_info["origin"]
                dest_name = route_info["destination"]

                folium_path = [(p[1], p[0]) for p in raw_path]
                color = colors[idx % len(colors)]

                # 🔵 경로
                folium.PolyLine(
                    folium_path,
                    weight=4,
                    color=color,
                    tooltip=f"{origin_name} → {dest_name}"
                ).add_to(m)

                # 🔹 출발지
                folium.Marker(
                    location=folium_path[0],
                    popup=f"{origin_name}",
                    icon=folium.Icon(color=color, icon="play")
                ).add_to(m)

                # 🔴 도착지
                folium.Marker(
                    location=folium_path[-1],
                    popup=f"{dest_name}",
                    icon=folium.Icon(color=color, icon="flag")
                ).add_to(m)

                # 👇👇👇 핵심 추가 부분
                bounds_points.append(folium_path[0])  # 출발지
                bounds_points.append(folium_path[-1])  # 도착지

            # 🔥 자동 줌 맞춤
            if bounds_points:
                m.fit_bounds(bounds_points)

            st_folium(m, width=800, height=500)



# =====================================================
# 📘 주소록 관리 탭
# =====================================================

with tab2:
    # 🔥 주소 입력 폼 초기화
    if st.session_state.get("reset_address_form", False):
        st.session_state["new_address_name"] = ""
        st.session_state["address_search_query"] = ""
        st.session_state["address_candidate_select"] = None
        st.session_state["selected_address_preview"] = ""
        st.session_state.reset_address_form = False

    st.header("➕ 주소 추가")

    col1, col2 = st.columns([3,5])

    # ----------------------------------
    # 이름 입력
    # ----------------------------------
    with col1:
        new_name = st.text_input("저장할 이름", key="new_address_name")

    # ----------------------------------
    # 주소 검색
    # ----------------------------------
    with col2:

        search_query = st.text_input(
            "주소 또는 장소 검색",
            placeholder="예: 스타벅스 강남 / 테헤란로 152",
            key="address_search_query"
        )

        selected_address = None

        if search_query and len(search_query) >= 2:

            candidates = search_location_candidates(search_query)

            if candidates:

                option_labels = [
                    f"{item['title']} | {item['address']}"
                    for item in candidates
                ]

                selected_label = st.selectbox(
                    "검색 결과 선택",
                    option_labels,
                    key="address_candidate_select"
                )

                idx = option_labels.index(selected_label)
                selected_item = candidates[idx]

                selected_address = selected_item["address"]

                st.text_input(
                    "선택된 주소",
                    value=selected_address,
                    disabled=True,
                    key="selected_address_preview"
                )

            else:
                st.warning("검색 결과가 없습니다.")

    # ----------------------------------
    # 저장 버튼
    # ----------------------------------

    if st.button("💾 주소 저장", use_container_width=True):

        if not new_name:
            st.warning("저장할 이름을 입력하세요")

        elif not selected_address:
            st.warning("주소를 검색 후 선택하세요")

        else:
            save_address(new_name, selected_address)
            st.success("주소 저장 완료")

            # 🔥 초기화 플래그
            st.session_state.reset_address_form = True

            st.rerun()


    st.header("📘 저장된 주소 목록")

    data = get_all_addresses()   # [(이름, 주소), (이름, 주소)] 형태라고 가정

    if data:

        for name, address in data:

            col1, col2, col3 = st.columns([2, 6, 1])

            # 🔹 이름
            with col1:
                st.markdown(f"**📍 {name}**")

            # 🔹 주소
            with col2:
                st.write(address)

            # 🔥 삭제 버튼 (아이콘)
            with col3:
                if st.button("🗑", key=f"delete_tab2_{name}"):
                    delete_address(name)
                    st.success(f"'{name}' 삭제 완료")
                    st.rerun()

    else:
        st.info("저장된 주소가 없습니다.")