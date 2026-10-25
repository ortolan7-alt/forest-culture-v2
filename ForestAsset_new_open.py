import streamlit as st
import pandas as pd
import os
import math
import base64
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components
import altair as alt
import tempfile
# ====== [NEW] GraphDB 시각화용 라이브러리 ======
import rdflib
from pyvis.network import Network
# ============================================

# 1. 페이지 설정 및 다크모드 대응 CSS 테마
st.set_page_config(page_title="산림문화자원 아카이브 시범 구축", page_icon="🌲", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    
    .stApp { font-family: 'Pretendard', 'Noto Sans KR', sans-serif; }
    h1 { color: var(--text-color) !important; font-weight: 800; letter-spacing: -0.5px; text-align: center; margin-bottom: 5px !important; }
    .stMarkdown p { text-align: center; color: var(--text-color); opacity: 0.8; font-size: 1.1em; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; padding-bottom: 10px; border-bottom: 2px solid rgba(128, 128, 128, 0.2); }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: var(--secondary-background-color); border-radius: 8px 8px 0px 0px; padding: 10px 24px; color: var(--text-color); opacity: 0.7; font-weight: 600; border: 1px solid rgba(128, 128, 128, 0.2); border-bottom: none; transition: all 0.3s ease; }
    .stTabs [aria-selected="true"] { color: #FFFFFF !important; background-color: #2ea043 !important; border-color: #2ea043 !important; opacity: 1; }
    [data-testid="stSidebar"] { border-right: 1px solid rgba(128, 128, 128, 0.2); }
    
    /* 탭2 이미지 중앙 정렬 유지 */
    div[data-testid="stImage"] { display: flex !important; justify-content: center !important; align-items: center !important; width: 100% !important; }
    div[data-testid="stImage"] img { height: 250px !important; width: 100% !important; max-width: 280px !important; object-fit: cover !important; border-radius: 12px !important; margin: 0 auto !important; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
    
    /* 모달창 내부 이미지 원본 비율 유지 */
    div[role="dialog"] div[data-testid="stImage"] img, div[data-testid="stDialog"] div[data-testid="stImage"] img { height: auto !important; width: 100% !important; max-height: 60vh !important; max-width: none !important; object-fit: contain !important; background-color: rgba(0,0,0,0.03); box-shadow: none !important; margin-bottom: 15px !important; }
    
    .stButton > button { border-radius: 6px; border: 1px solid #2ea043; color: #2ea043; background-color: transparent; font-weight: 600; transition: all 0.2s ease-in-out; }
    .stButton > button:hover { background-color: #2ea043; color: #FFFFFF; border-color: #2ea043; transform: translateY(-2px); }
    .reset-btn-container { margin-top: 28px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ★ [NEW] 자산 ID 기반 자동 이미지 스크래핑 로직
# ==========================================
def get_images_for_asset(item, base_dir='asset_images'):
    """
    1순위: asset_images/{ID}/ 폴더 내의 모든 이미지를 가져옵니다.
    2순위: 폴더가 없으면 CSV의 '이미지경로' 컬럼 데이터를 파싱합니다.
    """
    valid_img_paths = []
    
    # 1. 자산 ID를 기준으로 폴더 확인 (ID 컬럼이 있다고 가정)
    asset_id = str(item.get('ID', '')).strip()
    if asset_id and str(asset_id) != 'nan':
        folder_path = os.path.join(base_dir, asset_id)
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            # 지원하는 이미지 확장자
            exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
            for f in os.listdir(folder_path):
                if f.lower().endswith(exts):
                    valid_img_paths.append(os.path.join(folder_path, f))
            # 파일 이름순 정렬 (예: 1.jpg, 2.jpg ...)
            valid_img_paths.sort()
            
    # 2. 폴더에 이미지가 없다면 기존 CSV 방식(하위 호환) 적용
    if not valid_img_paths:
        csv_paths = str(item.get('이미지경로', ''))
        valid_img_paths = [p.strip() for p in csv_paths.split(',') if p.strip() and os.path.exists(p.strip())]
        
    return valid_img_paths

def get_base64_of_image(image_path):
    if image_path and os.path.exists(str(image_path)):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

def change_img_index(state_key, step, total_images):
    st.session_state[state_key] = (st.session_state[state_key] + step) % total_images

# ==========================================
# 2. 파이썬 전용 상세 팝업 모달창
# ==========================================
@st.dialog("자원 상세 정보", width="large")
def show_detail_modal(item):
    col_img, col_text = st.columns([1, 1.2]) 
    
    with col_img:
        # ★ 새로운 자동 스크래핑 함수 적용
        valid_img_paths = get_images_for_asset(item)
        
        if not valid_img_paths:
            st.image('https://via.placeholder.com/800x600?text=No+Image', use_container_width=True)
        elif len(valid_img_paths) == 1:
            st.image(valid_img_paths[0], use_container_width=True)
        else:
            item_id = str(item.name) 
            state_key = f"img_idx_{item_id}"
            if state_key not in st.session_state: st.session_state[state_key] = 0
            current_idx = st.session_state[state_key]
            
            st.image(valid_img_paths[current_idx], use_container_width=True)
            
            col_prev, col_lbl, col_next = st.columns([1, 1, 1])
            with col_prev: st.button("◀ 이전", key=f"prev_{item_id}", on_click=change_img_index, args=(state_key, -1, len(valid_img_paths)), use_container_width=True)
            with col_lbl: st.markdown(f"<div style='text-align:center; padding-top:10px; font-weight:bold;'>{current_idx + 1} / {len(valid_img_paths)}</div>", unsafe_allow_html=True)
            with col_next: st.button("다음 ▶", key=f"next_{item_id}", on_click=change_img_index, args=(state_key, 1, len(valid_img_paths)), use_container_width=True)
                
        vid_path = item.get('동영상경로', '') 
        if pd.notna(vid_path) and str(vid_path).strip() not in ['', 'nan']:
            st.write("") 
            st.markdown("<div style='text-align:left; font-size:0.85rem; font-weight:bold; color:#2ea043; margin-bottom:5px;'>🎥 관련 영상</div>", unsafe_allow_html=True)
            st.video(str(vid_path).strip())
            
    with col_text:
        st.markdown(f"<h3 style='margin-top:0;'>{str(item.get('명칭', '제목 없음'))}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:0.85rem; opacity:0.7; margin-bottom:15px;'>📍 {item.get('주소', '주소 미상')}</p>", unsafe_allow_html=True)
        st.divider()
        
        st.markdown("<div style='font-size:0.85rem; font-weight:bold; color:#2ea043; margin-bottom:5px;'>📖 자원 설명</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:0.9rem; line-height:1.6; opacity:0.9;'>{str(item.get('내용', '등록된 설명이 없습니다.'))}</div>", unsafe_allow_html=True)
        
        if pd.notna(item.get('대상지 현황')) and str(item.get('대상지 현황')).strip() != 'nan':
            st.write("")
            st.markdown("<div style='font-size:0.85rem; font-weight:bold; color:#2ea043; margin-bottom:5px;'>📋 대상지 현황</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.9rem; line-height:1.6; opacity:0.9;'>{str(item.get('대상지 현황'))}</div>", unsafe_allow_html=True)
            
        st.divider()
        
        st.markdown("<div style='font-size:0.85rem; font-weight:bold; color:#2ea043; margin-bottom:10px;'>📊 상세 속성 정보</div>", unsafe_allow_html=True)
        col_meta1, col_meta2 = st.columns(2)
        exclude_cols = ['명칭', '내용', '대상지 현황', '현장의견', '이미지경로', '동영상경로', '주소', 'ID', 'Lat', 'Lon', '출처', '문헌자료', '관련링크']
        
        count = 0
        for col_name in item.index:
            if col_name in exclude_cols: continue
            val = item[col_name]
            if pd.isna(val) or str(val).strip() in ['', 'nan', '·']: val = "-"
                
            meta_str = f"<div style='font-size:0.85rem; opacity:0.8;'>• <b>{col_name}</b>: {val}</div>"
            if count % 2 == 0:
                with col_meta1: st.markdown(meta_str, unsafe_allow_html=True)
            else:
                with col_meta2: st.markdown(meta_str, unsafe_allow_html=True)
            count += 1

def load_data(csv_path):
    if os.path.exists(csv_path):
        try: return pd.read_csv(csv_path, encoding='utf-8-sig')
        except UnicodeDecodeError: return pd.read_csv(csv_path, encoding='cp949')
    else:
        st.error(f"'{csv_path}' 파일을 찾을 수 없습니다.")
        return pd.DataFrame()

# ==========================================
# 3. 메인 화면 구성
# ==========================================
def main():
    st.markdown("<h1>🌲 디지털 산림문화자원 아카이브 시범 구축</h1>", unsafe_allow_html=True)
    st.markdown("<p>데이터 기반 산림문화 갤러리 및 공간 검색 플랫폼</p>", unsafe_allow_html=True)
    st.write("") 

    col_empty1, col_video, col_empty2 = st.columns([1, 6, 1])
    with col_video:
        video_html = """
        <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; border-radius: 12px; border: 1px solid rgba(128,128,128,0.2); box-shadow: 0 10px 20px rgba(0,0,0,0.05);">
            <iframe src="https://www.youtube.com/embed/kx3zWy-C9a4?autoplay=1&mute=1&loop=1&playlist=kx3zWy-C9a4&controls=0&showinfo=0&rel=0"
                    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen>
            </iframe>
        </div>
        """
        st.markdown(video_html, unsafe_allow_html=True)
        st.caption("▲ 담양 메타세쿼이아 가로수길 (국가산림문화자산 지정번호 : 2015-0001)")
    
    st.write("")

    CSV_FILE = 'test_ForestAsset_27_modify.csv'
    df = load_data(CSV_FILE)

    if df.empty: return

    def clear_filters():
        st.session_state["search_query"] = ""
        st.session_state["selected_category"] = "전체"
        st.session_state["selected_sub"] = "전체"

    with st.sidebar:
        st.markdown("### 🔍 산림문화자원 검색 필터")
        st.write("▼ 현지조사 보완자료 일부 제공")
        st.divider()
        
        col_search, col_reset = st.columns([4, 1])
        with col_search:
            search_query = st.text_input("통합 검색", placeholder="명칭, 주소 등...", key="search_query")
        with col_reset:
            st.markdown("<div class='reset-btn-container'></div>", unsafe_allow_html=True)
            st.button("🔄", key="btn_reset", on_click=clear_filters, help="검색 및 필터 초기화", use_container_width=True)
        
        categories = ["전체"] + list(df['지역'].dropna().unique()) if '지역' in df.columns else ["전체"]
        selected_category = st.selectbox("권역 필터", categories, key="selected_category")
            
        sub_categories = ["전체"] + list(df['중분류'].dropna().unique()) if '중분류' in df.columns else ["전체"]
        selected_sub = st.selectbox("유형 필터", sub_categories, key="selected_sub")

    filtered_df = df.copy()
    if selected_category != "전체": filtered_df = filtered_df[filtered_df['지역'] == selected_category]
    if selected_sub != "전체": filtered_df = filtered_df[filtered_df['중분류'] == selected_sub]
    if search_query:
        filtered_df = filtered_df[
            filtered_df['명칭'].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df['내용'].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df['주소'].astype(str).str.contains(search_query, case=False, na=False)
        ]

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🧊 하이라이트 전시관", 
        "📊 분석 및 유사 자원", 
        "🗺️ 공간 탐색 (Map)", 
        "📚 출처 정보",
        "🕸️ 지식 그래프 (Graph)" # 새로 추가된 탭
    ])

    item_to_show = None

    # [탭 1] 하이라이트 전시관
    with tab1:
        st.write("")
        st.markdown("### 🌲 하이라이트 전시관")
        st.info("💡 마우스나 터치로 화면을 좌우로 스와이프하여 자원을 감상하세요!")
        
        col_k1, col_k2, col_k3 = st.columns(3)
        col_k1.metric("총 자원 수", len(df))
        col_k2.metric("권역 분포", df['지역'].nunique() if '지역' in df.columns else 0)
        col_k3.metric("자원 유형", df['중분류'].nunique() if '중분류' in df.columns else 0)
        st.divider()
        
        display_df = df.head(10)
        image_tags = ""
        js_data = [] 
        num_items = len(display_df)
        angle_step = 360 / num_items if num_items > 0 else 0
        translate_z = 700 

        for i, row in display_df.iterrows():
            # ★ 동적 폴더 검색으로 첫 번째(대표) 이미지 할당
            folder_imgs = get_images_for_asset(row)
            first_img = folder_imgs[0] if folder_imgs else ""
            
            base64_str = get_base64_of_image(first_img)
            img_src = f"data:image/jpeg;base64,{base64_str}" if base64_str else "https://via.placeholder.com/400x500?text=No+Image"
            
            title = str(row.get("명칭", "")).replace("'", "\\'").replace('"', '&quot;')
            addr = str(row.get("주소", "")).replace("'", "\\'").replace('"', '&quot;')
            desc = str(row.get("내용", "")).replace("'", "\\'").replace('"', '&quot;').replace("\n", "<br>")
            
            js_data.append(f"{{ title: '{title}', addr: '{addr}', desc: '{desc}', img: '{img_src}' }}")

            style = f"transform: rotateY({i * angle_step}deg) translateZ({translate_z}px);"
            image_tags += f'<div class="carousel-item" style="{style}" onclick="openModal({i})"><img src="{img_src}"><div class="title">{title}</div></div>'

        js_array_str = "[\n" + ",\n".join(js_data) + "\n]"

        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
            :root {{ --bg-1: #ffffff; --bg-2: #f4f6f9; --card-bg: #ffffff; --text-main: #222222; --text-desc: #444444; --text-muted: #888888; --border-color: #eaeaea; --primary-green: #2ea043; }}
            @media (prefers-color-scheme: dark) {{ :root {{ --bg-1: #0E1117; --bg-2: #161920; --card-bg: #262730; --text-main: #FAFAFA; --text-desc: #DDDDDD; --text-muted: #AAAAAA; --border-color: #444444; }} }}
            body {{ margin: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; width: 100%; overflow: hidden; background: radial-gradient(circle at center, var(--bg-1) 0%, var(--bg-2) 100%); font-family: 'Noto Sans KR', sans-serif; color: var(--text-main); overscroll-behavior-y: contain; }}
            .scene {{ width: 100%; height: 500px; perspective: 1600px; perspective-origin: 50% -10%; margin: 0px auto 0px auto; display: flex; justify-content: center; position: relative; cursor: grab; }}
            .scene:active {{ cursor: grabbing; }}
            .carousel-wrapper {{ width: 340px; height: 480px; transform-style: preserve-3d; transform: rotateX(-6deg) translateY(-20px); pointer-events: none; }}
            .carousel {{ width: 100%; height: 100%; position: absolute; transform-style: preserve-3d; }}
            .carousel-item {{ position: absolute; width: 340px; height: 480px; left: 0; top: 0; border-radius: 12px; box-shadow: 0 15px 35px rgba(0,0,0,0.25); background: var(--card-bg); text-align: center; backface-visibility: hidden; border: 1px solid var(--border-color); cursor: pointer; transition: all 0.3s ease; -webkit-box-reflect: below 5px linear-gradient(transparent, transparent, rgba(0,0,0,0.1)); pointer-events: auto; }}
            .carousel-item:hover {{ border: 2px solid var(--primary-green); transform: scale(1.05) translateY(-15px); }}
            .carousel-item img {{ width: 100%; height: 380px; object-fit: cover; border-top-left-radius: 12px; border-top-right-radius: 12px; -webkit-user-drag: none; user-select: none; -moz-user-select: none; }}
            .carousel-item .title {{ padding: 22px 15px; font-weight: 700; font-size: 18px; pointer-events: none; user-select: none; }}
            .nav-btn {{ position: absolute; top: 45%; transform: translateY(-50%); width: 60px; height: 60px; border-radius: 50%; background-color: rgba(128, 128, 128, 0.08); color: var(--text-main); border: 1px solid rgba(128, 128, 128, 0.2); font-size: 28px; display: flex; align-items: center; justify-content: center; cursor: pointer; z-index: 1000; backdrop-filter: blur(4px); transition: all 0.3s ease; }}
            .nav-btn:hover {{ background-color: rgba(46, 160, 67, 0.85); color: #ffffff; border-color: var(--primary-green); transform: translateY(-50%) scale(1.1); box-shadow: 0 0 20px rgba(46, 160, 67, 0.4); }}
            .btn-prev {{ left: 30px; }}  
            .btn-next {{ right: 30px; }} 
            .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.6); backdrop-filter: blur(3px); }}
            .modal-content {{ background-color: var(--card-bg); margin: 3% auto; padding: 25px 35px; width: 85%; max-width: 600px; border-radius: 12px; box-shadow: 0 5px 30px rgba(0,0,0,0.3); max-height: 85vh; overflow-y: auto; position: relative; }}
            .close {{ color: var(--text-muted); position: absolute; top: 15px; right: 20px; font-size: 28px; font-weight: bold; cursor: pointer; }}
            .close:hover {{ color: var(--text-main); }}
            .modal-img {{ width: 100%; height: auto; max-height: 400px; object-fit: contain; border-radius: 8px; margin-bottom: 20px; background-color: var(--bg-2); }}
            .modal-title {{ font-size: 22px; font-weight: bold; margin: 0 0 5px 0; }}
            .modal-addr {{ font-size: 13px; color: var(--text-muted); margin-bottom: 20px; border-bottom: 1px solid var(--border-color); padding-bottom: 15px; }}
            .modal-desc-title {{ font-size: 13px; color: var(--primary-green); font-weight: bold; margin-bottom: 5px; }}
            .modal-desc {{ font-size: 14px; color: var(--text-desc); line-height: 1.6; }}
        </style>
        </head>
        <body>
        <button class="nav-btn btn-prev" onclick="rotateByButton(-1)">&#10094;</button>
        <button class="nav-btn btn-next" onclick="rotateByButton(1)">&#10095;</button>
        <div class="scene" id="scene"><div class="carousel-wrapper"><div class="carousel" id="carousel">{image_tags}</div></div></div>
        <div id="modal" class="modal" onclick="if(event.target==this) closeModal()"><div class="modal-content"><span class="close" onclick="closeModal()">&times;</span><img id="modal-img" class="modal-img" src=""><h2 id="modal-title" class="modal-title"></h2><div id="modal-addr" class="modal-addr"></div><div class="modal-desc-title">📖 자원 설명</div><div id="modal-desc" class="modal-desc"></div></div></div>
        <script>
            let currentAngle = 0; const angleStep = {angle_step}; const tz = {translate_z};
            const carousel = document.getElementById('carousel'); const scene = document.getElementById('scene');
            carousel.style.transition = 'transform 0.8s cubic-bezier(0.2, 0.8, 0.2, 1.2)';
            carousel.style.transform = `translateZ(-${{tz}}px) rotateY(0deg)`;
            function rotateByButton(dir) {{ carousel.style.transition = 'transform 0.8s cubic-bezier(0.2, 0.8, 0.2, 1.2)'; currentAngle -= dir * angleStep; carousel.style.transform = `translateZ(-${{tz}}px) rotateY(${{currentAngle}}deg)`; }}
            let isDragging = false; let startX = 0; let draggedDistance = 0; const dragSensitivity = 0.4; 
            scene.addEventListener('mousedown', (e) => {{ isDragging = true; startX = e.pageX; draggedDistance = 0; carousel.style.transition = 'none'; }});
            window.addEventListener('mousemove', (e) => {{ if (!isDragging) return; const x = e.pageX; const deltaX = x - startX; draggedDistance += Math.abs(deltaX); currentAngle += deltaX * dragSensitivity; carousel.style.transform = `translateZ(-${{tz}}px) rotateY(${{currentAngle}}deg)`; startX = x; }});
            window.addEventListener('mouseup', () => {{ if (isDragging) {{ isDragging = false; carousel.style.transition = 'transform 0.8s cubic-bezier(0.2, 0.8, 0.2, 1.2)'; }} }});
            scene.addEventListener('touchstart', (e) => {{ isDragging = true; startX = e.touches[0].pageX; draggedDistance = 0; carousel.style.transition = 'none'; }}, {{passive: true}});
            window.addEventListener('touchmove', (e) => {{ if (!isDragging) return; const x = e.touches[0].pageX; const deltaX = x - startX; draggedDistance += Math.abs(deltaX); currentAngle += deltaX * dragSensitivity; carousel.style.transform = `translateZ(-${{tz}}px) rotateY(${{currentAngle}}deg)`; startX = x; }}, {{passive: true}});
            window.addEventListener('touchend', () => {{ if (isDragging) {{ isDragging = false; carousel.style.transition = 'transform 0.8s cubic-bezier(0.2, 0.8, 0.2, 1.2)'; }} }});
            const assetData = {js_array_str};
            function openModal(index) {{ if (draggedDistance > 10) return; const data = assetData[index]; document.getElementById('modal-img').src = data.img; document.getElementById('modal-title').innerText = data.title; document.getElementById('modal-addr').innerText = "📍 " + data.addr; document.getElementById('modal-desc').innerHTML = data.desc; document.getElementById('modal').style.display = "block"; }}
            function closeModal() {{ document.getElementById('modal').style.display = "none"; }}
        </script>
        </body>
        </html>
        """
        st.components.v1.html(html_code, height=750) 

    # [탭 2] 분석 및 유사 자원 
    with tab2:
        st.write("")
        st.subheader("📊 산림문화자원 분석 및 탐색 대시보드")
        
        if filtered_df.empty:
            st.info("검색 조건에 일치하는 자원이 없습니다.")
        else:
            c1, c2 = st.columns(2)
            if '지역' in filtered_df.columns:
                arc_data = filtered_df['지역'].value_counts().reset_index()
                arc_data.columns = ['Category', 'Count']
                arc_chart = alt.Chart(arc_data).mark_arc(innerRadius=60).encode(
                    theta=alt.Theta('Count:Q'),
                    color=alt.Color('Category:N', legend=alt.Legend(title="권역")),
                    tooltip=['Category', 'Count']
                ).properties(width=300, height=300, title="권역 분포 (원형)")
                c1.altair_chart(arc_chart, use_container_width=True)
                
            if '중분류' in filtered_df.columns:
                bar_data = filtered_df['중분류'].value_counts().reset_index()
                bar_data.columns = ['Category', 'Count']
                bar_chart = alt.Chart(bar_data).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color='#2ea043').encode(
                    x=alt.X('Category:N', title="", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('Count:Q', title="자원 수"),
                    tooltip=['Category', 'Count']
                ).properties(width=300, height=300, title="유형 분포 (바형)")
                c2.altair_chart(bar_chart, use_container_width=True)

            st.divider()
            
            title_col, btn_prev_col, btn_next_col = st.columns([4, 1, 1])
            with title_col:
                st.markdown("### 🖼️ 유사 자원 탐색 갤러리")
            
            if 'carousel_t2_pos' not in st.session_state: st.session_state.carousel_t2_pos = 0
            start = st.session_state.carousel_t2_pos
            
            with btn_prev_col:
                if st.button("◀ 이전 리스트", key="prev_t2_top", use_container_width=True):
                    st.session_state.carousel_t2_pos = max(0, start - 4)
                    st.rerun()
            with btn_next_col:
                if st.button("다음 리스트 ▶", key="next_t2_top", use_container_width=True):
                    st.session_state.carousel_t2_pos = min(max(0, len(filtered_df) - 4), start + 4)
                    st.rerun()
            
            visible_items = filtered_df.iloc[start : start + 4] 
            
            cols = st.columns(4)
            for i, (idx, row) in enumerate(visible_items.iterrows()):
                with cols[i]:
                    with st.container():
                        # ★ 동적 폴더 검색 로직 적용
                        folder_imgs = get_images_for_asset(row)
                        first_img = folder_imgs[0] if folder_imgs else ""
                        
                        base64_str = get_base64_of_image(first_img)
                        img_src = f"data:image/jpeg;base64,{base64_str}" if base64_str else "https://via.placeholder.com/400x300?text=No+Image"
                        
                        st.markdown(f"""
                        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 10px;">
                            <img src="{img_src}" style="width: 100%; max-width: 280px; height: 250px; object-fit: cover; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08);">
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"<div style='text-align:center; margin-top:8px;'><b>{str(row.get('명칭', ''))}</b></div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center; font-size:0.85rem; opacity:0.7; margin-bottom:10px;'>📍 {row.get('지역', '')} | 🏷️ {row.get('중분류', '')}</div>", unsafe_allow_html=True)
                        
                        btn_col1, btn_col2, btn_col3 = st.columns([0.5, 4, 0.5])
                        with btn_col2:
                            if st.button("상세 정보 열람", key=f"btn_detail_t2_{row.name}", use_container_width=True):
                                item_to_show = row
                        st.write("")

    # [탭 3] Map 공간 탐색 (VWorld 맵)
    with tab3:
        st.write("")
        if 'Lat' in filtered_df.columns and 'Lon' in filtered_df.columns:
            map_data = filtered_df[['명칭', 'Lat', 'Lon']].copy()
            map_data['Lat'] = pd.to_numeric(map_data['Lat'], errors='coerce')
            map_data['Lon'] = pd.to_numeric(map_data['Lon'], errors='coerce')
            map_data = map_data.dropna()
            
            if not map_data.empty:
                map_data = map_data.rename(columns={'Lat': 'lat', 'Lon': 'lon'})
                vworld_tiles = "https://xdworld.vworld.kr/2d/Base/service/{z}/{x}/{y}.png"
                
                m = folium.Map(
                    location=[map_data['lat'].mean(), map_data['lon'].mean()],
                    zoom_start=7, tiles=vworld_tiles, attr="VWorld"
                )

                for idx, row in map_data.iterrows():
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        tooltip=row['명칭'],
                        icon=folium.Icon(color='green', icon='leaf')
                    ).add_to(m)

                map_event = st_folium(m, width=1200, height=600, returned_objects=["last_object_clicked"])

                if map_event and map_event.get("last_object_clicked"):
                    clicked_lat = map_event["last_object_clicked"]["lat"]
                    clicked_lon = map_event["last_object_clicked"]["lng"]
                    tolerance = 1e-4
                    matched = map_data[
                        (abs(map_data['lat'] - clicked_lat) < tolerance) &
                        (abs(map_data['lon'] - clicked_lon) < tolerance)
                    ]

                    if not matched.empty:
                        original_idx = matched.index[0]
                        if st.session_state.get('last_map_sel') != original_idx:
                            st.session_state['last_map_sel'] = original_idx
                            item_to_show = df.loc[original_idx]
                    else:
                        st.session_state['last_map_sel'] = None
            else:
                st.warning("현재 필터링된 결과에 유효한 좌표 데이터가 없습니다.")
        else:
            st.info("지도 표시를 위한 위경도 데이터가 없습니다.")

    # [탭 4] 출처 정보 
    with tab4:
        st.write("")
        st.subheader("📚 연관 자료 출처 및 문헌 정보")
        
        target_cols = ['ID', '명칭', '주소', '출처', '문헌자료']
        display_cols = [col for col in target_cols if col in filtered_df.columns]
                
        st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

    # 2D 갤러리 및 지도 연동 상세 팝업 모달창 오픈
    if item_to_show is not None:
        show_detail_modal(item_to_show)

    # [탭 5] 지식 그래프 시각화 (자동 라벨 인식 적용)
    with tab5:
        st.write("")
        st.subheader("🕸️ 산림문화자원 지식 그래프 (Knowledge Graph)")
        st.write("자원, 지역, 유형 간의 의미론적 관계를 탐색합니다. (마우스 휠로 확대/축소 및 드래그 가능)")
        
        # ttl_file_path = "forest_culture_graphdb_ready.ttl" <- 초기버전
        ttl_file_path = "forest_culture_full.ttl"
        g = rdflib.Graph()
        
        try:
            if os.path.exists(ttl_file_path):
                g.parse(ttl_file_path, format="turtle")
            else:
                st.info(f"'{ttl_file_path}' 파일이 없어 임시 테스트 그래프를 생성합니다.")
                
                # 테스트 데이터 (label, 명칭 등의 속성 사용)
                g.parse(data="""
                    @prefix ex: <http://example.org/> .
                    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                    
                    ex:Asset_1 rdfs:label "테스트 자산 1호" ;
                               ex:유형 ex:천연기념물 ;
                               ex:위치 ex:서울특별시_종로구 .
                               
                    ex:Asset_2 ex:명칭 "담양 메타세쿼이아 가로수길" ;
                               ex:유형 ex:가로수 ;
                               ex:위치 ex:전라남도_담양군 .
                               
                    ex:전라남도_담양군 rdfs:label "전라남도 담양군" ;
                                       ex:상위행정구역 ex:전라남도 .
                """, format="turtle")

            # 1. PyVis 네트워크 그래프 초기화
            net = Network(height="600px", width="100%", bgcolor="transparent", font_color="var(--text-color)")
            net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100, spring_strength=0.08)

            # ==========================================
            # ★ 사용자 아이디어 반영: Asset 다음의 label 자동 탐색 로직
            # ==========================================
            label_dict = {}
            
            # 그래프의 모든 데이터를 순회하며 라벨 역할을 하는 서술어를 찾습니다.
            for s, p, o in g:
                p_str = str(p).lower()
                # 서술어에 label, name, 명칭, 한글명 등이 포함되어 있으면 라벨 사전에 등록
                if "label" in p_str or "name" in p_str or "명칭" in p_str or "한글명" in p_str:
                    label_dict[str(s)] = str(o)

            # 화면에 표시할 텍스트를 결정하는 함수
            def get_display_label(uri):
                uri_str = str(uri)
                # 1순위: 사전에 등록된 라벨(한글명)이 있으면 즉시 반환
                if uri_str in label_dict:
                    return label_dict[uri_str]
                
                # 2순위: 라벨이 따로 없으면 URI의 맨 끝 단어를 추출하여 사용
                if "#" in uri_str: return uri_str.split("#")[-1]
                if "/" in uri_str: return uri_str.split("/")[-1]
                return uri_str
            # ==========================================

            MAX_TRIPLES = 1000 
            
            # 2. 노드 및 엣지 생성
            for i, (subj, pred, obj) in enumerate(g):
                if i >= MAX_TRIPLES: break
                
                p_str = str(pred).lower()
                # 라벨(이름)을 지정하는 엣지는 화면에 선으로 그리지 않고 숨김
                if "label" in p_str or "name" in p_str or "명칭" in p_str or "한글명" in p_str:
                    continue
                
                # 고유 ID와 화면 표시 라벨 분리
                s_id = str(subj)
                o_id = str(obj)
                
                s_label = get_display_label(subj)
                p_label = get_display_label(pred)
                
                is_literal = isinstance(obj, rdflib.Literal)
                o_label = str(obj) if is_literal else get_display_label(obj)

                # 노드 렌더링 (ID는 유지하되, 화면에는 찾은 라벨 출력)
                net.add_node(s_id, label=s_label, title=s_id, color="#2ea043", size=20)
                
                o_color = "#e3a008" if is_literal else "#1f6feb"
                o_size = 15 if is_literal else 20
                net.add_node(o_id, label=o_label, title=o_id, color=o_color, size=o_size)
                
                net.add_edge(s_id, o_id, title=p_label, label=p_label, color="gray")

            # 3. HTML 렌더링
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
                try:
                    net.save_graph(tmp_file.name)
                except AttributeError:
                    net.write_html(tmp_file.name)
                html_file_path = tmp_file.name

            with open(html_file_path, "r", encoding="utf-8") as f:
                graph_html = f.read()
            
            components.html(graph_html, height=650)
            
        except Exception as e:
            st.error(f"지식 그래프 생성 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
