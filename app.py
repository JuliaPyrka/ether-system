import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re
import json
import os

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | COMMERCIAL", layout="wide")
DATA_FOLDER = "ether_data"

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
    .week-selector { background-color: #1a1c24; padding: 15px; border-radius: 10px; border-left: 5px solid #d93025; margin-bottom: 10px; }
    .timesheet-card { background-color: #1a1c24; padding: 20px; border-radius: 10px; border: 1px solid #444; border-left: 5px solid #4caf50; }
    .wallet-card { background-color: #282828; padding: 15px; border-radius: 10px; border: 1px solid #555; text-align: center; margin-bottom: 20px; }
    .wallet-amount { font-size: 24px; font-weight: bold; color: #4caf50; }
    /* TABELA */
    .schedule-table { width: 100%; border-collapse: collapse; color: #000; background-color: #fff; font-family: Arial, sans-serif; font-size: 11px; }
    .schedule-table th { background-color: #444; color: #fff; padding: 8px; border: 1px solid #777; text-align: center; }
    .schedule-table td { border: 1px solid #ccc; padding: 4px; vertical-align: top; text-align: center; height: 60px; width: 12.5%; }
    .highlight-day { background-color: #e3f2fd !important; } 
    .role-header { background-color: #eee; font-weight: bold; text-align: center; vertical-align: middle !important; border: 1px solid #999; font-size: 12px; }
    .shift-box { background-color: #fff; border: 1px solid #aaa; border-radius: 3px; margin-bottom: 3px; padding: 2px; box-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
    .shift-time { font-weight: bold; display: block; color: #000; font-size: 10px; }
    .shift-name { display: block; color: #333; text-transform: uppercase; font-size: 9px; line-height: 1.1; }
    .empty-shift-box { background-color: #ffcccc; border: 2px solid #ff0000; border-radius: 3px; margin-bottom: 3px; padding: 2px; min-height: 20px; }
    .empty-time { font-weight: bold; display: block; color: #cc0000; font-size: 10px; }
    .day-header { font-size: 12px; text-transform: uppercase; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- SYSTEM PLIKÓW (PERSISTENCE) ---
if not os.path.exists(DATA_FOLDER): os.makedirs(DATA_FOLDER)

def load_json(filename, default):
    path = os.path.join(DATA_FOLDER, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_json(filename, data):
    path = os.path.join(DATA_FOLDER, filename)
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

# --- FUNKCJE POMOCNICZE ---
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
    """Blokada edycji w Poniedziałek o 23:00"""
    now = datetime.now()
    if now.weekday() == 0 and now.hour >= 23: return True # Poniedziałek po 23
    if now.weekday() in [1, 2, 3]: return True # Wt, Śr, Czw
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

# --- ALGORYTM SPRAWIEDLIWOŚCI (FAIR PLAY) ---
def find_worker_for_shift(role_needed, shift_time_type, date_obj, employees_list, avail_grid, assigned_today, shift_counts):
    candidates = []
    date_str = date_obj.strftime('%Y-%m-%d')
    
    for emp in employees_list:
        # 1. Konflikt
        if emp['Imie'] in assigned_today[shift_time_type]: continue
        if emp['Imie'] in assigned_today['all_day']: continue # Max 1 zmiana dziennie (chyba że braknie ludzi)
        
        # 2. Rola
        role_base = role_needed.replace(" 1", "").replace(" 2", "")
        if role_base in emp['Role'] or role_base in emp['Auto']:
            # 3. Dyspozycja
            key = f"{emp['Imie']}_{date_str}"
            avail = avail_grid.get(key, "")
            if is_avail_compatible(avail, shift_time_type):
                candidates.append(emp)

    if not candidates: return None

    # 4. SPRAWIEDLIWOŚĆ (Kto ma najmniej zmian?)
    # Sortujemy: najpierw po liczbie zmian (rosnąco), potem losowo (żeby nie brać zawsze tego samego z listy)
    candidates.sort(key=lambda x: (shift_counts.get(x['Imie'], 0), random.random()))
    
    # 5. PREFERENCJE PŁCI (Tylko dla Obsługi)
    final_candidate = None
    if role_needed == "Obsługa":
        men = [c for c in candidates if c.get('Plec') == 'M']
        if men: final_candidate = men[0] # Bierzemy pierwszego (najmniej zmian)
        else:
            women = [c for c in candidates if c.get('Plec') == 'K']
            if women: final_candidate = women[0]
    else:
        final_candidate = candidates[0]
        
    return final_candidate['Imie']

# --- RENDERERY ---
def render_html_schedule(shifts_data, start_date):
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
    
    # Konwersja listy słowników na DataFrame do łatwego filtrowania
    df = pd.DataFrame(shifts_data)
    if df.empty: return "Brak danych"
    df['Data'] = pd.to_datetime(df['Data']).dt.date

    for role in visual_roles:
        html += f'<tr><td class="role-header">{role.upper()}</td>'
        for d in days:
            w_day = d.weekday()
            td_class = 'class="highlight-day"' if w_day in [1, 5, 6] else ''
            
            # Filtrowanie
            current_shifts = df[(df['Data'] == d.date()) & (df['Stanowisko'].str.contains(role, regex=False))]
            
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
        d_str = pd.to_datetime(day).strftime('%d.%m')
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

# --- INICJALIZACJA BAZY DANYCH (LOAD/SAVE) ---
if 'db_users' not in st.session_state:
    st.session_state.db_users = load_json('db_users.json', {"admin": {"pass": "admin123", "role": "manager", "name": "Kierownik"}})
if 'db_employees' not in st.session_state:
    st.session_state.db_employees = load_json('db_employees.json', [])
if 'db_shifts' not in st.session_state:
    st.session_state.db_shifts = load_json('db_shifts.json', []) # Lista słowników
if 'db_avail' not in st.session_state:
    st.session_state.db_avail = load_json('db_avail.json', {})
if 'db_logs' not in st.session_state:
    st.session_state.db_logs = load_json('db_logs.json', [])

# Funkcja zapisująca stan
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
            else: st.error("Błędne dane.")
    st.stop()

# ==========================================
# PANEL PRACOWNIKA
# ==========================================
if st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        menu = st.radio("Menu:", ["📅 Mój Grafik", "✍️ Moja Dyspozycyjność", "⏱️ Karta Czasu"])
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
                new = cols[i].text_input("h", val, key=key, disabled=is_locked, label_visibility="collapsed")
                if not is_locked: st.session_state.db_avail[key] = new
            
            if st.form_submit_button("Zapisz", disabled=is_locked):
                save_all() # ZAPIS DO PLIKU
                st.toast("Zapisano!", icon="✅")

    # 3. KARTA CZASU
    elif menu == "⏱️ Karta Czasu":
        st.title("Ewidencja")
        
        df_logs = pd.DataFrame(st.session_state.db_logs)
        if not df_logs.empty:
            my_logs = df_logs[df_logs['Pracownik'] == st.session_state.user_name]
            total_h = my_logs['Godziny'].sum()
            st.metric("Suma Godzin", f"{total_h:.2f} h")
            st.dataframe(my_logs[["Data", "Start", "Koniec", "Godziny"]], use_container_width=True)
        
        with st.container():
            st.markdown("<div class='timesheet-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            l_date = c1.date_input("Data", datetime.now())
            l_start = c2.time_input("Start", time(16,0))
            l_end = c3.time_input("Koniec", time(0,0))
            if c4.button("Dodaj Czas"):
                dt1 = datetime.combine(l_date, l_start)
                dt2 = datetime.combine(l_date, l_end)
                if dt2 < dt1: dt2 += timedelta(days=1)
                h = (dt2 - dt1).total_seconds() / 3600
                st.session_state.db_logs.append({
                    "Pracownik": st.session_state.user_name, "Data": str(l_date), 
                    "Start": str(l_start), "Koniec": str(l_end), "Godziny": round(h, 2)
                })
                save_all()
                st.success("Dodano!")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# PANEL KIEROWNIKA
# ==========================================
elif st.session_state.user_role == "manager":
    with st.sidebar:
        st.title("🔧 KIEROWNIK")
        menu = st.radio("Nawigacja:", ["Auto-Planer", "Dyspozycje", "Kadry (Konta)", "Grafik"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # 1. AUTO-PLANER
    if menu == "Auto-Planer":
        st.title("🚀 Generator")
        today = datetime.now().date()
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_friday = today + timedelta(days=days_ahead)
        if today.weekday() == 4: next_friday = today

        with st.container(border=True):
            week_start = st.date_input("Start (Piątek):", next_friday, min_value=today)
            if week_start.weekday() != 4: st.error("Wybierz Piątek!"); st.stop()
        
        week_days = [week_start + timedelta(days=i) for i in range(7)]
        day_labels = ["PIĄTEK", "SOBOTA", "NIEDZIELA", "PONIEDZIAŁEK", "WTOREK", "ŚRODA", "CZWARTEK"]
        week_config = []
        
        tabs = st.tabs([f"{d.strftime('%d.%m')}" for i, d in enumerate(week_days)])
        
        for i, tab in enumerate(tabs):
            with tab:
                with st.container(border=True):
                    c1, c2, c3 = st.columns(3)
                    s1 = c1.time_input(f"1. Film", time(9,0), key=f"s1_{i}")
                    sl = c2.time_input(f"Start Ost.", time(21,0), key=f"sl_{i}")
                    el = c3.time_input(f"Koniec Ost.", time(0,0), key=f"el_{i}")
                    st.write("---")
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    k = c1.selectbox("KASA", [0,1,2], index=1, key=f"k_{i}")
                    b1 = c2.selectbox("BAR 1", [0,1,2,3], index=1, key=f"b1_{i}")
                    b2 = c3.selectbox("BAR 2", [0,1,2], index=1, key=f"b2_{i}")
                    c = c4.selectbox("CAFE", [0,1,2], index=1, key=f"c_{i}")
                    om = c5.selectbox("OBS RANO", [1,2,3], index=1, key=f"om_{i}")
                    oe = c6.selectbox("OBS NOC", [1,2,3,4], index=2, key=f"oe_{i}")
                week_config.append({"date": week_days[i], "times": (s1,sl,el), "counts": (k,b,o)})

        if st.button("⚡ GENERUJ", type="primary"):
            # 1. Wyczyść stary grafik na ten tydzień
            start_str = week_days[0].strftime('%Y-%m-%d')
            end_str = week_days[-1].strftime('%Y-%m-%d')
            # Filtrujemy listę, zachowując tylko to co NIE jest w tym tygodniu
            st.session_state.db_shifts = [s for s in st.session_state.db_shifts if not (start_str <= str(s['Data']) <= end_str)]
            
            # 2. Licznik zmian (dla sprawiedliwości)
            shift_counts = {emp['Imie']: 0 for emp in st.session_state.db_employees}
            
            cnt = 0
            for cfg in week_config:
                d_obj = cfg['date']
                s1, sl, el = cfg['times']
                k, b1, b2, c, om, oe = cfg['counts']
                
                start = (datetime.combine(d_obj, s1) - timedelta(minutes=45)).strftime("%H:%M")
                bar_end = (datetime.combine(d_obj, sl) + timedelta(minutes=15)).strftime("%H:%M")
                obs_end = (datetime.combine(d_obj, el) + timedelta(minutes=15)).strftime("%H:%M")
                split = "16:00"
                
                tasks = []
                for _ in range(k): tasks.append(("Kasa", "morning", start, split)); tasks.append(("Kasa", "evening", split, bar_end))
                for _ in range(b1): tasks.append(("Bar 1", "morning", start, split)); tasks.append(("Bar 1", "evening", split, bar_end))
                for _ in range(b2): tasks.append(("Bar 2", "morning", start, split)); tasks.append(("Bar 2", "evening", split, bar_end))
                for _ in range(c): tasks.append(("Cafe", "morning", start, split)); tasks.append(("Cafe", "evening", split, bar_end))
                for _ in range(om): tasks.append(("Obsługa", "morning", start, split))
                for _ in range(oe): tasks.append(("Obsługa", "evening", split, obs_end))
                
                assigned = {'morning': [], 'evening': [], 'all_day': []}
                for role, t_type, s, e in tasks:
                    worker = find_worker_for_shift(role, t_type, d_obj, st.session_state.db_employees, st.session_state.db_avail, assigned, shift_counts)
                    final = worker if worker else ""
                    
                    st.session_state.db_shifts.append({
                        "Data": str(d_obj), "Stanowisko": role, "Godziny": f"{s}-{e}", "Pracownik_Imie": final, "Typ": "Auto"
                    })
                    if worker:
                        assigned[t_type].append(worker)
                        assigned['all_day'].append(worker)
                        shift_counts[worker] += 1
                    cnt += 1
            
            save_all()
            st.success(f"Wygenerowano {cnt} zmian! Zobacz Grafik.")

    # --- 2. DYSPOZYCJE ---
    elif menu == "Dyspozycje":
        st.title("📥 Dyspozycje (Podgląd)")
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
    elif menu == "Kadry (Konta)":
        st.title("📇 Kadry i Konta")
        
        with st.expander("➕ Dodaj Pracownika i Konto"):
            with st.form("add_user"):
                u_name = st.text_input("Imię i Nazwisko")
                u_login = st.text_input("Login")
                u_pass = st.text_input("Hasło")
                u_roles = st.multiselect("Role", ["Obsługa", "Bar", "Kasa", "Cafe"])
                u_plec = st.selectbox("Płeć", ["K", "M"])
                
                if st.form_submit_button("Utwórz"):
                    # Dodaj do users
                    st.session_state.db_users[u_login] = {"pass": u_pass, "role": "worker", "name": u_name}
                    # Dodaj do employees
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
        # Wyświetlamy listę userów
        users_data = []
        for login, data in st.session_state.db_users.items():
            users_data.append({"Login": login, "Imię": data["name"], "Rola": data["role"]})
        st.dataframe(pd.DataFrame(users_data))

    # --- 4. GRAFIK ---
    elif menu == "Grafik":
        st.title("📋 Grafik")
        today = datetime.now().date()
        d_start = st.date_input("Pokaż tydzień od (Piątek):", today)
        
        # Konwersja listy słowników na DataFrame do wyświetlania
        df = pd.DataFrame(st.session_state.db_shifts)
        
        if not df.empty:
            # Filtrowanie po dacie (string compare)
            # Konwertujemy kolumnę Data na datetime do porównań
            df['DataObj'] = pd.to_datetime(df['Data']).dt.date
            d_end = d_start + timedelta(days=6)
            
            mask = (df['DataObj'] >= d_start) & (df['DataObj'] <= d_end)
            df_view = df.loc[mask]
            
            if not df_view.empty:
                st.markdown(render_html_schedule(df_view, d_start), unsafe_allow_html=True)
                st.write("---")
                if st.button("🖨️ PDF"):
                    pdf = generate_schedule_pdf(df_view, f"GRAFIK {d_start}")
                    st.download_button("Pobierz", pdf, "grafik.pdf", "application/pdf")
            else: st.info("Brak zmian w tym okresie.")
        else: st.info("Baza grafiku jest pusta.")
