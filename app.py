import streamlit as st
import requests
import pandas as pd
import time


# ==============================
# 🔐 Streamlit Secrets에서 API 키 불러오기
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
# 📌 주소 → 좌표 변환
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
# 📌 거리/시간 계산
# ==============================
def get_distance(start, goal):
    params = {
        "start": start,
        "goal": goal,
        "option": "traoptimal"
    }

    res = requests.get(DIRECTION_URL, headers=HEADERS, params=params)

    if res.status_code != 200:
        return None, None

    data = res.json()

    try:
        summary = data['route']['traoptimal'][0]['summary']
        distance_km = summary['distance'] / 1000
        duration_min = summary['duration'] / 60000
        return round(distance_km, 1), round(duration_min, 1)
    except:
        return None, None


# ==============================
# 🎨 Streamlit UI
# ==============================

st.title("🚗 거리 비교하기")

st.header("📍 출발지 입력 (4곳)")

origins = {}

for i in range(1, 5):
    name = st.text_input(f"출발지{i} 이름", key=f"name{i}")
    addr = st.text_input(f"출발지{i} 도로명 주소", key=f"addr{i}")

    if name and addr:
        origins[name] = addr


st.header("🎯 목적지 입력")

dest_count = st.number_input("목적지 개수", min_value=1, max_value=10, value=1)

destinations = {}

for i in range(int(dest_count)):
    name = st.text_input(f"목적지{i+1} 이름", key=f"dest_name{i}")
    addr = st.text_input(f"목적지{i+1} 도로명 주소", key=f"dest_addr{i}")

    if name and addr:
        destinations[name] = addr


# ==============================
# 🚀 계산 버튼
# ==============================
import pandas as pd

if st.button("🚀 거리 계산 시작"):

    result_rows = []
    summary_rows = []

    with st.spinner("거리 계산 중입니다... 잠시만 기다려주세요 ⏳"):

        for dest_name, dest_addr in destinations.items():
            dest_coord = geocode(dest_addr)

            if not dest_coord:
                st.error(f"{dest_name} 주소 변환 실패")
                continue

            total_distance = 0
            total_time = 0

            for origin_name, origin_addr in origins.items():
                start_coord = geocode(origin_addr)
                time.sleep(0.2)

                if not start_coord:
                    continue

                distance, duration = get_distance(start_coord, dest_coord)

                if distance is not None:
                    result_rows.append({
                        "출발지": origin_name,
                        "목적지": dest_name,
                        "거리(km)": distance,
                        "소요시간(분)": duration
                    })

                    total_distance += distance
                    total_time += duration

                time.sleep(0.2)

            summary_rows.append({
                "목적지": dest_name,
                "총 거리(km)": round(total_distance, 1),
                "총 소요시간(분)": round(total_time, 1)
            })

    # ==========================
    # 📊 상세 결과 테이블
    # ==========================
    if result_rows:
        df_detail = pd.DataFrame(result_rows)
        st.subheader("📋 상세 거리 결과")
        st.dataframe(df_detail, use_container_width=True)

    # ==========================
    # 📈 합계 테이블 (거리 기준 정렬)
    # ==========================
    if summary_rows:
        df_summary = pd.DataFrame(summary_rows)
        df_summary = df_summary.sort_values("총 거리(km)")

        st.subheader("📊 목적지 총합 비교 (거리 오름차순)")
        st.dataframe(df_summary, use_container_width=True)

        best = df_summary.iloc[0]["목적지"]
        st.success(f"🏆 최적 목적지: {best}")