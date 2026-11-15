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
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">RLDA v11.2.4 | Interactive Dashboard & Cross-Section Viewer</div>', unsafe_allow_html=True)

# ==========================================
# 2. Helper Functions
# ==========================================
SHEET_ID = "1wkOIwvJGbsWz3MccBgFMIng9NqJ5v9HQ5yw_bfv1eMY"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

@st.cache_data(ttl=5)
def load_google_sheet(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        
        # แปลงข้อมูลให้เป็นตัวเลข
        num_cols = ['DI_No', 'KM_m', 'Northing', 'Easting', 'RailLevel', 
                    'DrainInvertLevel', 'LevelTopUdrain', 'ManholeLevelBottom',
                    'UpstreamInvertHU', 'DownstreamInvertHD', 'Lp', 'W_emb', 
                    'ExistingGroundLevel', 'DrainBase_m', 'WaterLevel_m',
                    'Velocity_ms', 'Qcap_m3s', 'Q_m3s', 'Depth_m', 'Froude',
                    'DrainBase_m-Culvert', 'WaterLevel_m-Culvert', 'Culvert-Q_m3s']
        
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        df = df.dropna(subset=['DI_No', 'Northing', 'Easting'])
        
        # แปลง UTM Zone 48N -> WGS84
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

# ==========================================
# 3. Load Data & Sidebar Filters
# ==========================================
df_all = load_google_sheet(CSV_URL)

if df_all is not None:
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
        
        km_range = st.sidebar.slider(
            "เลือกช่วง Chainage (KM)",
            min_value=min_km,
            max_value=max_km,
            value=(min_km, max_km),
            step=100.0
        )
        
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
    # 4. Main Tabs Layout (เพิ่ม Cross Section)
    # ==========================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🗺️ แผนที่ & ข้อมูล", 
        "📈 กราฟ Profile", 
        "📐 หน้าตัด U-Drain", 
        "📋 ตารางสรุป & Export"
    ])

    # --------------------------------------------------
    # TAB 1: Map & Inspector
    # --------------------------------------------------
    with tab1:
        col_map, col_info = st.columns([2, 1])
        
        with col_map:
            st.subheader("🗺️ Plan View (Satellite)")
            if not df.empty:
                center_lat = df['Lat'].mean()
                center_lng = df['Lng'].mean()
                
                m = folium.Map(
                    location=[center_lat, center_lng], 
                    zoom_start=15, 
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri, Maxar, Earthstar Geographics"
                )
                
                route_coords = df[['Lat', 'Lng']].values.tolist()
                folium.PolyLine(route_coords, color="#FF4500", weight=4, opacity=0.9).add_to(m)
                
                for idx, row in df.iterrows():
                    popup_html = f"<div style='background-color:white; padding:5px; border-radius:5px; color:black;'><b>DI {int(row['DI_No'])}</b><br>KM: {format_km(row['KM_m'])}</div>"
                    folium.Marker(
                        location=[row['Lat'], row['Lng']],
                        popup=folium.Popup(popup_html, max_width=200),
                        tooltip=f"DI {int(row['DI_No'])}",
                        icon=folium.Icon(color='green', icon='info-sign')
                    ).add_to(m)
                
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
                
                display_map = {
                    "DI_No": "DI_No", 
                    "KM_m": "KM (m)",
                    "RailLevel": "Rail Level [MSL]", 
                    "DrainInvertLevel": "Drain Invert Level [MSL]",
                    "LevelTopUdrain": "Level Top U-drain [MSL]", 
                    "ManholeLevelBottom": "Manhole Bottom [MSL]",
                    "HasDI": "HasDI", 
                    "ExistingGroundLevel": "Existing Ground Level [MSL]",
                    "Remark_DI_NO": "Remark", 
                    "WaterLevel_m": "Water Level [MSL]",
                    "Depth_m": "Depth [m]", 
                    "Velocity_ms": "Velocity [m/s]",
                    "Q_m3s": "Q [CMS]", 
                    "Froude": "Froude No."
                }
                
                param_list, value_list = [], []
                for key, label in display_map.items():
                    param_list.append(label)
                    if key in selected_row:
                        val = selected_row[key]
                        if pd.isna(val): 
                            value_list.append("-")
                        elif key == 'KM_m':
                            value_list.append(format_km(val))
                        elif key in ['Remark_DI_NO']: 
                            value_list.append(str(val))
                        elif key == 'HasDI':
                            val_str = str(val).strip().upper()
                            value_list.append("Yes" if val_str in ['1', '1.0', 'YES', 'Y', 'TRUE'] else "No")
                        else: 
                            value_list.append(f"{val:.3f}")
                    else: 
                        value_list.append("N/A")
                
                info_df = pd.DataFrame({"Parameter": param_list, "Value": value_list})
                st.dataframe(
                    info_df.style.set_properties(**{'background-color': 'white', 'color': 'black'}),
                    hide_index=True, use_container_width=True, height=550
                )

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
            
            fig.update_layout(
                title="Profile (Elevation vs Chainage)", 
                xaxis_title="Chainage (m)", 
                yaxis_title="Elevation (m.msl)", 
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            html_bytes = fig.to_html(include_plotlyjs='cdn').encode('utf-8')
            st.download_button(
                label="📥 ดาวน์โหลดกราฟ Profile (HTML)",
                data=html_bytes,
                file_name="Longitudinal_Profile.html",
                mime="text/html"
            )

    # --------------------------------------------------
    # TAB 3: Cross Section (U-Drain) [ใหม่]
    # --------------------------------------------------
    with tab3:
        st.subheader("📐 Cross Section (U-Drain)")
        if not df.empty:
            row = df[df['DI_No'] == st.session_state.selected_di].iloc[0]
            
            # ดึงขนาดท่อและระดับต่างๆ
            B = 0.30 # สมมติว่ากว้าง 0.3m (ถ้ามีใน Sheet สามารถดึงได้)
            base = row.get('DrainInvertLevel', 0)
            top = row.get('LevelTopUdrain', base + 0.5)
            H = top - base
            wl = row.get('WaterLevel_m', base)
            rl = row.get('RailLevel', top + 1.0)
            
            fig_xsec = go.Figure()
            
            # 1. วาดตัว U-Drain (พื้นคอนกรีต)
            fig_xsec.add_shape(
                type="rect", x0=-B/2, y0=base, x1=B/2, y1=top, 
                line=dict(color="black", width=2), fillcolor="lightgray"
            )
            
            # 2. วาดน้ำ (Water Level)
            if pd.notna(wl) and wl > base:
                wl_disp = min(wl, top)
                fig_xsec.add_shape(
                    type="rect", x0=-B/2, y0=base, x1=B/2, y1=wl_disp, 
                    line=dict(color="blue", width=1), fillcolor="rgba(0, 191, 255, 0.5)"
                )
            
            # 3. วาด Manhole / Culvert (ถ้ามี)
            if str(row.get('HasDI', '')).upper() in ['YES', 'Y', '1']:
                box_w = 1.0
                box_base = row.get('ManholeLevelBottom', base - 1.8) if pd.notna(row.get('ManholeLevelBottom')) else base - 1.8
                fig_xsec.add_shape(
                    type="rect", x0=B/2, y0=box_base, x1=B/2+box_w, y1=top, 
                    line=dict(color="gray", width=2), fillcolor="rgba(200, 200, 200, 0.5)"
                )
                fig_xsec.add_annotation(x=B/2 + box_w/2, y=top + 0.2, text="Manhole/Culvert", showarrow=False)

            # 4. วาดเส้นระดับต่างๆ
            fig_xsec.add_hline(y=wl, line_dash="dash", line_color="green", annotation_text=f"WL: {wl:.3f}")
            fig_xsec.add_hline(y=top, line_dash="dot", line_color="purple", annotation_text=f"Top: {top:.3f}")
            fig_xsec.add_hline(y=rl, line_color="black", annotation_text=f"Rail: {rl:.3f}")
            
            # 5. ตั้งค่าแกนและขนาด
            fig_xsec.update_layout(
                title=f"Cross Section @ DI {st.session_state.selected_di} (KM {format_km(row['KM_m'])})",
                xaxis_title="Width (m)", yaxis_title="Elevation (m.msl)",
                xaxis_range=[-B*2, B*2 + 1.5], yaxis_range=[base - 2.5, max(top, rl) + 1],
                showlegend=False,
                height=500
            )
            
            st.plotly_chart(fig_xsec, use_container_width=True)

            # ปุ่มดาวน์โหลด Cross Section (HTML)
            html_xsec = fig_xsec.to_html(include_plotlyjs='cdn').encode('utf-8')
            st.download_button(
                label="📥 ดาวน์โหลด Cross Section (HTML)",
                data=html_xsec,
                file_name=f"CrossSection_DI_{st.session_state.selected_di}.html",
                mime="text/html"
            )

    # --------------------------------------------------
    # TAB 4: Data Tables & Export
    # --------------------------------------------------
    with tab4:
        st.subheader("📋 ตารางข้อมูลผลลัพธ์")
        
        # 1. ตาราง Input (Geometry & Hydrology)
        st.markdown("### 1. ตาราง Input (Geometry & Hydrology)")
        input_cols = ['DI_No', 'KM_m', 'Northing', 'Easting', 'RailLevel', 'DrainInvertLevel', 'LevelTopUdrain', 'Q_m3s', 'Intensity_mmhr', 'Tc_min']
        cols_input_show = [c for c in input_cols if c in df.columns]
        df_input_display = df[cols_input_show].copy()
        if 'KM_m' in df_input_display.columns:
            df_input_display['KM_m'] = df_input_display['KM_m'].apply(format_km)
        st.dataframe(df_input_display.style.set_properties(**{'background-color': 'white', 'color': 'black'}), use_container_width=True)
        
        # 2. ตาราง Output (Hydraulics)
        st.markdown("### 2. ตาราง Output (Hydraulics & Safety)")
        output_cols = ['DI_No', 'KM_m', 'WaterLevel_m', 'Depth_m', 'Velocity_ms', 'Froude', 'Qcap_m3s', 'Shear_Pa', 'Shields']
        cols_output_show = [c for c in output_cols if c in df.columns]
        df_output_display = df[cols_output_show].copy()
        if 'KM_m' in df_output_display.columns:
            df_output_display['KM_m'] = df_output_display['KM_m'].apply(format_km)
        st.dataframe(df_output_display.style.set_properties(**{'background-color': 'white', 'color': 'black'}), use_container_width=True)

        # 3. ปุ่ม Export ตารางทั้งหมด
        csv_data = convert_df_to_csv(df)
        st.download_button(
            label="📥 ดาวน์โหลดตารางข้อมูลทั้งหมด (CSV)",
            data=csv_data,
            file_name="RLDA_Data_Export.csv",
            mime="text/csv"
        )

else:
    st.error("เกิดข้อผิดพลาดในการโหลดข้อมูล")
