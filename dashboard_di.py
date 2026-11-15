import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from pyproj import Transformer
import io
import csv

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(page_title="RLDA Dashboard Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main-header { font-size: 24px; font-weight: bold; color: #0077cc; margin-bottom: 20px; }
    .range-info { background-color: rgba(0, 119, 204, 0.2); padding: 10px; border-radius: 5px; margin-bottom: 15px; font-size: 14px; border-left: 4px solid #0077cc; color: inherit; }
    .stDataFrame { background-color: white; padding: 10px; border-radius: 5px; color: black; }
    .metric-box { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 5px solid #0077cc; color: black; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">RLDA v11.2.4 | Interactive Dashboard</div>', unsafe_allow_html=True)

# ==========================================
# 2. Helper Functions
# ==========================================
SHEET_ID = "1wkOIwvJGbsWz3MccBgFMIng9NqJ5v9HQ5yw_bfv1eMY"
ALIGN_SHEET_NAME = "Zone1_Alignment"
ALIGN_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={ALIGN_SHEET_NAME}"

@st.cache_data(ttl=5)
def load_google_sheet(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        
        # แปลงข้อมูลเป็นตัวเลข (ยกเว้นคอลัมน์ที่เป็น Text)
        text_cols = ['KM_Text', 'Remark_DI_NO', 'Pipe_Class', 'HasDI', 'Has_DI']
        for col in df.columns:
            if col not in text_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        df = df.dropna(subset=['DI_No', 'Northing', 'Easting'])
        
        # UTM Zone 48N -> WGS84
        transformer = Transformer.from_crs("epsg:32648", "epsg:4326", always_xy=True)
        df['Lat'], df['Lng'] = np.nan, np.nan
        
        if not df.empty:
            lng, lat = transformer.transform(df['Easting'].values, df['Northing'].values)
            df['Lng'] = lng
            df['Lat'] = lat
            
        return df
    except Exception as e:
        st.error(f"❌ ไม่สามารถโหลดข้อมูลได้: {e}")
        return None

def format_km(km_val):
    try:
        val = float(km_val)
        return f"{int(val//1000):03d}+{val%1000:07.3f}"
    except:
        return str(km_val)

def convert_df_to_csv(df):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(df.columns)
    for _, row in df.iterrows():
        writer.writerow(row.values)
    return output.getvalue().encode('utf-8-sig')

# ฟังก์ชันจัดรูปแบบตารางที่ปลอดภัย
def safe_format(df, format_str="{:.3f}", na_rep="-"):
    """จัดรูปแบบ DataFrame โดยเช็กชนิดข้อมูลก่อน"""
    styled_df = df.copy()
    for col in styled_df.columns:
        styled_df[col] = styled_df[col].apply(
            lambda x: format_str.format(x) if isinstance(x, (int, float, np.number)) and pd.notna(x) 
            else (na_rep if pd.isna(x) else str(x))
        )
    return styled_df

# ==========================================
# 3. Load Data & Sidebar Filters
# ==========================================
df_all = load_google_sheet(ALIGN_CSV_URL)

if df_all is not None:
    if df_all.empty:
        st.error("ไม่พบข้อมูลใน Sheet ที่ระบุ กรุณาตรวจสอบชื่อ Sheet ใน Google Sheets")
        st.stop()
        
    st.sidebar.header("🎛️ ตัวกรองข้อมูล (Filters)")
    
    filter_mode = st.sidebar.radio("เลือกโหมดการกรอง:", ["กรองด้วย DI", "กรองด้วย KM"])
    
    df = df_all.copy()
    
    if filter_mode == "กรองด้วย DI":
        di_list_all = df_all['DI_No'].tolist()
        col_di1, col_di2 = st.sidebar.columns(2)
        with col_di1:
            start_di = st.selectbox("เริ่มต้นที่ DI:", di_list_all, index=0)
        with col_di2:
            end_di = st.selectbox("สิ้นสุดที่ DI:", di_list_all, index=len(di_list_all)-1)
        
        if start_di > end_di:
            st.sidebar.error("⚠️ DI เริ่มต้นต้องน้อยกว่าหรือเท่ากับ DI สิ้นสุด")
            df = df_all[(df_all['DI_No'] >= end_di) & (df_all['DI_No'] <= start_di)].copy()
        else:
            df = df_all[(df_all['DI_No'] >= start_di) & (df_all['DI_No'] <= end_di)].copy()
    else:
        min_km = float(df_all['KM_m'].min())
        max_km = float(df_all['KM_m'].max())
        km_range = st.sidebar.slider("เลือกช่วง Chainage (KM)", min_value=min_km, max_value=max_km, value=(min_km, max_km), step=100.0)
        df = df_all[(df_all['KM_m'] >= km_range[0]) & (df_all['KM_m'] <= km_range[1])].copy()
    
    if not df.empty:
        km_min_val = df['KM_m'].min()
        km_max_val = df['KM_m'].max()
        di_min = df['DI_No'].min()
        di_max = df['DI_No'].max()
        
        st.sidebar.markdown(f"""
        <div class="range-info">
            <b>📍 ช่วงข้อมูลที่เลือก:</b><br>
            <b>DI:</b> {di_min} ถึง {di_max}<br>
            <b>KM:</b> {format_km(km_min_val)} ถึง {format_km(km_max_val)}<br>
            <b>จำนวน:</b> {len(df)} จุด
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.warning("⚠️ ไม่พบข้อมูลในช่วงที่เลือก")

    if 'selected_di' not in st.session_state:
        st.session_state.selected_di = df['DI_No'].iloc[0] if not df.empty else None

    # ==========================================
    # 4. Main Tabs Layout
    # ==========================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🗺️ แผนที่ & ข้อมูล", 
        "📈 กราฟ Profile", 
        "📐 หน้าตัด U-Drain",
        "🔲 หน้าตัด Manhole (ยาว)",
        "📋 ตารางสรุป & Export"
    ])

    # --------------------------------------------------
    # TAB 1: Map & Inspector (ปรับปรุงชื่อคอลัมน์)
    # --------------------------------------------------
    with tab1:
        col_map, col_info = st.columns([2, 1])
        
        with col_map:
            st.subheader("🗺️ Plan View (Satellite)")
            if not df.empty:
                center_lat = df['Lat'].mean()
                center_lng = df['Lng'].mean()
                
                m = folium.Map(location=[center_lat, center_lng], zoom_start=15, 
                               tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                               attr="Esri, Maxar, Earthstar Geographics")
                
                route_coords = df[['Lat', 'Lng']].values.tolist()
                folium.PolyLine(route_coords, color="#FF4500", weight=4, opacity=0.9).add_to(m)
                
                for idx, row in df.iterrows():
                    popup_html = f"<div style='background-color:white; padding:5px; border-radius:5px; color:black;'><b>DI {int(row['DI_No'])}</b><br>KM: {format_km(row['KM_m'])}</div>"
                    folium.Marker(location=[row['Lat'], row['Lng']], popup=folium.Popup(popup_html, max_width=200),
                                  tooltip=f"DI {int(row['DI_No'])}", icon=folium.Icon(color='green', icon='info-sign')).add_to(m)
                
                map_data = st_folium(m, width=800, height=500, returned_objects=["last_object_clicked"])
                
                if map_data.get('last_object_clicked') is not None:
                    click_lat = map_data['last_object_clicked']['lat']
                    click_lng = map_data['last_object_clicked']['lng']
                    df['dist'] = np.sqrt((df['Lat'] - click_lat)**2 + (df['Lng'] - click_lng)**2)
                    closest_idx = df['dist'].idxmin()
                    new_di = df.loc[closest_idx, 'DI_No']
                    if new_di != st.session_state.selected_di:
                        st.session_state.selected_di = new_di
                        st.rerun()
        
        with col_info:
            st.subheader("📋 Data Inspector")
            if not df.empty:
                di_list = df['DI_No'].tolist()
                try:
                    current_index = di_list.index(st.session_state.selected_di)
                except:
                    current_index = 0
                    
                selected_di = st.selectbox("เลือกจุด DI เพื่อดูข้อมูล:", di_list, index=current_index)
                st.session_state.selected_di = selected_di
                selected_row = df[df['DI_No'] == selected_di].iloc[0]

                # 1. หมวด U-Drain
                st.markdown("### 🔹 U-Drain")
                udrain_data = {
                    "Rail Level [MSL]": selected_row.get('RailLevel', '-'),
                    "Drain Invert Level [MSL]": selected_row.get('DrainInvertLevel', '-'),
                    "Level Top U-drain [MSL]": selected_row.get('LevelTopUdrain', '-'),
                    "Water Level [MSL]": selected_row.get('WaterLevel_m', '-'),
                    "Depth [m]": selected_row.get('Depth_m', '-'),
                    "Free Board [m]": selected_row.get('FreeBoard_m', '-'),
                    "Velocity [m/s]": selected_row.get('Velocity_ms', '-'),
                    "Flow-Q [CMS]": selected_row.get('Q_m3s', '-'),
                    "Froude No.": selected_row.get('Froude', '-')
                }
                df_udrain = pd.DataFrame(list(udrain_data.items()), columns=["Parameter", "Value"])
                st.dataframe(safe_format(df_udrain).style.set_properties(**{'background-color': 'white', 'color': 'black'}), hide_index=True, use_container_width=True)

                # 2. หมวด Manhole
                st.markdown("### 🔹 Manhole")
                manhole_data = {
                    "Has-DI (YES/NO)": "Yes" if str(selected_row.get('Has_DI', selected_row.get('HasDI', ''))).upper() in ['1', '1.0', 'YES', 'Y', 'TRUE'] else "No",
                    "WaterLevel_MSL-Manhole": selected_row.get('WaterLevel_m', '-'),
                    "Manhole Level Bottom [MSL]": selected_row.get('DrainBase_m', '-')
                }
                df_manhole = pd.DataFrame(list(manhole_data.items()), columns=["Parameter", "Value"])
                st.dataframe(safe_format(df_manhole).style.set_properties(**{'background-color': 'white', 'color': 'black'}), hide_index=True, use_container_width=True)

                # 3. หมวด Pipe Culvert
                st.markdown("### 🔹 Pipe Culvert")
                pipe_data = {
                    "Pipe Class": selected_row.get('Pipe_Class', '-'),
                    "Pipe Culvert Diameter [m]": selected_row.get('Pipe_D_m', '-'),
                    "Upstream Invert HU [MSL]": selected_row.get('UpstreamInvertHU', '-'),
                    "Downstream Invert HD [MSL]": selected_row.get('DownstreamInvertHD', '-'),
                    "Existing Ground Level [MSL]": selected_row.get('ExistingGroundLevel', '-'),
                    "Lp [m]": selected_row.get('Lp', '-'),
                    "Slope_Pipe Culvert": selected_row.get('Pipe_Slope', '-'),
                    "Velocity [m/s] Pipe Culvert": selected_row.get('Pipe_V_ms', '-'),
                    "Flow-Q [CMS] Pipe Culvert": selected_row.get('Pipe_Qcap_m3s', '-')
                }
                df_pipe = pd.DataFrame(list(pipe_data.items()), columns=["Parameter", "Value"])
                st.dataframe(safe_format(df_pipe).style.set_properties(**{'background-color': 'white', 'color': 'black'}), hide_index=True, use_container_width=True)

    # --------------------------------------------------
    # TAB 2: Longitudinal Profile
    # --------------------------------------------------
    with tab2:
        st.subheader("📈 Longitudinal Profile")
        if not df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df['KM_m'], y=df['RailLevel'], mode='lines+markers', name='Rail Level', line=dict(color='#d9534f', width=2)))
            if 'ExistingGroundLevel' in df.columns:
                fig.add_trace(go.Scatter(x=df['KM_m'], y=df['ExistingGroundLevel'], mode='lines', name='Existing Ground', line=dict(color='#9ccc65', width=2, dash='dot')))
            if 'LevelTopUdrain' in df.columns:
                 fig.add_trace(go.Scatter(x=df['KM_m'], y=df['LevelTopUdrain'], mode='lines', name='Drain Top', line=dict(color='#7b1fa2', width=2, dash='dash')))
            if 'DrainInvertLevel' in df.columns:
                fig.add_trace(go.Scatter(x=df['KM_m'], y=df['DrainInvertLevel'], mode='lines+markers', name='Drain Invert', line=dict(color='#1a237e', width=2)))
            if 'WaterLevel_m' in df.columns:
                fig.add_trace(go.Scatter(x=df['KM_m'], y=df['WaterLevel_m'], mode='lines+markers', name='Water Level (HGL)', line=dict(color='#00BFFF', width=3)))
            if 'ManholeLevelBottom' in df.columns:
                fig.add_trace(go.Scatter(x=df['KM_m'], y=df['ManholeLevelBottom'], mode='markers', name='Manhole Bottom', marker=dict(color='#b71c1c', size=6)))

            fig.add_trace(go.Scatter(x=[selected_row['KM_m']], y=[selected_row['RailLevel']], mode='markers', name='Selected Node', marker=dict(color='red', size=16, symbol='star', line=dict(color='black', width=1.5))))
            fig.update_layout(title="Profile (Elevation vs Chainage)", xaxis_title="Chainage (m)", yaxis_title="Elevation (m.msl)", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
            
            html_bytes = fig.to_html(include_plotlyjs='cdn').encode('utf-8')
            st.download_button(label="📥 ดาวน์โหลดกราฟ Profile (HTML)", data=html_bytes, file_name="Longitudinal_Profile.html", mime="text/html")

    # --------------------------------------------------
    # TAB 3: Cross Section U-Drain (Dynamic + Dimension Lines)
    # --------------------------------------------------
    with tab3:
        st.subheader("📐 Cross Section U-Drain")
        if not df.empty:
            row = df[df['DI_No'] == st.session_state.selected_di].iloc[0]
            B = 0.30 # สมมติ
            base = row.get('DrainInvertLevel', 0)
            top = row.get('LevelTopUdrain', base + 0.5)
            wl = row.get('WaterLevel_m', base)
            wl_capped = row.get('WL_capped_m', wl)
            rl = row.get('RailLevel', top + 1.0)
            fb = top - wl
            
            fig_xsec = go.Figure()
            
            # วาดตัว U-Drain
            fig_xsec.add_shape(type="rect", x0=-B/2, y0=base, x1=B/2, y1=top, line=dict(color="black", width=2), fillcolor="lightgray")
            # วาดน้ำ
            if pd.notna(wl) and wl > base:
                wl_disp = min(wl, top)
                fig_xsec.add_shape(type="rect", x0=-B/2, y0=base, x1=B/2, y1=wl_disp, line=dict(color="blue", width=1), fillcolor="rgba(0, 191, 255, 0.5)")
            
            # วาดเส้น Reference
            fig_xsec.add_hline(y=wl, line_dash="dash", line_color="green", annotation_text=f"WL: {wl:.3f}")
            fig_xsec.add_hline(y=top, line_dash="dot", line_color="purple", annotation_text=f"Top: {top:.3f}")
            fig_xsec.add_hline(y=rl, line_color="black", annotation_text=f"Rail: {rl:.3f}")

            # วาด Dimension Lines
            fig_xsec.add_annotation(x=0, y=base - 0.1, text=f"Width = {B:.3f} m", showarrow=False, bgcolor="white")
            fig_xsec.add_shape(type="line", x0=-B/2, y0=base - 0.08, x1=B/2, y1=base - 0.08, line=dict(color="black", width=1, dash="dash"))
            fig_xsec.add_shape(type="line", x0=-B/2, y0=base - 0.10, x1=-B/2, y1=base - 0.06, line=dict(color="black", width=1))
            fig_xsec.add_shape(type="line", x0=B/2, y0=base - 0.10, x1=B/2, y1=base - 0.06, line=dict(color="black", width=1))

            if wl > base:
                fig_xsec.add_annotation(x=B/2 + 0.05, y=(base+wl)/2, text=f"y = {wl-base:.3f} m", showarrow=False, bgcolor="white")
                fig_xsec.add_shape(type="line", x0=B/2 + 0.02, y0=base, x1=B/2 + 0.02, y1=wl, line=dict(color="black", width=1, dash="dash"))
            
            if fb > 0:
                fig_xsec.add_annotation(x=B/2 + 0.05, y=(wl+top)/2, text=f"FB = {fb:.3f} m", showarrow=False, bgcolor="white")
                fig_xsec.add_shape(type="line", x0=B/2 + 0.02, y0=wl, x1=B/2 + 0.02, y1=top, line=dict(color="black", width=1, dash="dash"))

            fig_xsec.update_layout(
                title=f"Cross Section U-Drain @ DI {st.session_state.selected_di} (KM {format_km(row['KM_m'])})",
                xaxis_title="Width (m)", yaxis_title="Elevation (m.msl)",
                xaxis_range=[-B*2, B*2], yaxis_range=[base - 0.5, max(top, rl) + 1], showlegend=False, height=500
            )
            st.plotly_chart(fig_xsec, use_container_width=True)

            # แสดงค่า V, Q ใต้กราฟ
            st.markdown(f"""
            <div class="metric-box">
                <b>Hydraulic Properties:</b><br>
                - Velocity: {row.get('Velocity_ms', 0):.3f} m/s<br>
                - Flow-Q: {row.get('Q_m3s', 0):.4f} CMS<br>
                - Froude No.: {row.get('Froude', 0):.3f}<br>
                - Water Level: {wl:.3f} m.msl<br>
                - Capped Water Level: {wl_capped:.3f} m.msl
            </div>
            """, unsafe_allow_html=True)

            html_xsec = fig_xsec.to_html(include_plotlyjs='cdn').encode('utf-8')
            st.download_button(label="📥 ดาวน์โหลด U-Drain (HTML)", data=html_xsec, file_name=f"UDrain_DI_{st.session_state.selected_di}.html", mime="text/html")

    # --------------------------------------------------
    # TAB 4: Cross Section Manhole & Culvert (Longitudinal)
    # --------------------------------------------------
    with tab4:
        st.subheader("🔲 หน้าตัด Manhole & Culvert (แนวยาว)")
        if not df.empty:
            row = df[df['DI_No'] == st.session_state.selected_di].iloc[0]
            
            # ดึงค่าตามชื่อคอลัมน์ที่กำหนด
            base_inv = row.get('DrainBase_MSL-Manhole', row.get('DrainInvertLevel', 0))
            wl_mh = row.get('WaterLevel_MSL-Manhole', row.get('WaterLevel_m', 0))
            pipe_dia = row.get('Pipe Culvert Diameter [m]', row.get('Pipe_D_m', 0.6))
            pipe_class = row.get('Pipe_Class', '-')
            hu = row.get('UpstreamInvertHU', 0)
            hd = row.get('DownstreamInvertHD', 0)
            lp = row.get('Lp', 9.0)
            slope = row.get('Pipe_Slope', 0)
            v_pipe = row.get('Pipe_V_ms', 0)
            q_pipe = row.get('Pipe_Qcap_m3s', 0)
            
            top_level = row.get('LevelTopUdrain', base_inv + 0.5)
            eg = row.get('ExistingGroundLevel', top_level + 0.5)
            mh_bottom = row.get('ManholeLevelBottom', row.get('DrainBase_m', base_inv - 1.8))
            
            fig_long = go.Figure()
            
            # 1. ผิวดิน (EG)
            fig_long.add_trace(go.Scatter(x=[-1, lp+1], y=[eg, eg], mode='lines', name='Existing Ground', line=dict(color='#8d6e63', width=3)))
            
            # 2. ตัว Manhole (สี่เหลี่ยม)
            fig_long.add_shape(type="rect", x0=-0.5, y0=mh_bottom, x1=0.5, y1=top_level, line=dict(color="black", width=2), fillcolor="lightgray")
            
            # 3. ท่อ Culvert (เส้น HU ถึง HD)
            fig_long.add_trace(go.Scatter(x=[0, lp], y=[hu, hd], mode='lines', name='Pipe Culvert', line=dict(color='blue', width=2)))
            
            # 4. ท้องท่อ (Invert) ที่ Manhole
            fig_long.add_hline(y=base_inv, line_dash="dot", line_color="purple", annotation_text=f"Invert: {base_inv:.3f}")

            # วาด Dimension Lines
            fig_long.add_annotation(x=lp/2, y=hd - 0.2, text=f"Lp = {lp:.3f} m", showarrow=False, bgcolor="white")
            fig_long.add_shape(type="line", x0=0, y0=hd - 0.15, x1=lp, y1=hd - 0.15, line=dict(color="black", width=1, dash="dash"))
            fig_long.add_shape(type="line", x0=0, y0=hd - 0.18, x1=0, y1=hd - 0.12, line=dict(color="black", width=1))
            fig_long.add_shape(type="line", x0=lp, y0=hd - 0.18, x1=lp, y1=hd - 0.12, line=dict(color="black", width=1))
            
            # ค่า HU, HD
            fig_long.add_annotation(x=-0.2, y=hu, text=f"HU: {hu:.3f}", showarrow=False, bgcolor="white")
            fig_long.add_annotation(x=lp+0.2, y=hd, text=f"HD: {hd:.3f}", showarrow=False, bgcolor="white")

            fig_long.update_layout(
                title=f"Longitudinal Section @ DI {st.session_state.selected_di} (KM {format_km(row['KM_m'])})",
                xaxis_title="Distance (m)", yaxis_title="Elevation (m.msl)",
                xaxis_range=[-1.5, lp+1.5], yaxis_range=[mh_bottom - 1, eg + 1], showlegend=True, height=500
            )
            st.plotly_chart(fig_long, use_container_width=True)

            # แสดงค่าต่างๆ ตามที่คุณระบุ
            st.markdown(f"""
            <div class="metric-box">
                <b>Manhole & Culvert Properties:</b><br>
                - Has-DI: {'YES' if str(row.get('Has_DI', row.get('HasDI', ''))).upper() in ['YES', '1', 'Y'] else 'NO'}<br>
                - WaterLevel_MSL-Manhole: {wl_mh:.3f} m.msl<br>
                - Manhole Level Bottom: {mh_bottom:.3f} m.msl<br>
                <b>Pipe Culvert:</b><br>
                - Pipe Class: {pipe_class}<br>
                - Pipe Diameter: {pipe_dia:.3f} m<br>
                - Upstream Invert HU: {hu:.3f} m.msl<br>
                - Downstream Invert HD: {hd:.3f} m.msl<br>
                - Existing Ground Level: {eg:.3f} m.msl<br>
                - Lp: {lp:.3f} m<br>
                - Slope Pipe Culvert: {slope:.4f}<br>
                - Velocity Pipe Culvert: {v_pipe:.3f} m/s<br>
                - Flow-Q Pipe Culvert: {q_pipe:.4f} CMS
            </div>
            """, unsafe_allow_html=True)

            html_long = fig_long.to_html(include_plotlyjs='cdn').encode('utf-8')
            st.download_button(label="📥 ดาวน์โหลด Manhole (HTML)", data=html_long, file_name=f"Manhole_Long_DI_{st.session_state.selected_di}.html", mime="text/html")

    # --------------------------------------------------
    # TAB 5: Data Tables & Export (ตามหมวดหมู่)
    # --------------------------------------------------
    with tab5:
        st.subheader("📋 ตารางข้อมูลผลลัพธ์แยกหมวดหมู่")
        
        # หมวดที่ 1: Hydraulic Results (U-Drain)
        st.markdown("### 1. ตารางผลการคำนวณทางชลศาสตร์ (Hydraulic Results)")
        hydraulic_cols = [
            'DI_No', 'KM_m', 'WL_capped_m', 'Fill_pct', 'RailLevel_m', 'Depth_m', 
            'CritDepth_m', 'WaterLevel_m', 'Q_m3s', 'Velocity_ms', 'Froude', 
            'Qcap_m3s', 'Shear_Pa', 'Shields', 'BedLoad_m2s', 'Tc_min', 'To_min', 
            'Td_min', 'Intensity_mmhr', 'HasDI'
        ]
        hydraulic_cols_show = [c for c in hydraulic_cols if c in df.columns]
        df_hydraulic = df[hydraulic_cols_show].copy()
        if 'KM_m' in df_hydraulic.columns:
            df_hydraulic['KM_m'] = df_hydraulic['KM_m'].apply(format_km)
        st.dataframe(df_hydraulic.style.set_properties(**{'background-color': 'white', 'color': 'black'}), use_container_width=True)
        
        # หมวดที่ 2: Drop Inlet System
        st.markdown("### 2. ตารางผลการคำนวณระบบบ่อพัก (Drop Inlet System)")
        drop_inlet_cols = [
            'DI_No', 'KM_m', 'DrainBase_m', 'WaterLevel_m', 'Q_m3s',
            'DI_Wi_m', 'DI_Li_m', 'DI_Di_m', 't_wall_m', 'Pipe_D_m', 
            'Pipe_Class', 'HU_msl', 'HD_msl', 'Lp_m', 'Pipe_Slope', 
            'Pipe_V_ms', 'Pipe_Qcap_m3s', 'HCR', 'Cover_m', 'CoverStatus', 'ScourStatus', 'HasDI'
        ]
        drop_inlet_cols_show = [c for c in drop_inlet_cols if c in df.columns]
        df_drop_inlet = df[drop_inlet_cols_show].copy()
        if 'KM_m' in df_drop_inlet.columns:
            df_drop_inlet['KM_m'] = df_drop_inlet['KM_m'].apply(format_km)
        st.dataframe(df_drop_inlet.style.set_properties(**{'background-color': 'white', 'color': 'black'}), use_container_width=True)

        # ปุ่ม Export ตารางทั้งหมด (CSV)
        csv_data = convert_df_to_csv(df)
        st.download_button(label="📥 ดาวน์โหลดตารางข้อมูลทั้งหมด (CSV)", data=csv_data, file_name="RLDA_Data_Export.csv", mime="text/csv")

else:
    st.error("เกิดข้อผิดพลาดในการโหลดข้อมูล")
