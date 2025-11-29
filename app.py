import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | POLISH PERFECT", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: #1a1c24; padding: 10px; border-radius: 10px; margin-top: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #333; border-radius: 5px; color: white; padding: 5px 20px; border: 1px solid #555; }
    .stTabs [aria-selected="true"] { background-color: #3b82f6 !important; font-weight: bold; border: 1px solid #3b82f6; }
    
    /* PANELE */
    .config-box { background-color: #262626; padding: 20px; border-radius: 10px; border: 1px solid #444; margin-top: 15px; }
    .week-info-box { background-color: #1a1c24; padding: 15px; border-radius: 10px; border-left: 5px solid #d93025; margin-bottom: 20px; font-size: 18px; font-weight: bold; }
    
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
    .empty-shift-box { background-color: #ffcccc; border: 2px solid #ff0000; border-radius: 3px; margin-bottom: 3px; padding: 2px; min-height: 20px; }
    .empty-time { font-weight: bold; display: block; color: #cc0000; font-size: 10px; }
    
    .day-header { font-size: 12px; text-transform: uppercase; font-weight: bold; }
    
    /* KADRY */
    .worker-edit-card { background-color: #1f2937; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #374151; }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA UŻYTKOWNIKÓW ---
USERS = {
    "admin":  {"pass": "AlastorRules", "role": "manager", "name": "Szef"},
    "kierownik": {"pass": "film123", "role": "manager", "name": "Kierownik"},
    "julia":  {"pass": "julia1", "role": "worker", "name": "Julia Bąk"},
    "kacper": {"pass": "kacper1", "role": "worker", "name": "Kacper Borzechowski"},
}

# --- USTAWIENIA GLOBALNE ---
if 'sys_config' not in st.session_state:
    st.session_state.sys_config = {
        "lock_day_idx": 0,     # 0=Poniedziałek
        "lock_hour": 23        # Godzina 23:00
    }

# --- FUNKCJE LOGICZNE ---
def polish_sort_key(text):
    """Sortowanie uwzględniające polskie znaki"""
    alphabet = {
        'ą': 'a1', 'ć': 'c1', 'ę': 'e1', 'ł': 'l1', 'ń': 'n1', 'ó': 'o1', 'ś': 's1', 'ź': 'z1', 'ż': 'z2',
        'Ą': 'A1', 'Ć': 'C1', 'Ę': 'E1', 'Ł': 'L1', 'Ń': 'N1', 'Ó': 'O1', 'Ś': 'S1', 'Ź': 'Z1', 'Ż': 'Z2'
    }
    return "".join([alphabet.get(c, c) for c in text])

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
    """Sprawdza blokadę wg ustawień"""
    cfg = st.session_state.sys_config
    now = datetime.now()
    
    # Jeśli dzień tygodnia > dzień blokady (np. Wtorek > Poniedziałek) -> ZABLOKOWANE
    if now.weekday() > cfg['lock_day_idx']: return True
    # Jeśli dzień ten sam, ale godzina minęła -> ZABLOKOWANE
    if now.weekday() == cfg['lock_day_idx'] and now.hour >= cfg['lock_hour']: return True
    
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
    html = f"""<div style="background-color: #333; color: white; padding: 10px; text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 0px; border-radius: 5px 5px 0 0;">GRAFIK: {date_header_str}</div><table class="schedule-table"><thead><tr><th style="width: 8%;">STANOWISKO</th>"""
    for d in days:
        w_day = d.weekday()
        day_map = {4:"PIĄTEK", 5:"SOBOTA", 6:"NIEDZIELA", 0:"PONIEDZIAŁEK", 1:"WTOREK", 2:"ŚRODA", 3:"CZWARTEK"}
        style = 'style="background-color: #2c5282;"' if w_day in [1, 5, 6] else ''
        html += f'<th {style}><div class="day-header">{day_map[w_day]}<br>{d.strftime("%d.%m")}</div></th>'
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
    # SORTOWANIE POLSKIE
    raw_data.sort(key=lambda x: polish_sort_key(x['Imie'].split()[-1]))
    
    rows = []
    for i, p in enumerate(raw_data):
        rows.append({"ID": i+1, "Imie": p["Imie"], "Role": p["Role"], "Plec": p["Plec"], "Auto": calculate_auto_roles(p["Role"])})
    st.session_state.employees = pd.DataFrame(rows)

if 'employees' not in st.session_state or 'Plec' not in st.session_state.employees.columns: reset_database()
if 'shifts' not in st.session_state: st.session_state.shifts = pd.DataFrame(columns=["Data", "Stanowisko", "Godziny", "Pracownik_Imie", "Typ"])
if 'avail_grid' not in st.session_state: st.session_state.avail_grid = {}
if 'active_week_start' not in st.session_state: st.session_state.active_week_start = datetime.now().date()

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
        st.title("🔧 KIEROWNIK")
        menu = st.radio("Nawigacja:", ["Auto-Planer (LOGISTIC)", "Dyspozycje (Podgląd)", "Kadry (Edycja)", "Grafik (WIZUALNY)", "Ustawienia"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # 1. AUTO-PLANER
    if menu == "Auto-Planer (LOGISTIC)":
        st.title("🚀 Generator")
        
        today = datetime.now().date()
        # Sugerowany start (piątek)
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_friday = today + timedelta(days=days_ahead)
        if today.weekday() == 4: next_friday = today

        with st.container(border=True):
            week_start = st.date_input("Planowany Tydzień (Start Piątek):", next_friday, min_value=today)
            if week_start.weekday() != 4:
                st.error("⛔ Grafiki zaczynają się w PIĄTEK!")
                st.stop()
            # ZAPIS DO SESJI, ŻEBY DYSPOZYCJE WIDZIAŁY TĘ DATĘ
            st.session_state.active_week_start = week_start
            
            week_end = week_start + timedelta(days=6)
            st.info(f"Planujesz: **{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}**")

        week_days = [week_start + timedelta(days=i) for i in range(7)]
        week_config = []
        day_labels = ["PIĄTEK", "SOBOTA", "NIEDZIELA", "PONIEDZIAŁEK", "WTOREK", "ŚRODA", "CZWARTEK"]
        
        tabs = st.tabs([f"{d.strftime('%d.%m')}" for _, d in enumerate(week_days)])
        
        for i, tab in enumerate(tabs):
            with tab:
                st.markdown(f"#### {day_labels[i]}")
                c1, c2 = st.columns(2)
                with c1:
                    s1 = st.time_input(f"Start 1.", time(9,0), key=f"s1_{i}")
                    sl = st.time_input(f"Start Ost.", time(21,0), key=f"sl_{i}")
                    el = st.time_input(f"Koniec Ost.", time(0,0), key=f"el_{i}")
                with c2:
                    col_a, col_b, col_c = st.columns(3)
                    k = col_a.selectbox("KASA", [0,1,2], index=1, key=f"k_{i}")
                    b = col_b.selectbox("BAR", [1,2,3,4], index=1, key=f"b_{i}")
                    o = col_c.selectbox("OBSŁUGA", [1,2,3,4], index=1, key=f"o_{i}")
                    # Uproszczone suwaki dla demo, w produkcji można dać więcej
                
                week_config.append({"date": week_days[i], "times": (s1,sl,el), "counts": (k,b,o)})
        
        if st.button("⚡ GENERUJ", type="primary"):
            mask = (st.session_state.shifts['Data'] >= week_days[0]) & (st.session_state.shifts['Data'] <= week_days[-1])
            st.session_state.shifts = st.session_state.shifts[~mask]
            
            cnt = 0
            for cfg in week_config:
                d = cfg['date']
                s1, sl, el = cfg['times']
                k, b, o = cfg['counts']
                
                # Obliczenia
                start = (datetime.combine(d, s1) - timedelta(minutes=45)).strftime("%H:%M")
                bar_end = (datetime.combine(d, sl) + timedelta(minutes=15)).strftime("%H:%M")
                obs_end = (datetime.combine(d, el) + timedelta(minutes=15)).strftime("%H:%M")
                split = "16:00"
                
                tasks = []
                for _ in range(k): tasks.append(("Kasa", "morning", start, split)); tasks.append(("Kasa", "evening", split, bar_end))
                # Uproszczony przydział reszty
                for _ in range(b): tasks.append(("Bar 1", "morning", start, split)); tasks.append(("Bar 1", "evening", split, bar_end))
                for _ in range(o): tasks.append(("Obsługa", "morning", start, split)); tasks.append(("Obsługa", "evening", split, obs_end))
                
                assigned = {'morning': [], 'evening': []}
                for role, t_type, s, e in tasks:
                    worker = find_worker_for_shift(role, t_type, d, st.session_state.employees, st.session_state.avail_grid, assigned)
                    final = worker if worker else "WAKAT"
                    st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                        "Data": d, "Stanowisko": role, "Godziny": f"{s}-{e}", "Pracownik_Imie": final, "Typ": "Auto"
                    }
                    if worker: assigned[t_type].append(worker)
                    cnt += 1
            st.success(f"Wygenerowano {cnt} zmian! Zobacz Grafik.")

    # --- 2. DYSPOZYCJE ---
    elif menu == "Dyspozycje (Podgląd)":
        start_d = st.session_state.active_week_start
        end_d = start_d + timedelta(days=6)
        st.title("📥 Dyspozycje")
        st.markdown(f"<div class='week-info-box'>Dyspozycje na tydzień: {start_d.strftime('%d.%m')} - {end_d.strftime('%d.%m')}</div>", unsafe_allow_html=True)
        
        days = [start_d + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
        
        # Tabela podglądu
        cols = st.columns([3] + [1]*7)
        cols[0].write("**Pracownik**")
        for i, d in enumerate(days): cols[i+1].write(f"**{day_names[i]}**")
        st.divider()
        
        for idx, emp in st.session_state.employees.iterrows():
            r_cols = st.columns([3] + [1]*7)
            r_cols[0].write(f"{emp['Imie']}")
            for i, d in enumerate(days):
                key = f"{emp['Imie']}_{d.strftime('%Y-%m-%d')}"
                val = st.session_state.avail_grid.get(key, "-")
                r_cols[i+1].write(val)

    # --- 3. KADRY ---
    elif menu == "Kadry (Edycja)":
        st.title("📇 Kadry")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("Edytor")
            emp_names = st.session_state.employees['Imie'].tolist()
            selected = st.selectbox("Edytuj osobę:", ["-- NOWY --"] + emp_names)
            
            with st.form("edit_hr"):
                if selected == "-- NOWY --":
                    f_name = st.text_input("Imię i Nazwisko")
                    f_role = st.multiselect("Role", ["Obsługa", "Bar", "Kasa", "Cafe"])
                    f_plec = st.selectbox("Płeć", ["K", "M"])
                    if st.form_submit_button("Dodaj"):
                        auto = calculate_auto_roles(f_role)
                        st.session_state.employees.loc[len(st.session_state.employees)] = {
                            "ID": len(st.session_state.employees)+1, "Imie": f_name, "Role": f_role, "Plec": f_plec, "Auto": auto
                        }
                        st.rerun()
                else:
                    # Pobieranie danych istniejącego
                    curr = st.session_state.employees[st.session_state.employees['Imie'] == selected].iloc[0]
                    f_name = st.text_input("Imię", value=curr['Imie'])
                    f_role = st.multiselect("Role", ["Obsługa", "Bar", "Kasa", "Cafe"], default=curr['Role'])
                    f_plec = st.selectbox("Płeć", ["K", "M"], index=0 if curr['Plec']=="K" else 1)
                    
                    c_save, c_del = st.columns(2)
                    if c_save.form_submit_button("Zapisz"):
                        idx = st.session_state.employees[st.session_state.employees['Imie'] == selected].index[0]
                        st.session_state.employees.at[idx, 'Imie'] = f_name
                        st.session_state.employees.at[idx, 'Role'] = f_role
                        st.session_state.employees.at[idx, 'Plec'] = f_plec
                        st.rerun()
                    if c_del.form_submit_button("Usuń"):
                        idx = st.session_state.employees[st.session_state.employees['Imie'] == selected].index[0]
                        st.session_state.employees = st.session_state.employees.drop(idx).reset_index(drop=True)
                        st.rerun()
        
        with col2:
            st.dataframe(st.session_state.employees[["Imie", "Role", "Plec"]], use_container_width=True, height=600)

    # --- 4. GRAFIK ---
    elif menu == "Grafik (WIZUALNY)":
        st.title("📋 Grafik")
        d_start = st.session_state.active_week_start
        d_end = d_start + timedelta(days=6)
        
        mask = (st.session_state.shifts['Data'] >= d_start) & (st.session_state.shifts['Data'] <= d_end)
        df_view = st.session_state.shifts.loc[mask]
        
        if not df_view.empty:
            st.markdown(render_html_schedule(df_view, d_start), unsafe_allow_html=True)
            st.write("---")
            if st.button("🖨️ PDF"):
                pdf = generate_schedule_pdf(df_view, f"GRAFIK {d_start} - {d_end}")
                st.download_button("Pobierz", pdf, "grafik.pdf", "application/pdf")
        else:
            st.info("Pusto. Wygeneruj grafik.")

    # --- 5. USTAWIENIA ---
    elif menu == "Ustawienia":
        st.title("⚙️ Ustawienia")
        st.markdown("<div class='config-box'>", unsafe_allow_html=True)
        day_map = {0:"Poniedziałek", 1:"Wtorek", 2:"Środa", 3:"Czwartek", 4:"Piątek", 5:"Sobota", 6:"Niedziela"}
        
        curr_day = st.session_state.sys_config['lock_day_idx']
        new_day = st.selectbox("Dzień blokady dyspozycji:", list(day_map.keys()), index=curr_day, format_func=lambda x: day_map[x])
        
        curr_hour = st.session_state.sys_config['lock_hour']
        new_hour = st.slider("Godzina blokady:", 0, 23, curr_hour)
        
        if st.button("Zapisz"):
            st.session_state.sys_config['lock_day_idx'] = new_day
            st.session_state.sys_config['lock_hour'] = new_hour
            st.success("Zapisano!")
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# PRACOWNIK
# ==========================================
elif st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        menu = st.radio("Menu:", ["📅 Mój Grafik", "✍️ Moja Dyspozycyjność"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()
        
    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        my = st.session_state.shifts[st.session_state.shifts['Pracownik_Imie'] == st.session_state.user_name]
        if not my.empty: st.dataframe(my[["Data", "Stanowisko", "Godziny"]], use_container_width=True)
        else: st.info("Brak zmian.")

    elif menu == "✍️ Moja Dyspozycyjność":
        st.title("Moja Dyspozycyjność")
        
        # Pobieramy datę ustaloną przez managera
        start_d = st.session_state.active_week_start
        end_d = start_d + timedelta(days=6)
        
        st.info(f"Wpisujesz dyspozycje na tydzień: **{start_d.strftime('%d.%m')} - {end_d.strftime('%d.%m')}**")
        
        is_locked = is_availability_locked()
        if is_locked: st.error("🔒 Edycja zablokowana.")
        
        days = [start_d + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
        
        # Formularz
        with st.form("avail"):
            cols = st.columns(7)
            for i, d in enumerate(days):
                cols[i].write(f"**{day_names[i]}**")
                key = f"{st.session_state.user_name}_{d.strftime('%Y-%m-%d')}"
                val = st.session_state.avail_grid.get(key, "")
                new = cols[i].text_input("Godziny", val, key=key, disabled=is_locked, label_visibility="collapsed")
                if not is_locked: st.session_state.avail_grid[key] = new
            
            st.form_submit_button("Zapisz", disabled=is_locked)
