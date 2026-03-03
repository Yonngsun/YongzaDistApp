#streamlit run C:\Users\Administrator\PycharmProjects\PythonProject\app.py
import streamlit as st
import requests
import pandas as pd
import time
import sqlite3


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

#=========================
#주소 후보리스트 반환 함수 만들기 (0303 21:00)

def search_place_candidates(query):

    headers = {
        "X-Naver-Client-Id": NAVER_OPEN_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_OPEN_CLIENT_SECRET
    }

    params = {
        "query": query,
        "display": 10,
        "sort": "random"
    }

    res = requests.get(LOCAL_SEARCH_URL, headers=headers, params=params)

    if res.status_code != 200:
        st.error(f"Open API 오류: {res.status_code}")
        return []

    data = res.json()
    results = []

    for item in data.get("items", []):

        title = item["title"].replace("<b>", "").replace("</b>", "")
        road = item.get("roadAddress")
        jibun = item.get("address")

        address = road if road else jibun

        if address:
            results.append({
                "title": title,
                "address": address,
                "mapx": item.get("mapx"),
                "mapy": item.get("mapy")
            })

    return results
#===============================================

#==================================================
# 주소추천 공통합수 (목적지,도착지)

def render_location_section(section_type, label_prefix, count, name_options):

    result_dict = {}

    for i in range(1, count + 1):

        st.markdown(f"---")
        st.subheader(f"{label_prefix}{i}")

        col1, col2 = st.columns(2)

        # ==========================
        # 🔹 1️⃣ 선택박스 (왼쪽)
        # ==========================
        with col1:
            selected = st.selectbox(
                "장소 선택",
                name_options,
                key=f"{section_type}_select_box_{i}"
            )

        if selected == "선택하세요":
            continue

        is_direct = selected == "네이버검색🔍"

        # ==========================
        # 🔹 2️⃣ 직접 입력 UI (왼쪽 중심)
        # ==========================
        if is_direct:

            with col1:
                name = st.text_input(
                    "이름 입력",
                    key=f"{section_type}_name_input_{i}"
                )

            selected_address = None

            if name and len(name) >= 2:

                candidates = search_place_candidates(name)

                if candidates:
                    option_labels = [
                        f"{item['title']} | {item['address']}"
                        for item in candidates
                    ]

                    with col2:
                        selected_label = st.selectbox(
                            "검색 결과 선택",
                            option_labels,
                            key=f"{section_type}_candidate_select_{i}"
                        )

                    selected_index = option_labels.index(selected_label)
                    selected_item = candidates[selected_index]
                    selected_address = selected_item["address"]

                else:
                    with col2:
                        st.warning("검색 결과가 없습니다.")

            # ✅ 저장 버튼은 한 번만 생성
            with col2:
                save_clicked = st.button(
                    "저장",
                    key=f"{section_type}_save_btn_{i}",
                    disabled=not (name and selected_address)
                )

            if save_clicked:
                save_address(name, selected_address)
                st.success("저장 완료!")
                st.rerun()

            addr = selected_address

        # ==========================
        # 🔹 3️⃣ 저장된 주소 표시 (오른쪽)
        # ==========================
        else:
            name = selected
            saved_addr = get_saved_address(name)

            with col2:
                addr = st.text_input(
                    "주소",
                    value=saved_addr,
                    disabled=True,
                    key=f"{section_type}_saved_addr_display_{i}"
                )

        if name and addr:
            result_dict[name] = addr

    return result_dict

# 주소추천 공통합수 (목적지,도착지)
#==================================================

init_db()

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

def get_distance(start, goal):
    params = {"start": start, "goal": goal, "option": "traoptimal"}
    res = requests.get(DIRECTION_URL, headers=HEADERS, params=params)

    if res.status_code != 200:
        return None, None

    try:
        summary = res.json()['route']['traoptimal'][0]['summary']
        return round(summary['distance']/1000,1), round(summary['duration']/60000,1)
    except:
        return None, None

# ==============================
# 🎨 UI
# ==============================

st.title("🚗 거리 비교 서비스")

tab1, tab2 = st.tabs(["🚀 거리 계산", "📘 주소록 관리"])

# =====================================================
# 🚀 거리 계산 탭
# =====================================================

with tab1:
    all_names = [row[0] for row in get_all_addresses()]
    name_options = ["선택하세요"] + ["네이버검색🔍"] + all_names

#================= UI입력창 시작 =================
    st.header("📍 출발지 (최대 4곳)")

    origins = render_location_section(
        "origin",
        "출발지",
        4,
        name_options
    )

    st.header("🎯 목적지")

    dest_count = st.number_input("목적지 개수", 1, 10, 1)

    destinations = render_location_section(
        "destination",
        "목적지",
        int(dest_count),
        name_options
    )
#================= UI입력창 종료 =================


    if st.button("🚀 거리 계산 시작"):

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

                for origin_name, origin_addr in origins.items():
                    start_coord = geocode(origin_addr)

                    if not start_coord:
                        continue

                    dist, dur = get_distance(start_coord, dest_coord)

                    if dist is not None:
                        result_rows.append({
                            "목적지": dest_name,
                            "출발지": origin_name,
                            "거리(km)": dist,
                            "소요시간(분)": dur
                        })

                        total_d += dist
                        total_t += dur

                    time.sleep(0.2)

                summary_rows.append({
                    "목적지": dest_name,
                    "총 거리(km)": round(total_d,1),
                    "총 소요시간(분)": round(total_t,1)
                })

        if result_rows:
            st.subheader("📋 상세 결과")
            st.dataframe(pd.DataFrame(result_rows), use_container_width=True)

        if summary_rows:
            df = pd.DataFrame(summary_rows).sort_values("총 거리(km)")
            st.subheader("📊 목적지 총합 비교")
            st.dataframe(df, use_container_width=True)
            st.success(f"🏆 최적 목적지: {df.iloc[0]['목적지']}")

# =====================================================
# 📘 주소록 관리 탭
# =====================================================

with tab2:

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