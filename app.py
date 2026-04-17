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
        
        titles = soup.select('a[class^="product_link__"]')
        
        all_words = []
        for title in titles[:10]:
            all_words.extend(title.text.strip().split())
        
        unique_keywords = []
        for w in all_words:
            if len(w) > 1 and w not in target_name:
                unique_keywords.append(w)
        
        return ", ".join(list(dict.fromkeys(unique_keywords))[:15])
    except:
        return "분석 실패"

# --- 본문 화면 구성 ---
st.title("📦 위탁판매 상품 최적화 시스템")

# [Step 1]
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
        st.success(f"📌 {start_row}번부터 100개 추출 완료!")

# [Step 2]
if st.session_state.batch_df is not None:
    st.divider()
    st.header("Step 2. 상품명 간소화 및 직접 수정")
    
    if st.button("AI 상품명 초안 생성"):
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
            st.success("AI 추천 이름 생성 완료!")

    if st.session_state.edit_df is not None:
        st.info("💡 '최종상품명' 칸을 클릭하여 직접 수정할 수 있습니다.")
        edited_data = st.data_editor(
            st.session_state.edit_df[['상품명', '최종상품명']],
            use_container_width=True,
            key="name_editor"
        )
        
        if st.button("수정한 상품명 확정"):
            st.session_state.edit_df['최종상품명'] = edited_data['최종상품명']
            st.session_state.step3_ready = True
            st.success("상품명 확정! 아래에서 키워드를 추출하세요.")

# [Step 3]
if st.session_state.get('step3_ready'):
    st.divider()
    st.header("Step 3. 상위 판매자 기반 키워드 추출")
    
    if st.button("황금 키워드 수집 시작"):
        final_kw_list = []
        p_bar_2 = st.progress(0)
        
        for i, row in enumerate(st.session_state.edit_df.iterrows()):
            target_name = row[1]['최종상품명']
            kw_result = get_competitor_keywords(target_name)
            final_kw_list.append(kw_result)
            p_bar_2.progress((i + 1) / len(st.session_state.edit_df))
            time.sleep(0.5)
        
        result_df = st.session_state.edit_df.copy()
        result_df['상품명'] = result_df['최종상품명']
        result_df['키워드'] = final_kw_list
        if '최종상품명' in result_df.columns: del result_df['최종상품명']
        
        st.session_state.final_result_df = result_df
        st.session_state.final_ready = True
        st.success("🎉 분석 완료!")

    if st.session_state.get('final_ready'):
        csv_data = st.session_state.final_result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "최종 엑셀 파일 다운로드",
            data=csv_data,
            file_name="optimized_result.csv",
            mime="text/csv"
        )
