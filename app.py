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

# ==============================
# 📌 주소 → 좌표
# ==============================

@st.cache_data
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

    origins = {}
    destinations = {}

    st.header("📍 출발지 (최대 4곳)")

    all_names = [row[0] for row in get_all_addresses()]
    name_options = ["직접 입력"] + all_names

    for i in range(1, 5):

        selected = st.selectbox(f"출발지{i} 선택", name_options, key=f"origin_select{i}")

        if selected == "직접 입력":
            name = st.text_input(f"출발지{i} 이름", key=f"origin_name{i}")
        else:
            name = selected

        saved_addr = get_saved_address(name) if name else None

        addr_key = f"origin_addr{i}"

        if saved_addr:
            st.session_state[addr_key] = saved_addr
            addr = st.text_input(
                f"출발지{i} 주소",
                key=addr_key,
                disabled=True
            )
        else:
            addr = st.text_input(f"출발지{i} 주소", key=f"origin_addr{i}")
            if name and addr:
                if st.button(f"출발지{i} 저장", key=f"origin_save{i}"):
                    save_address(name, addr)
                    st.success("저장 완료!")
                    st.rerun()

        if name and addr:
            origins[name] = addr

    st.header("🎯 목적지")

    dest_count = st.number_input("목적지 개수", 1, 10, 1)

    for i in range(int(dest_count)):

        selected = st.selectbox(f"목적지{i+1} 선택", name_options, key=f"dest_select{i}")

        if selected == "직접 입력":
            name = st.text_input(f"목적지{i+1} 이름", key=f"dest_name{i}")
        else:
            name = selected

        saved_addr = get_saved_address(name) if name else None

        addr_key = f"dest_addr{i}"

        if saved_addr:
            st.session_state[addr_key] = saved_addr
            addr = st.text_input(
                f"목적지{i + 1} 주소",
                key=addr_key,
                disabled=True
            )
        else:
            addr = st.text_input(f"목적지{i+1} 주소", key=f"dest_addr_input{i}")
            if name and addr:
                if st.button(f"목적지{i+1} 저장", key=f"dest_save{i}"):
                    save_address(name, addr)
                    st.success("저장 완료!")
                    st.rerun()

        if name and addr:
            destinations[name] = addr

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
                    time.sleep(0.2)

                    if not start_coord:
                        continue

                    dist, dur = get_distance(start_coord, dest_coord)

                    if dist is not None:
                        result_rows.append({
                            "출발지": origin_name,
                            "목적지": dest_name,
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

    data = get_all_addresses()

    if data:
        df = pd.DataFrame(data, columns=["이름", "주소"])
        st.dataframe(df, use_container_width=True)

        delete_name = st.selectbox("삭제할 이름 선택", df["이름"])

        if st.button("삭제"):
            delete_address(delete_name)
            st.success("삭제 완료")
            st.rerun()
    else:
        st.info("저장된 주소가 없습니다.")