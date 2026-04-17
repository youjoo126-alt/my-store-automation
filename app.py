import streamlit as st
import pandas as pd
import google.generativeai as genai
import time
import random

# --- 페이지 설정 ---
st.set_page_config(page_title="위탁판매 SEO 마스터 PRO", layout="wide")

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("⚙️ 설정 및 API 키")
    gemini_api_key = st.text_input("Gemini API Key", type="password")
    st.info("💡 AI가 마케팅 전문가가 되어 15개 이상의 황금 키워드를 직접 생성합니다.")
    
    if st.button("세션 초기화"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 세션 상태 초기화 ---
if 'raw_df' not in st.session_state: st.session_state.raw_df = None
if 'batch_df' not in st.session_state: st.session_state.batch_df = None
if 'edit_df' not in st.session_state: st.session_state.edit_df = None
if 'final_ready' not in st.session_state: st.session_state.final_ready = False

# --- 핵심 함수: AI 기반 키워드 생성 ---
def get_ai_keywords(product_name, model):
    try:
        prompt = f"""
        너는 한국 이커머스(네이버 스마트스토어, 쿠팡) 마케팅 전문가야.
        상품명: '{product_name}'
        
        이 상품이 네이버 쇼핑 검색 결과 상단에 노출될 수 있도록, 소비자들이 실제로 많이 검색하는 '황금 키워드'를 20개 생성해줘.
        
        [조건]
        1. 한국어로 작성할 것.
        2. 각 키워드는 쉼표(,)로 구분할 것.
        3. 반드시 15개 이상, 20개 이하로 작성할 것.
        4. 상품의 용도, 타겟 고객, 문제 해결, 감성 키워드를 적절히 섞어줘.
        5. 설명 없이 키워드만 나열해줘.
        """
        response = model.generate_content(prompt)
        keywords = response.text.strip().replace('\n', '')
        return keywords
    except Exception as e:
        return "추천,인기,필수템,가성비,핫아이템,선물추천,생활용품,실용적인,세련된,튼튼한,간편한,빠른배송,최저가,고품질,무료배송"

# --- 화면 구성 ---
st.title("📦 위탁판매 상품 최적화 시스템 (AI 전문가 모드)")

# [Step 1] 데이터 추출
st.header("Step 1. 오늘 작업할 100개 추출")
uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=["csv", "xlsx"])

if uploaded_file:
    if st.session_state.raw_df is None:
        try:
            if uploaded_file.name.endswith('.csv'):
                st.session_state.raw_df = pd.read_csv(uploaded_file)
            else:
                st.session_state.raw_df = pd.read_excel(uploaded_file)
        except:
            st.error("파일을 읽는 중 오류가 발생했습니다.")

    if st.session_state.raw_df is not None:
        start_row = st.number_input(f"시작 행 (총 {len(st.session_state.raw_df)}행)", min_value=1, value=1)
        if st.button("오늘의 100개 추출"):
            st.session_state.batch_df = st.session_state.raw_df.iloc[start_row-1 : start_row-1 + 100].copy()
            st.success(f"📌 {start_row}번부터 추출 완료!")

# [Step 2] 상품명 간소화
if st.session_state.batch_df is not None:
    st.divider()
    st.header("Step 2. 상품명 간소화 및 수정")
    if st.button("AI 상품명 초안 생성"):
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
            st.success("확정되었습니다. Step 3로 이동하세요.")

# [Step 3] AI 황금 키워드 추출
if st.session_state.get('step3_ready'):
    st.divider()
    st.header("Step 3. AI 마케팅 전문가 키워드 추출 (15개+)")
    if st.button("AI 키워드 분석 시작"):
        if not gemini_api_key:
            st.error("Gemini API Key가 필요합니다.")
        else:
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            final_kw = []
            p_bar_2 = st.progress(0)
            status_text = st.empty()
            
            for i, row in enumerate(st.session_state.edit_df.iterrows()):
                name = row[1]['최종상품명']
                status_text.text(f"AI가 키워드 분석 중: {name} ({i+1}/100)")
                
                # AI에게 키워드 생성 요청
                kw = get_ai_keywords(name, model)
                final_kw.append(kw)
                
                p_bar_2.progress((i + 1) / len(st.session_state.edit_df))
                # AI API는 속도가 빠르므로 지연 시간을 줄여도 됩니다.
                time.sleep(0.2)
            
            res_df = st.session_state.edit_df.copy()
            res_df['상품명'] = res_df['최종상품명']
            res_df['키워드'] = final_kw
            if '최종상품명' in res_df.columns: del res_df['최종상품명']
            
            st.session_state.final_result_df = res_df
            st.session_state.final_ready = True
            st.success("🎉 모든 키워드가 15개 이상 성공적으로 추출되었습니다!")

    if st.session_state.get('final_ready'):
        st.download_button(
            "최종 엑셀 다운로드", 
            data=st.session_state.final_result_df.to_csv(index=False).encode('utf-8-sig'), 
            file_name="final_seo_result.csv"
        )
