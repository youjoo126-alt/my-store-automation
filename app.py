import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import time
from bs4 import BeautifulSoup

# --- 페이지 설정 ---
st.set_page_config(page_title="위탁판매 SEO 마스터", layout="wide")

# --- 사이드바: 설정 및 API 입력 ---
with st.sidebar:
    st.header("⚙️ 설정 및 API 키")
    gemini_api_key = st.text_input("Gemini API Key", type="password")
    st.info("네이버 API 없이 상위 판매자 분석 방식으로 작동합니다.")
    
    st.divider()
    if st.button("세션 초기화 (처음부터 다시)"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 세션 상태 초기화 ---
if 'raw_df' not in st.session_state: st.session_state.raw_df = None
if 'batch_df' not in st.session_state: st.session_state.batch_df = None
if 'edit_df' not in st.session_state: st.session_state.edit_df = None
if 'final_ready' not in st.session_state: st.session_state.final_ready = False

# --- 함수: 상위 판매자 키워드 추출 로직 ---
def get_competitor_keywords(target_name):
    try:
        url = f"https://search.shopping.naver.com/search/all?query={target_name}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 상위 상품명들 수집 (네이버 쇼핑 구조 반영)
        titles = soup.select('a[class^="product_link__"]')
        
        all_words = []
        for title in titles[:10]: # 상위 10개 업체 분석
            all_words.extend(title.text.strip().split())
        
        # 불필요 단어 필터링 (원본 이름에 있는 단어 등 제외)
        unique_keywords = []
        for w in all_words:
            if len(w) > 1 and w not in target_name:
                unique_keywords.append(w)
        
        # 중복 제거 후 상위 15개 반환
        return ", ".join(list(dict.fromkeys(unique_keywords))[:15])
    except:
        return "분석 실패 (직접 입력 권장)"

# --- 본문 화면 구성 ---
st.title("📦 위탁판매 상품 최적화 시스템")

# [Step 1] 파일 업로드 및 100개 추출
st.header("Step 1. 오늘 작업할 100개 추출")
uploaded_file = st.file_uploader("전체 리스트 엑셀 파일을 업로드하세요", type=["csv", "xlsx"])

if uploaded_file:
    if st.session_state.raw_df is None:
        if uploaded_file.name.endswith('.csv'):
            st.session_state.raw_df = pd.read_csv(uploaded_file)
        else:
            st.session_state.raw_df = pd.read_excel(uploaded_file)
    
    total_rows = len(st.session_state.raw_df)
    st.write(f"✅ 총 {total_rows}개의 상품 확인됨")
    
    start_row = st.number_input(f"시작 행 번호 (1 ~ {total_rows})", min_value=1, value=1)
    
    if st.button("오늘의 100개 추출하기"):
        st.session_state.batch_df = st.session_state.raw_df.iloc[start_row-1 : start_row-1 + 100].copy()
        st.success(f"📌 {start_row}번부터 100개 데이터를 가져왔습니다.")

# [Step 2] 상품명 간소화 및 직접 편집
if st.session_state.batch_df is not None:
    st.divider()
    st.header("Step 2. 상품명 간소화 및 대표님 직접 수정")
    
    if st.button("AI 상품명 초안 생성 (Gemini)"):
        if not gemini_api_key:
            st.error("왼쪽 사이드바에 Gemini API Key를 입력해주세요.")
        else:
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            new_names = []
            p_bar = st.progress(0)
            for i, name in enumerate(st.session_state.batch_df['상품명']):
                prompt = f"상품명 '{name}'을 '소재 특징 + 제품명 + 수량' 형식으로 짧고 간결하게 바꿔줘. 결과만 말해."
                try:
                    res = model.generate_content(prompt)
                    new_names.append(res.text.strip())
                except:
                    new_names.append(name)
                p_bar.progress((i + 1) / len(st.session_state.batch_df))
            
            st.session_state.edit_df = st.session_state.batch_df.copy()
            st.session_state.edit_df['최종상품명'] = new_names
            st.success("AI 추천 이름이 생성되었습니다.")

    if st.session_state.edit_df is not None:
        st.info("💡 '최종상품명' 칸을 클릭하여 직접 수정할 수
