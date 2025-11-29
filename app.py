import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | MANAGER PRO", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    
    /* TABS & PANELS */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: #1a1c24; padding: 10px; border-radius: 10px; margin-top: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #333; border-radius: 5px; color: white; padding: 5px 20px; border: 1px solid #555; }
    .stTabs [aria-selected="true"] { background-color: #3b82f6 !important; font-weight: bold; border: 1px solid #3b82f6; }
    
    /* LICZNIKI DOSTĘPNOŚCI */
    .avail-badge {
        background-color: #1f2937;
        border: 1px solid #4b5563;
        padding: 5px 10px;
        border-radius: 15px;
        font-size: 12px;
        color: #fbbf24;
        margin-bottom: 10px;
        display: inline-block;
    }

    /* TABELA GRAFIKU */
    .schedule-table { width: 100%; border-collapse: collapse; color: #000; background-color: #fff; font-family: Arial, sans-serif; font-size: 11px; }
    .schedule-table th { background-color: #444; color: #fff; padding: 8px; border: 1px solid #777; text-align: center; }
    .schedule-table td { border: 1px solid #ccc; padding: 4px; vertical-align: top; text-align: center; height: 60px; width: 12.5%; }
    .highlight-day { background-color: #e3f2fd !important; } 
    .role-header { background-color: #eee; font-weight: bold; text-align: center; vertical-align: middle !important; border: 1px solid #999; font-size: 12px; }
    
    /* ZMIANY */
    .shift-box { background-color: #fff; border: 1px solid #aaa; border-radius: 3px; margin-bottom: 3px; padding: 2px; box-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
    .shift-time { font-weight: bold; display: block; color: #000; font-size: 10px; }
    .shift-name { display: block; color: #333; text-transform: uppercase; font-size: 9px; line-height: 1.1; }
    
    /* WAKATY */
    .empty-shift-box { background-color: #ffcccc; border: 2px solid #ff0000; border-radius: 3px; margin-bottom: 3px; padding: 2px; min-height: 20px; }
    .empty-time { font-weight: bold; display: block; color: #cc0000; font-size: 10px; }
    
    .day-header { font-size: 12px; text-transform: uppercase; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA UŻYTKOWNIKÓW ---
USERS = {
    "admin":  {"pass": "AlastorRules", "role": "manager", "name": "Szef"},
    "kierownik": {"pass": "film123", "role": "manager", "name": "Kierownik"},
    "julia":  {"pass": "julia1", "role": "worker", "name": "Julia Bąk"},
    "kacper": {"pass": "kacper1", "role": "worker", "name": "Kacper Borzechowski"},
}

# --- FUNKCJE LOGICZNE ---
def calculate_auto_roles(selected_roles):
    auto = ["Sprzątanie Generalne"]
    if "Bar" in selected_roles: auto.append("Inwentaryzacja")
    if "Bar" in selected_roles and "Obsługa" in selected_roles:
        auto.extend(["Pomoc Bar", "Pomoc Obsługa"])
    return list(set(auto))

def check_login(u, p):
    if u in USERS and USERS[u]["pass"] == p: return USERS[u]
    return None

def clean_text(text):
    if not isinstance(text, str): text = str(text)
    replacements = {'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z', '–':'-'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def is_availability_locked():
    now = datetime.now()
    if now.weekday() == 0 and now.hour >= 23: return True
    if now.weekday() > 0: return True 
    return False 

# --- PARSER DYSPOZYCJI ---
def is_avail_compatible(avail_str, shift_type):
    if not avail_str or avail_str == "-" or len(avail_str) < 3: return False
    clean = avail_str.replace(" ", "").split("/")[0]
    try:
        parts = re.split(r'[-–]', clean)
        if len(parts) != 2: return False
        s, e = int(parts[0]), int(parts[1])
        if shift_type == 'morning':
            if (6 <= s <= 12) and (e >= 15 or e <= 4): return True
        elif shift_type == 'evening':
            if (s <= 17) and (e <= 4 or e >= 22): return True
    except: return False
    return False

# Funkcja licząca dostępnych ludzi (do Radaru)
def count_available_staff(date_obj, employees_df, avail_grid):
    morning_count = 0
    evening_count = 0
    for idx, emp in employees_df.iterrows():
        key = f"{emp['Imie']}_{date_obj.strftime('%Y-%m-%d')}"
        avail = avail_grid.get(key, "")
        if is_avail_compatible(avail, "morning"): morning_count += 1
        if is_avail_compatible(avail, "evening"): evening_count += 1
    return morning_count, evening_count

def find_worker_for_shift(role_needed, shift_time_type, date_obj, employees_df, avail_grid, assigned_today):
    candidates = []
    for idx, emp in employees_df.iterrows():
        if emp['Imie'] in assigned_today[shift_time_type]: continue
        
        role_base = role_needed.replace(" 1", "").replace(" 2", "")
        if role_base in emp['Role'] or role_base in emp['Auto']:
            key = f"{emp['Imie']}_{date_obj.strftime('%Y-%m-%d')}"
            avail = avail_grid.get(key, "")
            if is_avail_compatible(avail, shift_time_type):
                candidates.append(emp)

    if not candidates: return None

    final_candidate_name = None
    if role_needed == "Obsługa":
        men = [c['Imie'] for c in candidates if c.get('Plec', 'K') == 'M']
        if men: final_candidate_name = random.choice(men)
        else:
            women = [c['Imie'] for c in candidates if c.get('Plec', 'M') == 'K']
            if women: final_candidate_name = random.choice(women)
    else:
        final_candidate_name = random.choice([c['Imie'] for c in candidates])
    return final_candidate_name

# --- HTML RENDER ---
def render_html_schedule(df_shifts, start_date):
    pl_days = {0: "PIĄTEK", 1: "SOBOTA", 2: "NIEDZIELA", 3: "PONIEDZIAŁEK", 4: "WTOREK", 5: "ŚRODA", 6: "CZWARTEK"}
    days = [start_date + timedelta(days=i) for i in range(7)]
    date_header_str = f"{start_date.strftime('%d.%m')} - {days[-1].strftime('%d.%m')}"
    
    html = f"""
    <div style="background-color: #333; color: white; padding: 10px; text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 0px; border-radius: 5px 5px 0 0;">
        GRAFIK: {date_header_str}
    </div>
    <table class="schedule-table">
    <thead><tr><th style="width: 8%;">STANOWISKO</th>
    """
    for d in days:
        w_day = d.weekday()
        day_map = {4:"PIĄTEK", 5:"SOBOTA", 6:"NIEDZIELA", 0:"PONIEDZIAŁEK", 1:"WTOREK", 2:"ŚRODA", 3:"CZWARTEK"}
        d_name = day_map[w_day]
        style = 'style="background-color: #2c5282;"' if w_day in [1, 5, 6] else ''
        html += f'<th {style}><div class="day-header">{d_name}<br>{d.strftime("%d.%m")}</div></th>'
    html += '</tr></thead><tbody>'
    
    visual_roles = ["Obsługa", "Kasa", "Bar 1", "Bar 2", "Cafe"]
    for role in visual_roles:
        html += f'<tr><td class="role-header">{role.upper()}</td>'
        for d in days:
            w_day = d.weekday()
            td_class = 'class="highlight-day"' if w_day in [1, 5, 6] else ''
            current_shifts = df_shifts[(df_shifts['Data'] == d) & (df_shifts['Stanowisko'].str.contains(role, regex=False))]
            cell_content = ""
            for _, row in current_shifts.iterrows():
                if row['Pracownik_Imie'] == "" or row['Pracownik_Imie'] == "WAKAT":
                    cell_content += f'<div class="empty-shift-box"><span class="empty-time">{row["Godziny"]}</span></div>'
                else:
                    display_pos = "(Combo)" if "+" in row['Stanowisko'] else ""
                    short = row['Pracownik_Imie'].split(" ")[0] + " " + row['Pracownik_Imie'].split(" ")[-1][0] + "."
                    cell_content += f'<div class="shift-box"><span class="shift-time">{row["Godziny"]}</span><span class="shift-name">{short} {display_pos}</span></div>'
            html += f'<td {td_class}>{cell_content}</td>'
        html += '</tr>'
    html += '</tbody></table>'
    return html

def generate_schedule_pdf(df_shifts, title):
    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean_text(title), ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", '', 8)
    days = sorted(df_shifts['Data'].unique())
    for day in days:
        d_str = day.strftime('%d.%m (%A)')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, clean_text(f"--- {d_str} ---"), ln=True)
        pdf.set_font("Arial", '', 10)
        day_shifts = df_shifts[df_shifts['Data'] == day]
        for _, row in day_shifts.sort_values(by=["Stanowisko"]).iterrows():
            name = row['Pracownik_Imie'] if row['Pracownik_Imie'] else "---"
            line = f"{row['Stanowisko']} | {row['Godziny']} | {name}"
            pdf.cell(0, 8, clean_text(line), ln=True, border=1)
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')

# --- DATA SEEDING ---
def preload_demo_data(start_date):
    demo_avail = {
        "Julia Bąk": ["16-1", "-", "8-1", "-", "16-1", "-", "16-1"], 
        "Kacper Borzechowski": ["-", "8-1", "8-1", "16-1", "8-1", "16-1", "16-1"],
        # Reszta pracowników...
    }
    days = [start_date + timedelta(days=i) for i in range(7)]
    for name, avails in demo_avail.items():
        for i, val in enumerate(avails):
            key = f"{name}_{days[i].strftime('%Y-%m-%d')}"
            if key not in st.session_state.avail_grid: # Tylko jeśli puste
                st.session_state.avail_grid[key] = val

# --- PAMIĘĆ SESJI ---
def reset_database():
    raw_data = [
        {"Imie": "Julia Bąk", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"], "Plec": "K"},
        {"Imie": "Kacper Borzechowski", "Role": ["Bar", "Obsługa", "Plakaty (Techniczne)"], "Plec": "M"},
        {"Imie": "Wiktor Buc", "Role": ["Obsługa"], "Plec": "M"},
        {"Imie": "Anna Dubińska", "Role": ["Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Julia Fidor", "Role": ["Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Julia Głowacka", "Role": ["Cafe", "Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Martyna Grela", "Role": ["Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Weronika Jabłońska", "Role": ["Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Jarosław Kaca", "Role": ["Bar", "Obsługa"], "Plec": "M"},
        {"Imie": "Michał Kowalczyk", "Role": ["Obsługa"], "Plec": "M"},
        {"Imie": "Dominik Mleczkowski", "Role": ["Cafe", "Bar", "Obsługa"], "Plec": "M"},
        {"Imie": "Aleksandra Pacek", "Role": ["Cafe", "Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Paweł Pod", "Role": ["Obsługa"], "Plec": "M"},
        {"Imie": "Aleksander Prus", "Role": ["Obsługa"], "Plec": "M"},
        {"Imie": "Julia Pyrka", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"], "Plec": "K"},
        {"Imie": "Wiktoria Siara", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"], "Plec": "K"},
        {"Imie": "Damian Siwak", "Role": ["Obsługa"], "Plec": "M"},
        {"Imie": "Katarzyna Stanisławska", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"], "Plec": "K"},
        {"Imie": "Patryk Szczodry", "Role": ["Obsługa"], "Plec": "M"},
        {"Imie": "Anna Szymańska", "Role": ["Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Hubert War", "Role": ["Bar", "Obsługa", "Plakaty (Techniczne)"], "Plec": "M"},
        {"Imie": "Marysia Wojtysiak", "Role": ["Cafe", "Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Michał Wojtysiak", "Role": ["Obsługa"], "Plec": "M"},
        {"Imie": "Weronika Ziętkowska", "Role": ["Cafe", "Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Magda Żurowska", "Role": ["Bar", "Obsługa"], "Plec": "K"}
    ]
    raw_data.sort(key=lambda x: x['Imie'].split()[-1])
    rows = []
    for i, p in enumerate(raw_data):
        rows.append({"ID": i+1, "Imie": p["Imie"], "Role": p["Role"], "Plec": p["Plec"], "Auto": calculate_auto_roles(p["Role"])})
    st.session_state.employees = pd.DataFrame(rows)

if 'employees' not in st.session_state or 'Plec' not in st.session_state.employees.columns: reset_database()
if 'shifts' not in st.session_state: st.session_state.shifts = pd.DataFrame(columns=["Data", "Stanowisko", "Godziny", "Pracownik_Imie", "Typ"])
if 'avail_grid' not in st.session_state: st.session_state.avail_grid = {}
if 'work_logs' not in st.session_state: st.session_state.work_logs = pd.DataFrame(columns=["Pracownik", "Data", "Start", "Koniec", "Godziny"])
# PAMIĘĆ USTAWIEŃ GENERATORA
if 'gen_config' not in st.session_state: st.session_state.gen_config = {}

# ==========================================
# LOGOWANIE
# ==========================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #d93025;'>ETHER SYSTEM</h1>", unsafe_allow_html=True)
        u = st.text_input("Login")
        p = st.text_input("Hasło", type="password")
        if st.button("ZALOGUJ"):
            user_data = check_login(u, p)
            if user_data:
                st.session_state.logged_in = True
                st.session_state.user_role = user_data["role"]
                st.session_state.user_name = user_data["name"]
                st.rerun()
            else: st.error("Błąd.")
    st.stop()

# ==========================================
# MENEDŻER
# ==========================================
if st.session_state.user_role == "manager":
    with st.sidebar:
        st.title("🔧 PANEL KIEROWNIKA")
        menu = st.radio("Nawigacja:", ["Auto-Planer (LOGISTIC)", "Dyspozycje (Szybkie)", "Kadry", "Grafik (WIZUALNY)"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # --- 1. AUTO-PLANER (LOGISTIC) ---
    if menu == "Auto-Planer (LOGISTIC)":
        st.title("🚀 Generator Logistyczny")
        
        today = datetime.now().date()
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_friday = today + timedelta(days=days_ahead)
        if today.weekday() == 4: next_friday = today

        with st.container(border=True):
            st.markdown("### 1. Wybierz Tydzień")
            week_start = st.date_input("Start cyklu (Tylko przyszłe Piątki):", next_friday, min_value=today)
            if week_start.weekday() != 4:
                st.error("⛔ BŁĄD: Grafiki w kinie muszą zaczynać się w PIĄTEK!")
                st.stop()
            week_end = week_start + timedelta(days=6)
            st.info(f"📅 Planujesz grafik na okres: **{week_start.strftime('%d.%m')} (Pt) - {week_end.strftime('%d.%m')} (Cz)**")
        
        preload_demo_data(week_start)
        
        week_days = [week_start + timedelta(days=i) for i in range(7)]
        day_labels = ["PIĄTEK", "SOBOTA", "NIEDZIELA", "PONIEDZIAŁEK", "WTOREK", "ŚRODA", "CZWARTEK"]
        
        tabs = st.tabs([f"{day_labels[i]} {d.strftime('%d.%m')}" for i, d in enumerate(week_days)])
        
        # ZMIENNA DO PRZECHOWYWANIA KONFIGURACJI Z CAŁEGO TYGODNIA
        week_final_config = []

        for i, tab in enumerate(tabs):
            with tab:
                current_day_key = f"day_{i}"
                
                # RADAR DOSTĘPNOŚCI (NOWOŚĆ)
                m_count, e_count = count_available_staff(week_days[i], st.session_state.employees, st.session_state.avail_grid)
                st.markdown(f"<div class='avail-badge'>👥 Dostępnych: {m_count} Rano / {e_count} Wieczorem</div>", unsafe_allow_html=True)
                
                with st.container(border=True):
                    # UŻYWAMY SESJI ABY ZAPAMIĘTAĆ WARTOŚCI (key=...)
                    c_t1, c_t2, c_t3 = st.columns(3)
                    s1 = c_t1.time_input(f"1. Film", time(9,0), key=f"s1_{i}")
                    sl = c_t2.time_input(f"Start Ost.", time(21,0), key=f"sl_{i}")
                    el = c_t3.time_input(f"Koniec Ost.", time(0,0), key=f"el_{i}")
                    
                    st.write("---")
                    st.markdown("##### Obsada w tym dniu:")
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    k = c1.selectbox("KASA", [0,1,2], index=1, key=f"k_{i}")
                    b1 = c2.selectbox("BAR 1", [0,1,2,3], index=1, key=f"b1_{i}")
                    b2 = c3.selectbox("BAR 2", [0,1,2], index=1, key=f"b2_{i}")
                    c = c4.selectbox("CAFE", [0,1,2], index=1, key=f"c_{i}")
                    om = c5.selectbox("OBS RANO", [1,2,3], index=1, key=f"om_{i}")
                    oe = c6.selectbox("OBS NOC", [1,2,3,4], index=2, key=f"oe_{i}")
                
                week_final_config.append({
                    "date": week_days[i], "times": (s1, sl, el), "counts": (k, b1, b2, c, om, oe)
                })

        st.write("---")
        if st.button("⚡ GENERUJ CAŁY TYDZIEŃ", type="primary"):
            mask = (st.session_state.shifts['Data'] >= week_days[0]) & (st.session_state.shifts['Data'] <= week_days[-1])
            st.session_state.shifts = st.session_state.shifts[~mask]
            
            cnt = 0
            for day_cfg in week_final_config:
                current_date = day_cfg['date']
                s1, sl, el = day_cfg['times']
                k, b1, b2, c, om, oe = day_cfg['counts']
                
                dt_start = datetime.combine(datetime.today(), s1) - timedelta(minutes=45)
                t_open = dt_start.strftime("%H:%M")
                t_bar_end = (datetime.combine(datetime.today(), sl) + timedelta(minutes=15)).strftime("%H:%M")
                t_obs_end = (datetime.combine(datetime.today(), el) + timedelta(minutes=15)).strftime("%H:%M")
                t_split = "16:00"
                
                daily_tasks = []
                for _ in range(k): daily_tasks.append(("Kasa", "morning", t_open, t_split)); daily_tasks.append(("Kasa", "evening", t_split, t_bar_end))
                for _ in range(b1): daily_tasks.append(("Bar 1", "morning", t_open, t_split)); daily_tasks.append(("Bar 1", "evening", t_split, t_bar_end))
                for _ in range(b2): daily_tasks.append(("Bar 2", "morning", t_open, t_split)); daily_tasks.append(("Bar 2", "evening", t_split, t_bar_end))
                for _ in range(c): daily_tasks.append(("Cafe", "morning", t_open, t_split)); daily_tasks.append(("Cafe", "evening", t_split, t_bar_end))
                for _ in range(om): daily_tasks.append(("Obsługa", "morning", t_open, t_split))
                for _ in range(oe): daily_tasks.append(("Obsługa", "evening", t_split, t_obs_end))
                
                assigned_today = {'morning': [], 'evening': []}
                for role, t_type, s, e in daily_tasks:
                    worker_name = find_worker_for_shift(role, t_type, current_date, st.session_state.employees, st.session_state.avail_grid, assigned_today)
                    final = worker_name if worker_name is not None else ""
                    st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                        "Data": current_date, "Stanowisko": role, "Godziny": f"{s}-{e}", "Pracownik_Imie": final, "Typ": "Auto"
                    }
                    if worker_name is not None: assigned_today[t_type].append(worker_name)
                    cnt += 1
            
            st.success(f"✅ Wygenerowano {cnt} zmian! Sprawdź wynik poniżej lub w zakładce 'Grafik'.")
            
            # PODGLĄD WYNIKU OD RAZU (NOWOŚĆ)
            with st.expander("🔎 Szybki Podgląd Grafiku", expanded=True):
                preview_mask = (st.session_state.shifts['Data'] >= week_days[0]) & (st.session_state.shifts['Data'] <= week_days[-1])
                df_prev = st.session_state.shifts.loc[preview_mask]
                st.markdown(render_html_schedule(df_prev, week_start), unsafe_allow_html=True)

    # --- 2. DYSPOZYCJE ---
    elif menu == "Dyspozycje (Szybkie)":
        st.title("📥 Dyspozycje")
        today = datetime.now().date()
        d_start = st.date_input("Start tygodnia (Piątek):", today, min_value=today)
        days = [d_start + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
        
        with st.form("grid_form"):
            cols = st.columns([3, 2, 1, 2, 2, 2, 2, 2, 2])
            cols[0].write("**Pracownik**")
            cols[1].write(f"**Pt**")
            cols[2].write(">>")
            for i in range(1, 7): cols[i+2].write(f"**{day_names[i]}**")
            
            for idx, emp in st.session_state.employees.iterrows():
                r_cols = st.columns([3, 2, 1, 2, 2, 2, 2, 2, 2])
                r_cols[0].write(f"👤 {emp['Imie']}")
                key_fri = f"{emp['Imie']}_{days[0].strftime('%Y-%m-%d')}"
                val_fri = st.session_state.avail_grid.get(key_fri, "")
                new_fri = r_cols[1].text_input("Pt", val_fri, key=key_fri, label_visibility="collapsed")
                st.session_state.avail_grid[key_fri] = new_fri
                copy = r_cols[2].checkbox("Ty.", key=f"copy_{emp['ID']}")
                for i in range(1, 7):
                    key = f"{emp['Imie']}_{days[i].strftime('%Y-%m-%d')}"
                    if copy:
                        st.session_state.avail_grid[key] = new_fri
                        val = new_fri
                        disabled = True
                    else:
                        val = st.session_state.avail_grid.get(key, "")
                        disabled = False
                    new_val = r_cols[i+2].text_input(day_names[i], val, key=key, label_visibility="collapsed", disabled=disabled)
                    if not disabled: st.session_state.avail_grid[key] = new_val
            st.form_submit_button("💾 ZAPISZ WSZYSTKO")

    # --- 3. KADRY ---
    elif menu == "Kadry":
        st.title("📇 Kadry (A-Z)")
        display_df = st.session_state.employees[["ID", "Imie", "Role", "Plec"]].copy().rename(columns={"ID": "Lp."})
        st.dataframe(display_df, hide_index=True)

    # --- 4. GRAFIK (WIZUALNY) ---
    elif menu == "Grafik (WIZUALNY)":
        st.title("📋 Grafik Wizualny")
        today = datetime.now().date()
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_friday = today + timedelta(days=days_ahead)
        if today.weekday() == 4: next_friday = today
        
        d_start = st.date_input("Pokaż tydzień od (Piątek):", next_friday)
        d_end = d_start + timedelta(days=6)
        mask = (st.session_state.shifts['Data'] >= d_start) & (st.session_state.shifts['Data'] <= d_end)
        df_view = st.session_state.shifts.loc[mask]
        
        if not df_view.empty:
            html_table = render_html_schedule(df_view, d_start)
            st.markdown(html_table, unsafe_allow_html=True)
            st.write("---")
            if st.button("🖨️ POBIERZ PDF"):
                pdf_bytes = generate_schedule_pdf(df_view, f"GRAFIK: {d_start.strftime('%d.%m')} - {d_end.strftime('%d.%m')}")
                st.download_button("Pobierz Plik", pdf_bytes, "grafik.pdf", "application/pdf")
        else:
            st.info("Brak grafiku.")

# ==========================================
# PRACOWNIK
# ==========================================
elif st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        st.caption("Panel Pracownika")
        menu = st.radio("Menu:", ["📅 Mój Grafik", "✍️ Moja Dyspozycyjność", "⏱️ Karta Czasu Pracy"])
        st.divider()
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # 1. MÓJ GRAFIK
    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        my_shifts = st.session_state.shifts[st.session_state.shifts['Pracownik_Imie'] == st.session_state.user_name]
        
        if not my_shifts.empty:
            st.dataframe(my_shifts[["Data", "Stanowisko", "Godziny"]], use_container_width=True)
        else:
            st.info("Nie masz zmian w najbliższym grafiku.")

    # 2. DYSPOZYCJE
    elif menu == "✍️ Moja Dyspozycyjność":
        st.title("Moja Dyspozycyjność")
        is_locked = is_availability_locked()
        if is_locked: st.error("🔒 Edycja zablokowana (po terminie).")
        else: st.success("🔓 Edycja otwarta.")
        
        today = datetime.now().date()
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_friday = today + timedelta(days=days_ahead)
        days = [next_friday + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
        
        with st.form("worker_avail"):
            cols = st.columns(7)
            for i, d in enumerate(days):
                cols[i].write(f"**{day_names[i]}** {d.strftime('%d.%m')}")
                key = f"{st.session_state.user_name}_{d.strftime('%Y-%m-%d')}"
                val = st.session_state.avail_grid.get(key, "")
                new_val = cols[i].text_input("h", val, key=f"w_{key}", disabled=is_locked, label_visibility="collapsed")
                if not is_locked: st.session_state.avail_grid[key] = new_val
            
            st.form_submit_button("Zapisz", disabled=is_locked)

    # 3. KARTA CZASU
    elif menu == "⏱️ Karta Czasu Pracy":
        st.title("Ewidencja")
        my_shifts = st.session_state.shifts[st.session_state.shifts['Pracownik_Imie'] == st.session_state.user_name]
        
        if my_shifts.empty:
            st.warning("Brak zmian w grafiku.")
        else:
            shift_options = my_shifts.apply(lambda x: f"{x['Data']} | {x['Stanowisko']} ({x['Godziny']})", axis=1).tolist()
            
            with st.container():
                st.markdown("<div class='timesheet-card'>", unsafe_allow_html=True)
                selected_shift_str = st.selectbox("Wybierz zmianę:", shift_options)
                
                default_start = time(16,0)
                default_end = time(0,0)
                try:
                    h_part = selected_shift_str.split("(")[1].replace(")", "")
                    s, e = h_part.split("-")
                    default_start = datetime.strptime(s, "%H:%M").time()
                    default_end = datetime.strptime(e, "%H:%M").time()
                except: pass
                
                c1, c2, c3 = st.columns(3)
                shift_date = selected_shift_str.split(" | ")[0]
                c1.text_input("Data", value=shift_date, disabled=True)
                log_start = c2.time_input("Start", value=default_start)
                log_end = c3.time_input("Koniec", value=default_end)
                
                if st.button("➕ ZATWIERDŹ"):
                    l_date = datetime.strptime(shift_date, "%Y-%m-%d").date()
                    dt1 = datetime.combine(l_date, log_start)
                    dt2 = datetime.combine(l_date, log_end)
                    if dt2 < dt1: dt2 += timedelta(days=1)
                    hours = (dt2 - dt1).total_seconds() / 3600
                    st.session_state.work_logs.loc[len(st.session_state.work_logs)] = {
                        "Pracownik": st.session_state.user_name, "Data": l_date, "Start": log_start, "Koniec": log_end, "Godziny": round(hours, 2)
                    }
                    st.success(f"Dodano: {hours:.2f}h")
                st.markdown("</div>", unsafe_allow_html=True)
            
            st.divider()
            my_logs = st.session_state.work_logs[st.session_state.work_logs['Pracownik'] == st.session_state.user_name]
            if not my_logs.empty:
                st.metric("Suma Godzin", f"{my_logs['Godziny'].sum():.2f} h")
                st.dataframe(my_logs, use_container_width=True)
