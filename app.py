import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re
import json
import os

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | FINAL PRO", layout="wide")
DATA_FOLDER = "ether_data"

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    
    /* ZAKŁADKI */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: #1a1c24; padding: 10px; border-radius: 10px; margin-top: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #333; border-radius: 5px; color: white; padding: 5px 20px; border: 1px solid #555; }
    .stTabs [aria-selected="true"] { background-color: #3b82f6 !important; font-weight: bold; border: 1px solid #3b82f6; }
    
    /* PANELE */
    .config-box { background-color: #262626; padding: 20px; border-radius: 10px; border: 1px solid #444; margin-top: 15px; }
    .week-selector { background-color: #1a1c24; padding: 15px; border-radius: 10px; border-left: 5px solid #d93025; margin-bottom: 10px; }
    .timesheet-card { background-color: #1a1c24; padding: 20px; border-radius: 10px; border: 1px solid #444; border-left: 5px solid #4caf50; }
    .wallet-card { background-color: #282828; padding: 15px; border-radius: 10px; border: 1px solid #555; text-align: center; margin-bottom: 20px; }
    .wallet-amount { font-size: 24px; font-weight: bold; color: #4caf50; }
    
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

# --- SYSTEM PLIKÓW (PAMIĘĆ TRWAŁA) ---
if not os.path.exists(DATA_FOLDER): os.makedirs(DATA_FOLDER)

def load_json(filename, default):
    path = os.path.join(DATA_FOLDER, filename)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default
    return default

def save_json(filename, data):
    path = os.path.join(DATA_FOLDER, filename)
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

# --- FUNKCJE LOGICZNE ---
def polish_sort_key(text):
    alphabet = {'ą':'a1', 'ć':'c1', 'ę':'e1', 'ł':'l1', 'ń':'n1', 'ó':'o1', 'ś':'s1', 'ź':'z1', 'ż':'z2'}
    return "".join([alphabet.get(c.lower(), c.lower()) for c in text])

def calculate_auto_roles(selected_roles):
    auto = ["Sprzątanie Generalne"]
    if "Bar" in selected_roles: auto.append("Inwentaryzacja")
    if "Bar" in selected_roles and "Obsługa" in selected_roles:
        auto.extend(["Pomoc Bar", "Pomoc Obsługa"])
    return list(set(auto))

def clean_text(text):
    if not isinstance(text, str): text = str(text)
    replacements = {'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z', '–':'-'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def is_availability_locked():
    now = datetime.now()
    # Blokada: Wt(1), Śr(2), Czw(3) LUB Pon(0) po 23:00
    if now.weekday() in [1, 2, 3]: return True
    if now.weekday() == 0 and now.hour >= 23: return True
    return False 

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

def find_worker_for_shift(role_needed, shift_time_type, date_obj, employees_list, avail_grid, assigned_today):
    candidates = []
    date_str = date_obj.strftime('%Y-%m-%d')
    
    for emp in employees_list:
        # Conflict Guard
        if emp['Imie'] in assigned_today[shift_time_type]: continue
        
        role_base = role_needed.replace(" 1", "").replace(" 2", "")
        if role_base in emp['Role'] or role_base in emp['Auto']:
            key = f"{emp['Imie']}_{date_str}"
            avail = avail_grid.get(key, "")
            if is_avail_compatible(avail, shift_time_type):
                candidates.append(emp)

    if not candidates: return None

    final_candidate_name = None
    if role_needed == "Obsługa":
        men = [c for c in candidates if c.get('Plec') == 'M']
        if men: final_candidate_name = random.choice(men)['Imie']
        else:
            women = [c for c in candidates if c.get('Plec') == 'K']
            if women: final_candidate_name = random.choice(women)['Imie']
    else:
        final_candidate_name = random.choice(candidates)['Imie']
        
    return final_candidate_name

# --- HTML RENDER ---
def render_html_schedule(shifts_data, start_date):
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
    df = pd.DataFrame(shifts_data)
    if not df.empty:
        # Upewniamy się, że data jest typem date, a nie stringiem, do porównań
        df['Data_Obj'] = pd.to_datetime(df['Data']).dt.date
    
    for role in visual_roles:
        html += f'<tr><td class="role-header">{role.upper()}</td>'
        for d in days:
            w_day = d.weekday()
            td_class = 'class="highlight-day"' if w_day in [1, 5, 6] else ''
            cell_content = ""
            
            if not df.empty:
                current_shifts = df[(df['Data_Obj'] == d) & (df['Stanowisko'].str.contains(role, regex=False))]
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

def generate_schedule_pdf(shifts_data, title):
    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean_text(title), ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", '', 8)
    
    df = pd.DataFrame(shifts_data)
    if df.empty: return pdf.output(dest='S').encode('latin-1')
    
    days = sorted(df['Data'].unique())
    for day in days:
        d_str = pd.to_datetime(day).strftime('%d.%m (%A)')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, clean_text(f"--- {d_str} ---"), ln=True)
        pdf.set_font("Arial", '', 10)
        day_shifts = df[df['Data'] == day]
        for _, row in day_shifts.sort_values(by=["Stanowisko"]).iterrows():
            name = row['Pracownik_Imie'] if row['Pracownik_Imie'] else "---"
            line = f"{row['Stanowisko']} | {row['Godziny']} | {name}"
            pdf.cell(0, 8, clean_text(line), ln=True, border=1)
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')

# --- INICJALIZACJA STANU (ŁADOWANIE Z PLIKÓW) ---
if 'db_users' not in st.session_state:
    st.session_state.db_users = load_json('db_users.json', {"admin": {"pass": "admin123", "role": "manager", "name": "Kierownik"}})
if 'db_employees' not in st.session_state:
    # Domyślna lista tylko jeśli plik nie istnieje
    default_employees = [] # Pusta, bo dodasz ręcznie lub przez reset
    st.session_state.db_employees = load_json('db_employees.json', default_employees)
if 'db_shifts' not in st.session_state:
    st.session_state.db_shifts = load_json('db_shifts.json', [])
if 'db_avail' not in st.session_state:
    st.session_state.db_avail = load_json('db_avail.json', {})
if 'db_logs' not in st.session_state:
    st.session_state.db_logs = load_json('db_logs.json', [])

# Jeśli baza pusta, załaduj demo (tylko raz)
if not st.session_state.db_employees:
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
    raw_data.sort(key=lambda x: polish_sort_key(x['Imie'].split()[-1]))
    rows = []
    for i, p in enumerate(raw_data):
        rows.append({"ID": i+1, "Imie": p["Imie"], "Role": p["Role"], "Plec": p["Plec"], "Auto": calculate_auto_roles(p["Role"])})
    st.session_state.db_employees = rows
    # Dodajemy też konta użytkowników dla demo
    if "julia" not in st.session_state.db_users:
        st.session_state.db_users["julia"] = {"pass": "julia1", "role": "worker", "name": "Julia Bąk"}
        st.session_state.db_users["kacper"] = {"pass": "kacper1", "role": "worker", "name": "Kacper Borzechowski"}
    # Zapisz od razu
    save_json('db_employees.json', st.session_state.db_employees)
    save_json('db_users.json', st.session_state.db_users)

def save_all():
    save_json('db_users.json', st.session_state.db_users)
    save_json('db_employees.json', st.session_state.db_employees)
    save_json('db_shifts.json', st.session_state.db_shifts)
    save_json('db_avail.json', st.session_state.db_avail)
    save_json('db_logs.json', st.session_state.db_logs)

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
            users = st.session_state.db_users
            if u in users and users[u]["pass"] == p:
                st.session_state.logged_in = True
                st.session_state.user_role = users[u]["role"]
                st.session_state.user_name = users[u]["name"]
                st.rerun()
            else: st.error("Błąd.")
    st.stop()

# ==========================================
# PANEL PRACOWNIKA
# ==========================================
if st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        st.caption("Panel Pracownika")
        menu = st.radio("Menu:", ["📅 Mój Grafik", "✍️ Moja Dyspozycyjność", "⏱️ Karta Czasu"])
        st.divider()
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # 1. MÓJ GRAFIK
    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        df = pd.DataFrame(st.session_state.db_shifts)
        if not df.empty:
            my = df[df['Pracownik_Imie'] == st.session_state.user_name]
            if not my.empty:
                st.dataframe(my[["Data", "Stanowisko", "Godziny"]], use_container_width=True)
            else: st.info("Brak zmian.")
        else: st.info("Brak grafiku.")

    # 2. DYSPOZYCJE
    elif menu == "✍️ Moja Dyspozycyjność":
        st.title("Moja Dyspozycyjność")
        
        is_locked = is_availability_locked()
        if is_locked: st.error("🔒 Edycja zablokowana.")
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
                val = st.session_state.db_avail.get(key, "")
                new_val = cols[i].text_input("h", val, key=f"w_{key}", disabled=is_locked, label_visibility="collapsed")
                if not is_locked: st.session_state.db_avail[key] = new_val
            
            if st.form_submit_button("Zapisz", disabled=is_locked):
                save_all()
                st.toast("Zapisano!", icon="✅")

    # 3. KARTA CZASU
    elif menu == "⏱️ Karta Czasu":
        st.title("Ewidencja")
        
        # Pobieramy zmiany z bazy
        df_shifts = pd.DataFrame(st.session_state.db_shifts)
        my_shifts = pd.DataFrame()
        if not df_shifts.empty:
            my_shifts = df_shifts[df_shifts['Pracownik_Imie'] == st.session_state.user_name]
        
        if my_shifts.empty:
            st.warning("Brak zmian w grafiku.")
        else:
            # Opcje do wyboru
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
                    st.session_state.db_logs.append({
                        "Pracownik": st.session_state.user_name, "Data": str(l_date), 
                        "Start": str(log_start), "Koniec": str(log_end), "Godziny": round(hours, 2)
                    })
                    save_all()
                    st.success(f"Dodano: {hours:.2f}h")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            
            st.divider()
            df_logs = pd.DataFrame(st.session_state.db_logs)
            if not df_logs.empty:
                my_logs_view = df_logs[df_logs['Pracownik'] == st.session_state.user_name]
                if not my_logs_view.empty:
                    st.metric("Suma Godzin", f"{my_logs_view['Godziny'].sum():.2f} h")
                    st.dataframe(my_logs_view, use_container_width=True)

# ==========================================
# PANEL MENEDŻERA
# ==========================================
elif st.session_state.user_role == "manager":
    with st.sidebar:
        st.title("🔧 PANEL KIEROWNIKA")
        menu = st.radio("Nawigacja:", ["Auto-Planer (LOGISTIC)", "Dyspozycje (Podgląd)", "Kadry (Edycja)", "Grafik (WIZUALNY)"])
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
            week_start = st.date_input("Start cyklu (Tylko przyszłe Piątki):", next_friday, min_value=today)
            if week_start.weekday() != 4:
                st.error("⛔ BŁĄD: Grafiki w kinie muszą zaczynać się w PIĄTEK!")
                st.stop()
            week_end = week_start + timedelta(days=6)
            st.info(f"📅 Planujesz grafik na okres: **{week_start.strftime('%d.%m')} (Pt) - {week_end.strftime('%d.%m')} (Cz)**")
        
        # Ładowanie demo dyspozycji dla wybranego tygodnia (jeśli puste)
        days_check = [week_start + timedelta(days=i) for i in range(7)]
        # Tutaj opcjonalnie można wywołać preload_demo_data(week_start) jeśli baza jest pusta
        
        week_days = [week_start + timedelta(days=i) for i in range(7)]
        day_labels = ["PIĄTEK", "SOBOTA", "NIEDZIELA", "PONIEDZIAŁEK", "WTOREK", "ŚRODA", "CZWARTEK"]
        week_config = []
        
        tabs = st.tabs([f"{day_labels[i]} {d.strftime('%d.%m')}" for i, d in enumerate(week_days)])
        
        for i, tab in enumerate(tabs):
            with tab:
                with st.container(border=True):
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
                
                week_config.append({
                    "date": week_days[i], "times": (s1, sl, el), "counts": (k, b1, b2, c, om, oe)
                })

        st.write("---")
        if st.button("⚡ GENERUJ CAŁY TYDZIEŃ", type="primary"):
            # 1. Czyszczenie starych zmian z tego zakresu
            current_shifts = st.session_state.db_shifts
            # Filtrujemy: zostawiamy tylko te spoza zakresu
            start_s = str(week_days[0])
            end_s = str(week_days[-1])
            st.session_state.db_shifts = [s for s in current_shifts if not (start_s <= s['Data'] <= end_s)]
            
            cnt = 0
            for day_cfg in week_config:
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
                emp_df = pd.DataFrame(st.session_state.db_employees)
                
                for role, t_type, s, e in daily_tasks:
                    worker_name = find_worker_for_shift(role, t_type, current_date, emp_df, st.session_state.db_avail, assigned_today)
                    final = worker_name if worker_name is not None else ""
                    st.session_state.db_shifts.append({
                        "Data": str(current_date), "Stanowisko": role, "Godziny": f"{s}-{e}", "Pracownik_Imie": final, "Typ": "Auto"
                    })
                    if worker_name is not None: assigned_today[t_type].append(worker_name)
                    cnt += 1
            
            save_all()
            st.success(f"Wygenerowano {cnt} zmian! Przejdź do zakładki 'Grafik (WIZUALNY)'.")

    # --- 2. DYSPOZYCJE ---
    elif menu == "Dyspozycje (Podgląd)":
        st.title("📥 Dyspozycje")
        today = datetime.now().date()
        d_start = st.date_input("Tydzień:", today)
        days = [d_start + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
        
        cols = st.columns([2] + [1]*7)
        cols[0].write("**Pracownik**")
        for i, d in enumerate(days): cols[i+1].write(f"**{day_names[i]}**")
        st.divider()
        
        for emp in st.session_state.db_employees:
            r_cols = st.columns([2] + [1]*7)
            r_cols[0].write(f"{emp['Imie']}")
            for i, d in enumerate(days):
                key = f"{emp['Imie']}_{d.strftime('%Y-%m-%d')}"
                val = st.session_state.db_avail.get(key, "-")
                r_cols[i+1].write(val)

    # --- 3. KADRY (TWORZENIE KONT) ---
    elif menu == "Kadry (Edycja)":
        st.title("📇 Kadry i Konta")
        
        with st.expander("➕ Dodaj Pracownika i Konto"):
            with st.form("add_user"):
                u_name = st.text_input("Imię i Nazwisko")
                u_login = st.text_input("Login")
                u_pass = st.text_input("Hasło")
                u_roles = st.multiselect("Role", ["Obsługa", "Bar", "Kasa", "Cafe"])
                u_plec = st.selectbox("Płeć", ["K", "M"])
                
                if st.form_submit_button("Utwórz"):
                    st.session_state.db_users[u_login] = {"pass": u_pass, "role": "worker", "name": u_name}
                    auto = calculate_auto_roles(u_roles)
                    st.session_state.db_employees.append({
                        "ID": len(st.session_state.db_employees)+1, "Imie": u_name, 
                        "Role": u_roles, "Plec": u_plec, "Auto": auto
                    })
                    save_all()
                    st.success("Konto utworzone!")
                    st.rerun()
        
        st.write("---")
        st.subheader("Lista Kont")
        users_data = []
        for login, data in st.session_state.db_users.items():
            users_data.append({"Login": login, "Imię": data["name"], "Rola": data["role"]})
        st.dataframe(pd.DataFrame(users_data))

    # --- 4. GRAFIK ---
    elif menu == "Grafik (WIZUALNY)":
        st.title("📋 Grafik")
        today = datetime.now().date()
        d_start = st.date_input("Pokaż tydzień od (Piątek):", today)
        
        df = pd.DataFrame(st.session_state.db_shifts)
        
        if not df.empty:
            df['DataObj'] = pd.to_datetime(df['Data']).dt.date
            d_end = d_start + timedelta(days=6)
            mask = (df['DataObj'] >= d_start) & (df['DataObj'] <= d_end)
            df_view = df.loc[mask]
            
            if not df_view.empty:
                # Przekazujemy "surowe" słowniki do renderera, bo HTML render lubi dicty/df
                # Wcześniejsza funkcja render_html_schedule brała DF, więc jest OK
                st.markdown(render_html_schedule(df_view, d_start), unsafe_allow_html=True)
                st.write("---")
                if st.button("🖨️ PDF"):
                    pdf = generate_schedule_pdf(df_view, f"GRAFIK {d_start}")
                    st.download_button("Pobierz", pdf, "grafik.pdf", "application/pdf")
            else: st.info("Brak zmian w tym okresie.")
        else: st.info("Baza grafiku jest pusta.")
