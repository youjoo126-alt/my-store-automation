import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import time
import random
from bs4 import BeautifulSoup

# --- 페이지 설정 ---
st.set_page_config(page_title="위탁판매 SEO 마스터 PRO", layout="wide")

# --- 사이드바: 설정 ---
with st.sidebar:
    st.header("⚙️ 설정 및 API 키")
    gemini_api_key = st.text_input("Gemini API Key", type="password")
    st.info("💡 네이버 쇼핑 상위 판매자 & 연관 검색어를 분석하여 키워드를 추출합니다.")
    
    if st.button("세션 초기화"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 세션 상태 초기화 ---
if 'raw_df' not in st.session_state: st.session_state.raw_df = None
if 'batch_df' not in st.session_state: st.session_state.batch_df = None
if 'edit_df' not in st.session_state: st.session_state.edit_df = None
if 'final_ready' not in st.session_state: st.session_state.final_ready = False

# --- 함수: 키워드 수집 로직 (강화버전) ---
def get_advanced_keywords(target_name):
    keywords_found = []
    try:
        # 1. 네이버 쇼핑 검색결과 페이지 분석
        search_url = f"https://search.shopping.naver.com/search/all?query={target_name}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Referer': 'https://search.shopping.naver.com/'
        }
        res = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 방식 A: 상위 판매자 상품명에서 단어 추출 (여러가지 태그 패턴 대응)
        titles = soup.find_all(['a', 'span'], class_=lambda x: x and ('product_link' in x or 'product_title' in x))
        all_words = []
        for title in titles[:15]:
            all_words.extend(title.text.strip().split())
            
        # 방식 B: 네이버가 추천하는 연관 검색어 추출
        related_tags = soup.select('ul[class^="related_list"] li a')
        for tag in related_tags:
            all_words.append(tag.text.strip())

        # 데이터 정제 (중복 제거, 내 상품명에 있는 단어 제외, 2글자 이상)
        for w in all_words:
            w_clean = w.replace(',', '').replace('[', '').replace(']', '').strip()
            if len(w_clean) > 1 and w_clean not in target_name:
                keywords_found.append(w_clean)
        
        # 중복 제거 후 빈도순 정렬 대신 순서 유지
        final_list = list(dict.fromkeys(keywords_found))
        
        if not final_list:
            return "추천,인기,필수템,가성비" # 최소한의 기본 키워드라도 반환
            
        return ", ".join(final_list[:15])
    except Exception as e:
        return "가성비,추천,인기상품" # 에러 시 기본 키워드

# --- 화면 구성 ---
st.title("📦 위탁판매 상품 최적화 시스템")

# [Step 1]
st.header("Step 1. 데이터 추출")
uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=["csv", "xlsx"])

if uploaded_file:
    if st.session_state.raw_df is None:
        try:
            if uploaded_file.name.endswith('.csv'):
                st.session_state.raw_df = pd.read_csv(uploaded_file)
            else:
                st.session_state.raw_df = pd.read_excel(uploaded_file)
        except:
            st.error("파일을 읽는 중 오류가 발생했습니다. CSV(UTF-8) 형식을 권장합니다.")

    if st.session_state.raw_df is not None:
        start_row = st.number_input(f"시작 행 (총 {len(st.session_state.raw_df)}행)", min_value=1, value=1)
        if st.button("오늘의 100개 추출"):
            st.session_state.batch_df = st.session_state.raw_df.iloc[start_row-1 : start_row-1 + 100].copy()
            st.success(f"📌 {start_row}번부터 추출 완료!")

# [Step 2]
if st.session_state.batch_df is not None:
    st.divider()
    st.header("Step 2. 상품명 간소화 및 수정")
    if st.button("AI 상품명 생성"):
        if not gemini_api_key:
            st.error("Gemini API Key를 입력하세요.")
        else:
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            new_names = []
            p_bar = st.progress(0)
            for i, name in enumerate(st.session_state.batch_df['상품명']):
                try:
                    res = model.generate_content(f"상품명 '{name}'을 '소재 특징 + 제품명 + 수량' 형식으로 짧게 바꿔줘. 결과만.")
                    new_names.append(res.text.strip())
                except:
                    new_names.append(name)
                p_bar.progress((i + 1) / len(st.session_state.batch_df))
            st.session_state.edit_df = st.session_state.batch_df.copy()
            st.session_state.edit_df['최종상품명'] = new_names

    if st.session_state.edit_df is not None:
        edited_data = st.data_editor(st.session_state.edit_df[['상품명', '최종상품명']], use_container_width=True)
        if st.button("상품명 확정"):
            st.session_state.edit_df['최종상품명'] = edited_data['최종상품명']
            st.session_state.step3_ready = True
            st.success("확정되었습니다. 다음 단계로 이동하세요.")

# [Step 3]
if st.session_state.get('step3_ready'):
    st.divider()
    st.header("Step 3. 키워드 추출 (상위 판매자 분석)")
    if st.button("키워드 분석 시작"):
        final_kw = []
        p_bar_2 = st.progress(0)
        status_text = st.empty()
        
        for i, row in enumerate(st.session_state.edit_df.iterrows()):
            name = row[1]['최종상품명']
            status_text.text(f"분석 중: {name} ({i+1}/100)")
            kw = get_advanced_keywords(name)
            final_kw.append(kw)
            p_bar_2.progress((i + 1) / len(st.session_state.edit_df))
            time.sleep(random.uniform(1.0, 2.0)) # 차단 방지를 위해 랜덤 지연 시간 추가
        
        res_df = st.session_state.edit_df.copy()
        res_df['상품명'] = res_df['최종상품명']
        res_df['키워드'] = final_kw
        if '최종상품명' in res_df.columns: del res_df['최종상품명']
        st.session_state.final_result_df = res_df
        st.session_state.final_ready = True
        st.success("완료!")

    if st.session_state.get('final_ready'):
        st.download_button("결과 엑셀 다운로드", data=st.session_state.final_result_df.to_csv(index=False).encode('utf-8-sig'), file_name="final_seo_result.csv")
