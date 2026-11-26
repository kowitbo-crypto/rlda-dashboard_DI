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
    .metric-box { background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 5px solid #0077cc; color: black; margin-top: 10px; }
    .zone-badge { display: inline-block; background-color: #0077cc; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-left: 8px; }
    .section-header { background-color: #e8f4f8; padding: 8px 12px; border-radius: 4px; border-left: 4px solid #0077cc; margin-top: 15px; margin-bottom: 8px; font-weight: bold; color: #0077cc; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">RLDA v11.2.5 | Interactive Dashboard</div>', unsafe_allow_html=True)

# ==========================================
# 2. Configuration & Column Mapping
# ==========================================
SHEET_ID = "1Z5JRl7SQ_JK3gXXuD69r-gh6yvYLqS3eJfVZZEPypPQ"
ALIGN_SHEET_NAME = "Zone1_Alignment"
ALIGN_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={ALIGN_SHEET_NAME}"

# Mapping: ชื่อคอลัมน์ใน sheet (จริง) -> ชื่อมาตรฐานที่ใช้ใน code
# อิงตามโครงสร้าง sheet: Input / Results / Pipe / DropInlet
COLUMN_RENAME_MAP = {
    # --- Input Section (ค่า survey ต้นฉบับ) ---
    'Rail Level':              'RailLevel',
    'Drain Invert Level':      'DrainInvertLevel',
    'Level Top U-drain':       'LevelTopUdrain',
    'Manhole Level Bottom':    'ManholeLevelBottom',
    'ExistingGroundLevel':     'ExistingGroundLevel',
    'Overland Flow Length L0': 'OverlandFlowLengthL0',
    # --- Results Section (ค่าคำนวณชลศาสตร์) ---
    'RailLevel_m':             'RailLevel_m',
    'Drain Top_m':             'DrainTop_m',
    'Drain Base_m':            'DrainBase_m_input',   # เป็นค่าจาก Results section (computed)
    'WaterLevel_capped_m':     'WaterLevel_capped_m',
    'Depth_m':                 'Depth_m',
    'Fill_pct':                'Fill_pct',
    'CritDepth_m':             'CritDepth_m',
    'Q_m3s':                   'Q_m3s',          # first Q_m3s (Results section)
    'Velocity_ms':             'Velocity_ms',
    'Froude':                  'Froude',
    'Qcap_m3s':                'Qcap_m3s',
    'Shear_Pa':                'Shear_Pa',
    'Shields':                 'Shields',
    'BedLoad_m2s':             'BedLoad_m2s',
    'Tc_min':                  'Tc_min',
    'To_min':                  'To_min',
    'Td_min':                  'Td_min',
    'Intensity_mmhr':          'Intensity_mmhr',
    'Has_DI':                  'Has_DI',         # first Has_DI (Results section)
    'Pipe_HGL':                'Pipe_HGL',
    # --- Pipe Section ---
    'HU':                      'HU',
    'HD':                      'HD',
    'Lp':                      'Lp',
    'S_pipe':                  'S_pipe',
    'Q_pipe':                  'Q_pipe',
    'A_flow':                  'A_flow',
    'yn':                      'yn',
    'ynD':                     'ynD',
    'V':                       'V_pipe',
    'Qcap_full':               'Qcap_full',
    'Qcap_80':                 'Qcap_80',
    'HW':                      'HW',
    'Control':                 'Control',
    'hL':                      'hL',
    'HGL_in':                  'HGL_in',
    'HGL_out':                 'HGL_out',
    'Crown_in':                'Crown_in',
    'Crown_out':               'Crown_out',
    'EG_out':                  'EG_out',
    'Cover':                   'Cover',
    'Box_top':                 'Box_top',
    'Status':                  'Status',
    'Notes':                   'Notes',
    'DropInlet':               'DropInlet',
    # --- Drop Inlet Section (Pipe Culvert + Manhole สรุป) ---
    'DrainBase_m':             'DrainBase_m',
    'WaterLevel_m':            'WaterLevel_m',
    'DI_Wi_m':                 'DI_Wi_m',
    'DI_Li_m':                 'DI_Li_m',
    'DI_Di_m':                 'DI_Di_m',
    't_wall_m':                't_wall_m',
    'Pipe_D_m':                'Pipe_D_m',
    'Pipe_Class':              'Pipe_Class',
    'HU_msl':                  'UpstreamInvertHU',
    'HD_msl':                  'DownstreamInvertHD',
    'Lp_m':                    'Lp_m',
    'Pipe_Slope':              'Pipe_Slope',
    'Pipe_V_ms':               'Pipe_V_ms',
    'Pipe_Qcap_m3s':           'Pipe_Qcap_m3s',
    'HCR':                     'HCR',
    'Cover_m':                 'Cover_m',
    'CoverStatus':             'CoverStatus',
    'ScourStatus':             'ScourStatus',
}

# ==========================================
# 3. Helper Functions
# ==========================================
@st.cache_data(ttl=5)
def load_google_sheet(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()

        # Normalize column names using mapping (เลือกเฉพาะที่มีใน sheet)
        rename_dict = {k: v for k, v in COLUMN_RENAME_MAP.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        # Safety net: กรณีมี duplicate column หลัง rename (เก็บเฉพาะคอลัมน์แรก)
        dup_cols = df.columns[df.columns.duplicated(keep='first')].tolist()
        if dup_cols:
            df = df.loc[:, ~df.columns.duplicated(keep='first')]

        text_cols = ['KM_Text', 'Remark_DI_NO', 'Pipe_Class', 'HasDI', 'Has_DI',
                     'Control', 'Status', 'Notes', 'CoverStatus', 'ScourStatus']
        for col in df.columns:
            if col not in text_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.dropna(subset=['DI_No', 'Northing', 'Easting'])

        # แปลงระบบพิกัด EPSG:32648 -> EPSG:4326
        transformer = Transformer.from_crs("epsg:32648", "epsg:4326", always_xy=True)
        df['Lat'], df['Lng'] = np.nan, np.nan

        if not df.empty:
            lng, lat = transformer.transform(df['Easting'].values, df['Northing'].values)
            df['Lng'] = lng
            df['Lat'] = lat

        # คำนวณ FreeBoard_m ถ้าไม่มีใน sheet: FreeBoard = Top - WaterLevel
        if 'FreeBoard_m' not in df.columns:
            if 'LevelTopUdrain' in df.columns and 'WaterLevel_m' in df.columns:
                df['FreeBoard_m'] = df['LevelTopUdrain'] - df['WaterLevel_m']
            elif 'LevelTopUdrain' in df.columns and 'WaterLevel_capped_m' in df.columns:
                df['FreeBoard_m'] = df['LevelTopUdrain'] - df['WaterLevel_capped_m']

        # ตัวแปร alias สำหรับ Lp (ใช้ Lp_m จาก Drop Inlet section เป็นหลัก)
        if 'Lp' not in df.columns and 'Lp_m' in df.columns:
            df['Lp'] = df['Lp_m']

        # WL_capped_m alias สำหรับ cross-section display
        if 'WL_capped_m' not in df.columns and 'WaterLevel_capped_m' in df.columns:
            df['WL_capped_m'] = df['WaterLevel_capped_m']

        # ปรับ DI_No เป็น int (กรณีมีจุดทศนิยม)
        df['DI_No'] = df['DI_No'].astype(int)

        # ปรับ zone ให้เป็น int (กรณีมี NaN ให้ใส่ 0)
        if 'zone' in df.columns:
            df['zone'] = pd.to_numeric(df['zone'], errors='coerce').fillna(0).astype(int)
        else:
            df['zone'] = 0

        return df
    except Exception as e:
        st.error(f"ไม่สามารถโหลดข้อมูลได้: {e}")
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

def safe_format(df, format_str="{:.3f}", na_rep="-"):
    styled_df = df.copy()
    for col in styled_df.columns:
        styled_df[col] = styled_df[col].apply(
            lambda x: format_str.format(x) if isinstance(x, (int, float, np.number)) and pd.notna(x)
            else (na_rep if pd.isna(x) else str(x))
        )
    return styled_df

def safe_get(row, key, default='-'):
    """ดึงค่าจาก row อย่างปลอดภัย ถ้าไม่มีคอลัมน์หรือค่าเป็น NaN ให้คืน default"""
    val = row.get(key, default)
    if isinstance(val, (int, float, np.number)) and pd.isna(val):
        return default
    return val

def display_zone_table(data_dict, format_str="{:.3f}"):
    """แสดงตาราง Parameter-Value สำหรับแต่ละ zone ใน Data Inspector"""
    df_disp = pd.DataFrame(list(data_dict.items()), columns=["Parameter", "Value"])
    st.dataframe(
        safe_format(df_disp, format_str=format_str).style.set_properties(
            **{'background-color': 'white', 'color': 'black'}
        ),
        hide_index=True,
        use_container_width=True
    )

# ==========================================
# 4. Load Data & Sidebar Filters
# ==========================================
df_all = load_google_sheet(ALIGN_CSV_URL)

if df_all is not None:
    if df_all.empty:
        st.error("ไม่พบข้อมูลใน Sheet ที่ระบุ กรุณาตรวจสอบชื่อ Sheet ใน Google Sheets")
        st.stop()

    st.sidebar.header("ตัวกรองข้อมูล (Filters)")

    # ---- Zone Filter (ใหม่: แยกตาม zone ใน sheet) ----
    available_zones = sorted([z for z in df_all['zone'].unique() if z > 0])
    if available_zones:
        selected_zones = st.sidebar.multiselect(
            "เลือก Zone:",
            options=available_zones,
            default=available_zones,
            format_func=lambda z: f"Zone {z}"
        )
        if not selected_zones:
            st.sidebar.warning("กรุณาเลือกอย่างน้อย 1 Zone")
            selected_zones = available_zones
        df_zoned = df_all[df_all['zone'].isin(selected_zones)].copy()
    else:
        df_zoned = df_all.copy()
        st.sidebar.info("ไม่พบข้อมูล Zone ใน sheet")

    # ---- Filter Mode (DI / KM) ----
    filter_mode = st.sidebar.radio("เลือกโหมดการกรอง:", ["กรองด้วย DI", "กรองด้วย KM"])

    df = df_zoned.copy()

    if filter_mode == "กรองด้วย DI":
        di_list_all = sorted(df_zoned['DI_No'].unique().tolist())
        col_di1, col_di2 = st.sidebar.columns(2)
        with col_di1:
            start_di = st.selectbox("เริ่มต้นที่ DI:", di_list_all, index=0)
        with col_di2:
            end_di = st.selectbox("สิ้นสุดที่ DI:", di_list_all, index=len(di_list_all)-1)

        if start_di > end_di:
            st.sidebar.error("DI เริ่มต้นต้องน้อยกว่าหรือเท่ากับ DI สิ้นสุด")
            df = df_zoned[(df_zoned['DI_No'] >= end_di) & (df_zoned['DI_No'] <= start_di)].copy()
        else:
            df = df_zoned[(df_zoned['DI_No'] >= start_di) & (df_zoned['DI_No'] <= end_di)].copy()
    else:
        min_km = float(df_zoned['KM_m'].min())
        max_km = float(df_zoned['KM_m'].max())
        km_range = st.sidebar.slider(
            "เลือกช่วง Chainage (KM)",
            min_value=min_km, max_value=max_km,
            value=(min_km, max_km), step=100.0
        )
        df = df_zoned[(df_zoned['KM_m'] >= km_range[0]) & (df_zoned['KM_m'] <= km_range[1])].copy()

    if not df.empty:
        km_min_val = df['KM_m'].min()
        km_max_val = df['KM_m'].max()
        di_min = df['DI_No'].min()
        di_max = df['DI_No'].max()
        zones_in_range = sorted(df['zone'].unique().tolist())

        zone_badges = " ".join([f"<span class='zone-badge'>Zone {z}</span>" for z in zones_in_range])

        st.sidebar.markdown(f"""
        <div class="range-info">
            <b>ช่วงข้อมูลที่เลือก:</b><br>
            <b>Zone:</b> {zone_badges}<br>
            <b>DI:</b> {di_min} ถึง {di_max}<br>
            <b>KM:</b> {format_km(km_min_val)} ถึง {format_km(km_max_val)}<br>
            <b>จำนวน:</b> {len(df)} จุด
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.warning("ไม่พบข้อมูลในช่วงที่เลือก")

    if 'selected_di' not in st.session_state:
        st.session_state.selected_di = int(df['DI_No'].iloc[0]) if not df.empty else None

    # ==========================================
    # 5. Main Tabs Layout
    # ==========================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "แผนที่ & ข้อมูล (Data Inspector)",
        "กราฟ Profile",
        "หน้าตัด U-Drain",
        "หน้าตัด Manhole (ยาว)",
        "ตารางสรุป & Export"
    ])

    # --------------------------------------------------
    # TAB 1: Map & Data Inspector (แยก zone ตามหมวด U-Drain / Manhole / Pipe Culvert)
    # --------------------------------------------------
    with tab1:
        col_map, col_info = st.columns([2, 1])

        with col_map:
            st.subheader("Plan View (Satellite)")
            if not df.empty:
                center_lat = df['Lat'].mean()
                center_lng = df['Lng'].mean()

                m = folium.Map(
                    location=[center_lat, center_lng], zoom_start=15,
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri, Maxar, Earthstar Geographics"
                )

                # วาดเส้นทางแยกตาม zone (สีต่างกัน)
                zone_colors = {1: "#FF4500", 2: "#1a237e", 3: "#2e7d32", 4: "#6a1b9a"}
                for z in zones_in_range:
                    df_z = df[df['zone'] == z]
                    if not df_z.empty:
                        route_coords = df_z[['Lat', 'Lng']].values.tolist()
                        folium.PolyLine(
                            route_coords,
                            color=zone_colors.get(z, "#FF4500"),
                            weight=4, opacity=0.9,
                            tooltip=f"Zone {z}"
                        ).add_to(m)

                for idx, row in df.iterrows():
                    z = int(row['zone'])
                    popup_html = (
                        f"<div style='background-color:white; padding:5px; border-radius:5px; color:black;'>"
                        f"<b>DI {int(row['DI_No'])}</b> <span style='color:{zone_colors.get(z,'#000')};'>(Zone {z})</span><br>"
                        f"KM: {format_km(row['KM_m'])}</div>"
                    )
                    folium.Marker(
                        location=[row['Lat'], row['Lng']],
                        popup=folium.Popup(popup_html, max_width=200),
                        tooltip=f"DI {int(row['DI_No'])} (Zone {z})",
                        icon=folium.Icon(color='green', icon='info-sign')
                    ).add_to(m)

                map_data = st_folium(m, width=800, height=500, returned_objects=["last_object_clicked"])

                if map_data.get('last_object_clicked') is not None:
                    click_lat = map_data['last_object_clicked']['lat']
                    click_lng = map_data['last_object_clicked']['lng']
                    df['dist'] = np.sqrt((df['Lat'] - click_lat)**2 + (df['Lng'] - click_lng)**2)
                    closest_idx = df['dist'].idxmin()
                    new_di = int(df.loc[closest_idx, 'DI_No'])
                    if new_di != st.session_state.selected_di:
                        st.session_state.selected_di = new_di
                        st.rerun()

        with col_info:
            st.subheader("Data Inspector")
            if not df.empty:
                di_list = sorted(df['DI_No'].unique().tolist())
                try:
                    current_index = di_list.index(st.session_state.selected_di)
                except:
                    current_index = 0

                selected_di = st.selectbox("เลือกจุด DI เพื่อดูข้อมูล:", di_list, index=current_index)
                st.session_state.selected_di = selected_di
                selected_row = df[df['DI_No'] == selected_di].iloc[0]

                # แสดง Zone ปัจจุบัน
                current_zone = int(selected_row.get('zone', 0))
                st.markdown(
                    f"<div class='range-info' style='margin-bottom:10px;'>"
                    f"<b>DI:</b> {selected_di} &nbsp;|&nbsp; "
                    f"<b>KM:</b> {format_km(selected_row['KM_m'])} &nbsp;|&nbsp; "
                    f"<span class='zone-badge'>Zone {current_zone}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # ============================================================
                # ZONE 1: U-Drain
                # ============================================================
                st.markdown('<div class="section-header">U-Drain</div>', unsafe_allow_html=True)
                udrain_data = {
                    "Rail Level [MSL]":              safe_get(selected_row, 'RailLevel'),
                    "Drain Invert Level [MSL]":      safe_get(selected_row, 'DrainInvertLevel'),
                    "Level Top U-drain [MSL]":       safe_get(selected_row, 'LevelTopUdrain'),
                    "Water Level [MSL]":             safe_get(selected_row, 'WaterLevel_m'),
                    "Depth [m]":                     safe_get(selected_row, 'Depth_m'),
                    "Free Board [m]":                safe_get(selected_row, 'FreeBoard_m'),
                    "Velocity [m/s]":                safe_get(selected_row, 'Velocity_ms'),
                    "Flow-Q [CMS]":                  safe_get(selected_row, 'Q_m3s'),
                    "Froude No.":                    safe_get(selected_row, 'Froude'),
                }
                display_zone_table(udrain_data)

                # ============================================================
                # ZONE 2: Manhole
                # ============================================================
                st.markdown('<div class="section-header">Manhole</div>', unsafe_allow_html=True)
                has_di_val = str(safe_get(selected_row, 'Has_DI', '')).upper()
                manhole_data = {
                    "Has-DI YES/NO":                 "YES" if has_di_val in ['1', '1.0', 'YES', 'Y', 'TRUE'] else "NO",
                    "WaterLevel_MSL-Manhole":        safe_get(selected_row, 'WaterLevel_m'),
                    "Manhole Level Bottom [MSL]":    safe_get(selected_row, 'DrainBase_m'),
                }
                display_zone_table(manhole_data)

                # ============================================================
                # ZONE 3: Pipe Culvert
                # ============================================================
                st.markdown('<div class="section-header">Pipe Culvert</div>', unsafe_allow_html=True)
                pipe_data = {
                    "Pipe Class":                    safe_get(selected_row, 'Pipe_Class'),
                    "Pipe Culvert Diameter [m]":     safe_get(selected_row, 'Pipe_D_m'),
                    "Upstream Invert HU [MSL]":      safe_get(selected_row, 'UpstreamInvertHU'),
                    "Downstream Invert HD [MSL]":    safe_get(selected_row, 'DownstreamInvertHD'),
                    "Existing Ground Level [MSL]":   safe_get(selected_row, 'ExistingGroundLevel'),
                    "Lp_[m]":                        safe_get(selected_row, 'Lp'),
                    "Slope_Pipe Culvert":            safe_get(selected_row, 'Pipe_Slope'),
                    "Velocity [m/s] Pipe Culvert":   safe_get(selected_row, 'Pipe_V_ms'),
                    "Flow-Q [CMS] Pipe Culvert":     safe_get(selected_row, 'Pipe_Qcap_m3s'),
                }
                display_zone_table(pipe_data)

    # --------------------------------------------------
    # TAB 2: Longitudinal Profile
    # --------------------------------------------------
    with tab2:
        st.subheader("Longitudinal Profile")
        if not df.empty:
            fig = go.Figure()
            if 'RailLevel' in df.columns:
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

            if not df.empty and 'RailLevel' in df.columns:
                fig.add_trace(go.Scatter(
                    x=[selected_row['KM_m']], y=[selected_row.get('RailLevel')],
                    mode='markers', name='Selected Node',
                    marker=dict(color='red', size=16, symbol='star', line=dict(color='black', width=1.5))
                ))

            fig.update_layout(
                title=dict(text="Profile (Elevation vs Chainage)", font=dict(color='black', size=16)),
                xaxis=dict(title=dict(text="Chainage (m)", font=dict(color='black')), tickfont=dict(color='black')),
                yaxis=dict(title=dict(text="Elevation (m.msl)", font=dict(color='black')), tickfont=dict(color='black')),
                hovermode="x unified",
                paper_bgcolor='white',
                plot_bgcolor='white',
                font=dict(color='black'),
                legend=dict(font=dict(color='black'))
            )
            st.plotly_chart(fig, use_container_width=True)

            html_bytes = fig.to_html(include_plotlyjs='cdn').encode('utf-8')
            st.download_button(label="ดาวน์โหลดกราฟ Profile (HTML)", data=html_bytes, file_name="Longitudinal_Profile.html", mime="text/html")

    # --------------------------------------------------
    # TAB 3: Cross Section U-Drain
    # --------------------------------------------------
    with tab3:
        st.subheader("Cross Section U-Drain")
        if not df.empty:
            row = df[df['DI_No'] == st.session_state.selected_di].iloc[0]
            B = 0.30  # สมมติ
            base = float(row.get('DrainInvertLevel', 0) or 0)
            top = float(row.get('LevelTopUdrain', base + 0.5) or (base + 0.5))
            wl = float(row.get('WaterLevel_m', base) or base)
            wl_capped = float(row.get('WL_capped_m', wl) or wl)
            rl = float(row.get('RailLevel', top + 1.0) or (top + 1.0))
            fb = top - wl

            fig_xsec = go.Figure()

            # วาดตัว U-Drain
            fig_xsec.add_shape(type="rect", x0=-B/2, y0=base, x1=B/2, y1=top, line=dict(color="black", width=2), fillcolor="lightgray")
            # วาดน้ำ
            if pd.notna(wl) and wl > base:
                wl_disp = min(wl, top)
                fig_xsec.add_shape(type="rect", x0=-B/2, y0=base, x1=B/2, y1=wl_disp, line=dict(color="blue", width=1), fillcolor="rgba(0, 191, 255, 0.5)")

            # เส้น Reference
            fig_xsec.add_hline(y=wl, line_dash="dash", line_color="green", annotation_text=f"WL: {wl:.3f}")
            fig_xsec.add_hline(y=top, line_dash="dot", line_color="purple", annotation_text=f"Top: {top:.3f}")
            fig_xsec.add_hline(y=rl, line_color="black", annotation_text=f"Rail: {rl:.3f}")

            # Dimension Lines
            fig_xsec.add_annotation(x=0, y=base - 0.1, text=f"Width = {B:.3f} m", showarrow=False, bgcolor="white", font=dict(color="black"))
            fig_xsec.add_shape(type="line", x0=-B/2, y0=base - 0.08, x1=B/2, y1=base - 0.08, line=dict(color="black", width=1, dash="dash"))
            fig_xsec.add_shape(type="line", x0=-B/2, y0=base - 0.10, x1=-B/2, y1=base - 0.06, line=dict(color="black", width=1))
            fig_xsec.add_shape(type="line", x0=B/2, y0=base - 0.10, x1=B/2, y1=base - 0.06, line=dict(color="black", width=1))

            if wl > base:
                fig_xsec.add_annotation(x=B/2 + 0.05, y=(base+wl)/2, text=f"y = {wl-base:.3f} m", showarrow=False, bgcolor="white", font=dict(color="black"))
                fig_xsec.add_shape(type="line", x0=B/2 + 0.02, y0=base, x1=B/2 + 0.02, y1=wl, line=dict(color="black", width=1, dash="dash"))

            if fb > 0:
                fig_xsec.add_annotation(x=B/2 + 0.05, y=(wl+top)/2, text=f"FB = {fb:.3f} m", showarrow=False, bgcolor="white", font=dict(color="black"))
                fig_xsec.add_shape(type="line", x0=B/2 + 0.02, y0=wl, x1=B/2 + 0.02, y1=top, line=dict(color="black", width=1, dash="dash"))

            fig_xsec.update_layout(
                title=dict(text=f"Cross Section U-Drain @ DI {st.session_state.selected_di} (KM {format_km(row['KM_m'])})", font=dict(color='black', size=16)),
                xaxis=dict(title=dict(text="Width (m)", font=dict(color='black')), tickfont=dict(color='black')),
                yaxis=dict(title=dict(text="Elevation (m.msl)", font=dict(color='black')), tickfont=dict(color='black')),
                xaxis_range=[-B*2, B*2], yaxis_range=[base - 0.5, max(top, rl) + 1],
                showlegend=False, height=500,
                paper_bgcolor='white',
                plot_bgcolor='white',
                font=dict(color='black')
            )
            st.plotly_chart(fig_xsec, use_container_width=True)

            v_val = float(row.get('Velocity_ms', 0) or 0)
            q_val = float(row.get('Q_m3s', 0) or 0)
            fr_val = float(row.get('Froude', 0) or 0)

            st.markdown(f"""
            <div class="metric-box">
                <b>Hydraulic Properties:</b><br>
                - Velocity: {v_val:.3f} m/s<br>
                - Flow-Q: {q_val:.4f} CMS<br>
                - Froude No.: {fr_val:.3f}<br>
                - Water Level: {wl:.3f} m.msl<br>
                - Capped Water Level: {wl_capped:.3f} m.msl
            </div>
            """, unsafe_allow_html=True)

            html_xsec = fig_xsec.to_html(include_plotlyjs='cdn').encode('utf-8')
            st.download_button(label="ดาวน์โหลด U-Drain (HTML)", data=html_xsec, file_name=f"UDrain_DI_{st.session_state.selected_di}.html", mime="text/html")

    # --------------------------------------------------
    # TAB 4: Cross Section Manhole & Culvert (Longitudinal)
    # --------------------------------------------------
    with tab4:
        st.subheader("หน้าตัด Manhole & Culvert (แนวยาว)")
        if not df.empty:
            row = df[df['DI_No'] == st.session_state.selected_di].iloc[0]

            base_inv = float(row.get('DrainBase_m', row.get('DrainInvertLevel', 0) or 0))
            wl_mh = float(row.get('WaterLevel_m', 0) or 0)
            pipe_dia = float(row.get('Pipe_D_m', 0.6) or 0.6)
            pipe_class = row.get('Pipe_Class', '-')
            hu = float(row.get('UpstreamInvertHU', 0) or 0)
            hd = float(row.get('DownstreamInvertHD', 0) or 0)
            lp = float(row.get('Lp', row.get('Lp_m', 9.0) or 9.0))
            slope = float(row.get('Pipe_Slope', 0) or 0)
            v_pipe = float(row.get('Pipe_V_ms', 0) or 0)
            q_pipe = float(row.get('Pipe_Qcap_m3s', 0) or 0)

            top_level = float(row.get('LevelTopUdrain', base_inv + 0.5) or (base_inv + 0.5))
            eg = float(row.get('ExistingGroundLevel', top_level + 0.5) or (top_level + 0.5))
            mh_bottom = float(row.get('ManholeLevelBottom', row.get('DrainBase_m', base_inv - 1.8) or (base_inv - 1.8)))

            fig_long = go.Figure()

            # 1. ผิวดิน (EG)
            fig_long.add_trace(go.Scatter(x=[-1, lp+1], y=[eg, eg], mode='lines', name='Existing Ground', line=dict(color='#8d6e63', width=3)))

            # 2. ตัว Manhole
            fig_long.add_shape(type="rect", x0=-0.5, y0=mh_bottom, x1=0.5, y1=top_level, line=dict(color="black", width=2), fillcolor="lightgray")

            # 3. ท่อ Culvert (HU -> HD)
            fig_long.add_trace(go.Scatter(x=[0, lp], y=[hu, hd], mode='lines', name='Pipe Culvert', line=dict(color='blue', width=2)))

            # 4. ท้องท่อ Invert
            fig_long.add_hline(y=base_inv, line_dash="dot", line_color="purple", annotation_text=f"Invert: {base_inv:.3f}")

            # Dimension Lines
            fig_long.add_annotation(x=lp/2, y=hd - 0.2, text=f"Lp = {lp:.3f} m", showarrow=False, bgcolor="white", font=dict(color="black"))
            fig_long.add_shape(type="line", x0=0, y0=hd - 0.15, x1=lp, y1=hd - 0.15, line=dict(color="black", width=1, dash="dash"))
            fig_long.add_shape(type="line", x0=0, y0=hd - 0.18, x1=0, y1=hd - 0.12, line=dict(color="black", width=1))
            fig_long.add_shape(type="line", x0=lp, y0=hd - 0.18, x1=lp, y1=hd - 0.12, line=dict(color="black", width=1))

            fig_long.add_annotation(x=-0.2, y=hu, text=f"HU: {hu:.3f}", showarrow=False, bgcolor="white", font=dict(color="black"))
            fig_long.add_annotation(x=lp+0.2, y=hd, text=f"HD: {hd:.3f}", showarrow=False, bgcolor="white", font=dict(color="black"))

            fig_long.update_layout(
                title=dict(text=f"Longitudinal Section @ DI {st.session_state.selected_di} (KM {format_km(row['KM_m'])})", font=dict(color='black', size=16)),
                xaxis=dict(title=dict(text="Distance (m)", font=dict(color='black')), tickfont=dict(color='black')),
                yaxis=dict(title=dict(text="Elevation (m.msl)", font=dict(color='black')), tickfont=dict(color='black')),
                xaxis_range=[-1.5, lp+1.5], yaxis_range=[mh_bottom - 1, eg + 1],
                showlegend=True, height=500,
                paper_bgcolor='white',
                plot_bgcolor='white',
                font=dict(color='black'),
                legend=dict(font=dict(color='black'))
            )
            st.plotly_chart(fig_long, use_container_width=True)

            has_di_val = str(row.get('Has_DI', '')).upper()
            has_di_display = 'YES' if has_di_val in ['YES', '1', '1.0', 'Y', 'TRUE'] else 'NO'

            st.markdown(f"""
            <div class="metric-box">
                <b>Manhole & Culvert Properties:</b><br>
                - Has-DI YES/NO: {has_di_display}<br>
                - WaterLevel_MSL-Manhole: {wl_mh:.3f} m.msl<br>
                - Manhole Level Bottom: {mh_bottom:.3f} m.msl<br>
                <b>Pipe Culvert:</b><br>
                - Pipe Class: {pipe_class}<br>
                - Pipe Culvert Diameter: {pipe_dia:.3f} m<br>
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
            st.download_button(label="ดาวน์โหลด Manhole (HTML)", data=html_long, file_name=f"Manhole_Long_DI_{st.session_state.selected_di}.html", mime="text/html")

    # --------------------------------------------------
    # TAB 5: Data Tables & Export (แยกหมวดหมู่)
    # --------------------------------------------------
    with tab5:
        st.subheader("ตารางข้อมูลผลลัพธ์แยกหมวดหมู่")

        # หมวดที่ 1: Hydraulic Results (U-Drain)
        st.markdown('<div class="section-header">1. Hydraulic Results (U-Drain)</div>', unsafe_allow_html=True)
        hydraulic_cols = [
            'DI_No', 'zone', 'KM_m', 'RailLevel', 'LevelTopUdrain', 'DrainInvertLevel',
            'WaterLevel_m', 'Depth_m', 'FreeBoard_m', 'Velocity_ms', 'Q_m3s', 'Froude',
            'Qcap_m3s', 'Shear_Pa', 'Shields', 'BedLoad_m2s', 'Tc_min', 'To_min',
            'Td_min', 'Intensity_mmhr', 'Has_DI'
        ]
        hydraulic_cols_show = [c for c in hydraulic_cols if c in df.columns]
        df_hydraulic = df[hydraulic_cols_show].copy()
        if 'KM_m' in df_hydraulic.columns:
            df_hydraulic['KM_m'] = df_hydraulic['KM_m'].apply(format_km)
        st.dataframe(df_hydraulic.style.set_properties(**{'background-color': 'white', 'color': 'black'}), use_container_width=True)

        # หมวดที่ 2: Drop Inlet System (Manhole + Pipe Culvert)
        st.markdown('<div class="section-header">2. Drop Inlet System (Manhole + Pipe Culvert)</div>', unsafe_allow_html=True)
        drop_inlet_cols = [
            'DI_No', 'zone', 'KM_m', 'DrainBase_m', 'WaterLevel_m', 'Q_m3s',
            'DI_Wi_m', 'DI_Li_m', 'DI_Di_m', 't_wall_m', 'Pipe_D_m',
            'Pipe_Class', 'UpstreamInvertHU', 'DownstreamInvertHD', 'Lp', 'Pipe_Slope',
            'Pipe_V_ms', 'Pipe_Qcap_m3s', 'HCR', 'Cover_m', 'CoverStatus', 'ScourStatus', 'Has_DI'
        ]
        drop_inlet_cols_show = [c for c in drop_inlet_cols if c in df.columns]
        df_drop_inlet = df[drop_inlet_cols_show].copy()
        if 'KM_m' in df_drop_inlet.columns:
            df_drop_inlet['KM_m'] = df_drop_inlet['KM_m'].apply(format_km)
        st.dataframe(df_drop_inlet.style.set_properties(**{'background-color': 'white', 'color': 'black'}), use_container_width=True)

        # Export CSV
        csv_data = convert_df_to_csv(df)
        st.download_button(label="ดาวน์โหลดตารางข้อมูลทั้งหมด (CSV)", data=csv_data, file_name="RLDA_Data_Export.csv", mime="text/csv")

else:
    st.error("เกิดข้อผิดพลาดในการโหลดข้อมูล")
