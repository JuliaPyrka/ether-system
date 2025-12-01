import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re
import os
import sqlite3
import hashlib
import streamlit.components.v1 as components


# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | SYNC MASTER", layout="wide")
DB_FILE = "ether.db"
HOURLY_RATE = 30.50  # Poprawiona spacja (Syntax Error fix)

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: #1a1c24; padding: 10px; border-radius: 10px; margin-top: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #333; border-radius: 5px; color: white; padding: 5px 20px; border: 1px solid #555; }
    .stTabs [aria-selected="true"] { background-color: #3b82f6 !important; font-weight: bold; border: 1px solid #3b82f6; }
    .config-box { background-color: #262626; padding: 20px; border-radius: 10px; border: 1px solid #444; margin-top: 15px; }
    .timesheet-card { background-color: #1a1c24; padding: 20px; border-radius: 10px; border: 1px solid #444; border-left: 5px solid #4caf50; }
    .wallet-card { background-color: #282828; padding: 15px; border-radius: 10px; border: 1px solid #555; text-align: center; margin-bottom: 20px; }
    .wallet-amount { font-size: 24px; font-weight: bold; color: #4caf50; }
    .notification-box { background-color: #2e3b55; border-left: 5px solid #fbbf24; padding: 10px; margin-bottom: 10px; border-radius: 5px; font-size: 14px; }
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

# --- OBSŁUGA BAZY DANYCH (SQLite) ---

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Tabela użytkowników
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 login TEXT PRIMARY KEY,
                 password_hash TEXT,
                 role TEXT,
                 name TEXT)''')
    
    # Tabela pracowników (rozszerzone dane)
    c.execute('''CREATE TABLE IF NOT EXISTS employees (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT,
                 roles TEXT,
                 gender TEXT,
                 auto_roles TEXT)''')
                 
    # Tabela zmian
    c.execute('''CREATE TABLE IF NOT EXISTS shifts (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 date TEXT,
                 role TEXT,
                 hours TEXT,
                 employee_name TEXT,
                 type TEXT)''')
                 
    # Tabela dostępności
    c.execute('''CREATE TABLE IF NOT EXISTS availability (
                 key_id TEXT PRIMARY KEY,
                 employee_name TEXT,
                 date TEXT,
                 val TEXT)''')
                 
    # Tabela logów czasu pracy
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 employee TEXT,
                 date TEXT,
                 start TEXT,
                 end TEXT,
                 hours REAL)''')
                 
    # Tabela powiadomień
    c.execute('''CREATE TABLE IF NOT EXISTS inbox (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_login TEXT,
                 message TEXT,
                 timestamp TEXT)''')
                 
    conn.commit()
    conn.close()
    
    # Utworzenie konta admina, jeśli nie istnieje
    create_user_if_not_exists("admin", "admin123", "manager", "Kierownik")

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(password):
    return hashlib.sha256(str(password).encode('utf-8')).hexdigest()

def create_user_if_not_exists(login, password, role, name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT login FROM users WHERE login=?", (login,))
    if not c.fetchone():
        c.execute("INSERT INTO users (login, password_hash, role, name) VALUES (?, ?, ?, ?)",
                  (login, hash_password(password), role, name))
        conn.commit()
    conn.close()

def check_login_db(u, p):
    conn = get_db_connection()
    c = conn.cursor()
    # Haszujemy wpisane hasło i porównujemy z bazą
    p_hash = hash_password(p)
    c.execute("SELECT role, name FROM users WHERE login=? AND password_hash=?", (u, p_hash))
    res = c.fetchone()
    conn.close()
    if res:
        return {"role": res[0], "name": res[1]}
    return None

# --- FUNKCJE POMOCNICZE ---

def polish_sort_key(text):
    alphabet = {'ą': 'a1', 'ć': 'c1', 'ę': 'e1', 'ł': 'l1', 'ń': 'n1', 'ó': 'o1', 'ś': 's1', 'ź': 'z1', 'ż': 'z2'}
    return "".join([alphabet.get(c.lower(), c.lower()) for c in text])

def calculate_auto_roles(selected_roles):
    auto = ["Sprzątanie Generalne"]
    if "Bar" in selected_roles:
        auto.append("Inwentaryzacja")
    if "Bar" in selected_roles and "Obsługa" in selected_roles:
        auto.extend(["Pomoc Bar", "Pomoc Obsługa"])
    return list(set(auto))

def clean_text(text):
    if not isinstance(text, str):
        text = str(text)
    replacements = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z', '–': '-'}
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def is_availability_locked():
    now = datetime.now()
    if now.weekday() in [1, 2, 3]: return True
    if now.weekday() == 0 and now.hour >= 23: return True
    return False

def send_notification_db(to_user_login, message):
    conn = get_db_connection()
    ts = datetime.now().strftime("%d.%m %H:%M")
    conn.execute("INSERT INTO inbox (user_login, message, timestamp) VALUES (?, ?, ?)", (to_user_login, message, ts))
    conn.commit()
    conn.close()

def get_avail_db(name, date_str):
    conn = get_db_connection()
    c = conn.cursor()
    key = f"{name}_{date_str}"
    c.execute("SELECT val FROM availability WHERE key_id=?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else ""

def save_avail_db(name, date_str, val):
    conn = get_db_connection()
    key = f"{name}_{date_str}"
    conn.execute("INSERT OR REPLACE INTO availability (key_id, employee_name, date, val) VALUES (?, ?, ?, ?)", 
                 (key, name, date_str, val))
    conn.commit()
    conn.close()

# --- ALGORYTMY GRAFIKOWE (UPGRADE) ---

def is_avail_compatible(avail_str, shift_type):
    if not avail_str or avail_str.strip() == "-" or len(avail_str.strip()) < 3:
        return False
    clean = avail_str.replace(" ", "")
    segments = clean.split("/")
    for seg in segments:
        if not seg: continue
        try:
            parts = re.split(r'[-–]', seg)
            if len(parts) != 2: continue
            s, e = int(parts[0]), int(parts[1])
        except: continue

        if shift_type == 'morning':
            if (6 <= s <= 12) and (e >= 15 or e <= 4): return True
        elif shift_type == 'evening':
            if (s <= 17) and (e <= 4 or e >= 22): return True
    return False

def check_11h_rule(employee_name, current_date_obj, shift_type, conn):
    """
    Sprawdza, czy pracownik nie miał późnej zmiany poprzedniego dnia.
    Jeśli zmiana jest rano, a wczoraj kończył po północy -> False.
    """
    if shift_type != 'morning':
        return True # Wieczorem zazwyczaj ok, chyba że pracował rano (ale tu upraszczamy)
    
    yesterday = (current_date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
    c = conn.cursor()
    c.execute("SELECT hours FROM shifts WHERE employee_name=? AND date=?", (employee_name, yesterday))
    prev_shifts = c.fetchall()
    
    for row in prev_shifts:
        h_str = row[0]
        try:
            _, end_part = h_str.split("-")
            end_h = int(end_part.split(":")[0])
            # Jeśli kończył między 0:00 a 5:00 rano
            if 0 <= end_h <= 5:
                return False
            # Jeśli kończył późno w nocy np. 23, a start jest 9 rano - to jest 10h, mało.
            if end_h >= 23:
                return False
        except:
            pass
    return True

def find_worker_for_shift_db(role_needed, shift_time_type, date_obj, assigned_today_names, shift_counts):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Pobierz wszystkich pracowników
    c.execute("SELECT name, roles, gender, auto_roles FROM employees")
    all_emps = []
    for row in c.fetchall():
        all_emps.append({
            "Imie": row[0],
            "Role": row[1], # json string or simple string? Assuming eval for list
            "Plec": row[2],
            "Auto": row[3]
        })
    
    candidates = []
    date_str = date_obj.strftime('%Y-%m-%d')
    
    for emp in all_emps:
        # 1. Czy już pracuje dzisiaj?
        if emp['Imie'] in assigned_today_names:
            continue
            
        # 2. Czy ma kompetencje?
        role_base = role_needed.replace(" 1", "").replace(" 2", "")
        # Parsowanie stringa listy ról (proste obejście, lepiej trzymać json)
        emp_roles = emp['Role'] 
        emp_auto = emp['Auto']
        
        if role_base not in emp_roles and role_base not in emp_auto:
            continue

        # 3. Sprawdź dostępność w bazie
        avail = get_avail_db(emp['Imie'], date_str)
        if is_avail_compatible(avail, shift_time_type):
            # 4. Sprawdź zasadę 11h (Kodeks Pracy)
            if check_11h_rule(emp['Imie'], date_obj, shift_time_type, conn):
                candidates.append(emp)
    
    conn.close()

    if not candidates:
        return None

    # Algorytm sprawiedliwości: Sortuj wg liczby zmian (rosnąco) -> potem losowo
    # Dzięki temu osoby z 0 zmianami są brane pierwsze
    random.shuffle(candidates) # najpierw tasowanie dla osób z tą samą liczbą
    candidates.sort(key=lambda x: shift_counts.get(x['Imie'], 0))

    final_candidate_name = None
    if role_needed == "Obsługa":
        men = [c for c in candidates if c.get('Plec') == 'M']
        if men:
            final_candidate_name = men[0]['Imie']
        else:
            women = [c for c in candidates if c.get('Plec') == 'K']
            if women:
                final_candidate_name = women[0]['Imie']
    
    if not final_candidate_name and candidates:
        final_candidate_name = candidates[0]['Imie']

    return final_candidate_name

# --- HTML & PDF ---

def render_html_schedule(df, start_date):
    days = [start_date + timedelta(days=i) for i in range(7)]
    date_header_str = f"{start_date.strftime('%d.%m')} - {days[-1].strftime('%d.%m')}"
    
    html = f"""
    <div style="background-color: #333; color: white; padding: 10px; text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 0px; border-radius: 5px 5px 0 0;">
        GRAFIK: {date_header_str}
    </div>
    <table class="schedule-table">
        <thead>
            <tr>
                <th style="width: 8%;">STANOWISKO</th>
    """
    for d in days:
        w_day = d.weekday()
        day_map = {4:"PIĄTEK", 5:"SOBOTA", 6:"NIEDZIELA", 0:"PONIEDZIAŁEK", 1:"WTOREK", 2:"ŚRODA", 3:"CZWARTEK"}
        style = 'style="background-color: #2c5282;"' if w_day in [4,5,6] else ''
        html += f'<th {style}><div class="day-header">{day_map.get(w_day, "")}<br>{d.strftime("%d.%m")}</div></th>'
    
    html += '</tr></thead><tbody>'
    visual_roles = ["Obsługa", "Kasa", "Bar 1", "Bar 2", "Cafe"]
    
    if not df.empty:
        df['Data_Obj'] = pd.to_datetime(df['date']).dt.date
    
    for role in visual_roles:
        html += f'<tr><td class="role-header">{role.upper()}</td>'
        for d in days:
            w_day = d.weekday()
            td_class = 'class="highlight-day"' if w_day in [4,5,6] else ''
            cell_content = ""
            if not df.empty:
                current_shifts = df[(df['Data_Obj'] == d) & (df['role'].str.contains(role, regex=False))]
                for _, row in current_shifts.iterrows():
                    emp_name = row['employee_name']
                    if not emp_name or emp_name == "WAKAT":
                        cell_content += f'<div class="empty-shift-box"><span class="empty-time">{row["hours"]}</span></div>'
                    else:
                        display_pos = "(Combo)" if "+" in row['role'] else ""
                        parts = emp_name.split(" ")
                        short = (parts[0] + " " + parts[-1][0] + ".") if len(parts) >= 2 else emp_name
                        cell_content += f'<div class="shift-box"><span class="shift-time">{row["hours"]}</span><span class="shift-name">{short} {display_pos}</span></div>'
            html += f'<td {td_class}>{cell_content}</td>'
        html += '</tr>'
    html += '</tbody></table>'
    return html

def generate_schedule_pdf(df, title):
    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean_text(title), ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", '', 8)
    if df.empty: return pdf.output(dest='S').encode('latin-1')
    
    days = sorted(df['date'].unique())
    for day in days:
        d_str = pd.to_datetime(day).strftime('%d.%m (%A)')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, clean_text(f"--- {d_str} ---"), ln=True)
        pdf.set_font("Arial", '', 10)
        day_shifts = df[df['date'] == day]
        for _, row in day_shifts.sort_values(by=["role"]).iterrows():
            name = row['employee_name'] if row['employee_name'] else "---"
            line = f"{row['role']} | {row['hours']} | {name}"
            pdf.cell(0, 8, clean_text(line), ln=True, border=1)
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')

# --- INICJALIZACJA ---
init_db()

# Global date sync
if 'active_week_start' not in st.session_state:
    today = datetime.now().date()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0: days_ahead += 7
    if today.weekday() == 4:
        st.session_state.active_week_start = today
    else:
        st.session_state.active_week_start = today + timedelta(days=days_ahead)

# Domyślne dane pracowników (jeśli baza pusta)
conn = get_db_connection()
if conn.cursor().execute("SELECT count(*) FROM employees").fetchone()[0] == 0:
    raw_data = [
        {"Imie": "Julia Bąk", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"], "Plec": "K"},
        {"Imie": "Kacper Borzechowski", "Role": ["Bar", "Obsługa", "Plakaty (Techniczne)"], "Plec": "M"},
        {"Imie": "Wiktor Buc", "Role": ["Obsługa"], "Plec": "M"},
        {"Imie": "Anna Dubińska", "Role": ["Bar", "Obsługa"], "Plec": "K"},
        {"Imie": "Jarosław Kaca", "Role": ["Bar", "Obsługa"], "Plec": "M"},
    ]
    for p in raw_data:
        auto = calculate_auto_roles(p["Role"])
        conn.execute("INSERT INTO employees (name, roles, gender, auto_roles) VALUES (?, ?, ?, ?)",
                     (p["Imie"], str(p["Role"]), p["Plec"], str(auto)))
    conn.commit()
    # Demo użytkownik
    create_user_if_not_exists("julia", "julia1", "worker", "Julia Bąk")
conn.close()


# ==========================================
# LOGOWANIE
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #d93025;'>ETHER SYSTEM v2</h1>", unsafe_allow_html=True)
        st.info("System korzysta teraz z bezpiecznej bazy SQLite.")
        u = st.text_input("Login")
        p = st.text_input("Hasło", type="password")
        if st.button("ZALOGUJ"):
            user_data = check_login_db(u, p)
            if user_data:
                st.session_state.logged_in = True
                st.session_state.user_role = user_data["role"]
                st.session_state.user_name = user_data["name"]
                st.session_state.user_login = u
                st.rerun()
            else:
                st.error("Błędny login lub hasło.")
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
        if st.button("Wyloguj"):
            st.session_state.logged_in = False
            st.rerun()

    conn = get_db_connection()
    msgs = conn.execute("SELECT id, message FROM inbox WHERE user_login=? ORDER BY id DESC", (st.session_state.user_login,)).fetchall()
    if msgs:
        with st.expander(f"🔔 Masz powiadomienia ({len(msgs)})", expanded=True):
            for mid, mtext in msgs:
                st.markdown(f"<div class='notification-box'>{mtext}</div>", unsafe_allow_html=True)
            if st.button("Wyczyść"):
                conn.execute("DELETE FROM inbox WHERE user_login=?", (st.session_state.user_login,))
                conn.commit()
                st.rerun()
    conn.close()

    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        conn = get_db_connection()
        my_shifts = pd.read_sql_query("SELECT date as Data, role as Stanowisko, hours as Godziny FROM shifts WHERE employee_name=?", conn, params=(st.session_state.user_name,))
        conn.close()
        
        if not my_shifts.empty:
            st.dataframe(my_shifts, use_container_width=True)
            st.info("Aby zamienić zmianę, skontaktuj się z kierownikiem lub znajdź zastępstwo na grupie.")
        else:
            st.info("Brak nadchodzących zmian.")

    elif menu == "✍️ Moja Dyspozycyjność":
        st.title("Moja Dyspozycyjność")
        is_locked = is_availability_locked()
        if is_locked:
            st.error("🔒 Edycja zablokowana.")
        else:
            st.success("🔓 Edycja otwarta.")

        start_d = st.session_state.active_week_start
        days = [start_d + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]

        st.info(f"Tydzień: **{start_d.strftime('%d.%m')} - {(start_d + timedelta(days=6)).strftime('%d.%m')}**")
        
        with st.form("worker_avail"):
            cols = st.columns(7)
            current_avails = {}
            for i, d in enumerate(days):
                cols[i].write(f"**{day_names[i]}** {d.strftime('%d.%m')}")
                val = get_avail_db(st.session_state.user_name, d.strftime('%Y-%m-%d'))
                new_val = cols[i].text_input("h", val, key=f"av_{i}", disabled=is_locked, label_visibility="collapsed")
                current_avails[d.strftime('%Y-%m-%d')] = new_val
            
            if st.form_submit_button("Zapisz", disabled=is_locked):
                for d_str, v in current_avails.items():
                    save_avail_db(st.session_state.user_name, d_str, v)
                st.toast("Zapisano w bazie!", icon="✅")

        st.write("---")
        st.subheader("👀 Podgląd Zespołu")
        with st.expander("Kto kiedy może?"):
            conn = get_db_connection()
            all_emps = [r[0] for r in conn.execute("SELECT name FROM employees ORDER BY name").fetchall()]
            avail_data = []
            for emp_name in all_emps:
                row = {"Pracownik": emp_name}
                has_val = False
                for d in days:
                    v = get_avail_db(emp_name, d.strftime('%Y-%m-%d'))
                    if v: has_val = True
                    row[d.strftime('%a')] = v
                if has_val: avail_data.append(row)
            conn.close()
            if avail_data:
                st.dataframe(pd.DataFrame(avail_data))

    elif menu == "⏱️ Karta Czasu":
        st.title("Ewidencja")
        conn = get_db_connection()
        my_shifts = pd.read_sql_query("SELECT date, role, hours FROM shifts WHERE employee_name=?", conn, params=(st.session_state.user_name,))
        
        if my_shifts.empty:
            st.warning("Brak zmian.")
        else:
            opts = my_shifts.apply(lambda x: f"{x['date']} | {x['role']} ({x['hours']})", axis=1).tolist()
            with st.container():
                st.markdown("<div class='timesheet-card'>", unsafe_allow_html=True)
                sel = st.selectbox("Wybierz zmianę:", opts)
                
                # Auto-uzupełnianie godzin
                def_s, def_e = time(16, 0), time(0, 0)
                try:
                    hp = sel.split("(")[1].replace(")", "")
                    s, e = hp.split("-")
                    def_s = datetime.strptime(s, "%H:%M").time()
                    def_e = datetime.strptime(e, "%H:%M").time()
                except: pass

                c1, c2, c3 = st.columns(3)
                c1.text_input("Data", value=sel.split(" | ")[0], disabled=True)
                ls = c2.time_input("Start", value=def_s)
                le = c3.time_input("Koniec", value=def_e)

                if st.button("➕ DODAJ GODZINY"):
                    ld = datetime.strptime(sel.split(" | ")[0], "%Y-%m-%d").date()
                    dt1 = datetime.combine(ld, ls)
                    dt2 = datetime.combine(ld, le)
                    if dt2 < dt1: dt2 += timedelta(days=1)
                    h = (dt2 - dt1).total_seconds() / 3600
                    
                    conn.execute("INSERT INTO logs (employee, date, start, end, hours) VALUES (?, ?, ?, ?, ?)",
                                 (st.session_state.user_name, str(ld), str(ls), str(le), round(h, 2)))
                    conn.commit()
                    st.success("Dodano!")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                
            st.divider()
            logs = pd.read_sql_query("SELECT date, start, end, hours FROM logs WHERE employee=?", conn, params=(st.session_state.user_name,))
            if not logs.empty:
                total = logs['hours'].sum()
                st.markdown(f"<div class='wallet-card'><div>Zarobek:</div><div class='wallet-amount'>{total * HOURLY_RATE:.2f} PLN</div></div>", unsafe_allow_html=True)
                st.dataframe(logs, use_container_width=True)
        conn.close()

# ==========================================
# PANEL MENEDŻERA
# ==========================================
elif st.session_state.user_role == "manager":
    with st.sidebar:
        st.title("🔧 PANEL KIEROWNIKA")
        menu = st.radio("Nawigacja:", ["Auto-Planer (LOGISTIC)", "Dyspozycje (Podgląd)", "Kadry (Edycja)", "Grafik (WIZUALNY)"])
        if st.button("Wyloguj"):
            st.session_state.logged_in = False
            st.rerun()

    if menu == "Auto-Planer (LOGISTIC)":
        st.title("🚀 Generator Logistyczny V2.1")
        st.caption("Precyzyjne planowanie obsady: Rano (☀️) vs Wieczór (🌙)")
        
        today = datetime.now().date()
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_friday = today + timedelta(days=days_ahead)
        if today.weekday() == 4: next_friday = today

        # Wybór tygodnia
        c_week, c_info = st.columns([1, 3])
        with c_week:
            week_start = st.date_input("Start (Piątek):", next_friday, min_value=today)
        with c_info:
            if week_start.weekday() != 4:
                st.error("⛔ Wybierz PIĄTEK! Grafik kinowy planujemy od piątku.")
            else:
                st.info(f"Planowanie dla okresu: {week_start.strftime('%d.%m')} - {(week_start + timedelta(days=6)).strftime('%d.%m')}")

        if week_start.weekday() == 4:
            week_days = [week_start + timedelta(days=i) for i in range(7)]
            week_config = []
            
            # --- ZAKŁADKI DNI ---
            tabs = st.tabs([f"{d.strftime('%A')[:3].upper()} {d.strftime('%d.%m')}" for d in week_days])
            
            for i, tab in enumerate(tabs):
                with tab:
                    # SEKJA 1: GODZINY
                    st.markdown("### 🕒 Godziny Graniczne")
                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        s1 = c1.time_input("Start Pierwszego Seansu", time(9, 0), key=f"s1_{i}")
                        sl = c2.time_input("Start Ostatniego Seansu", time(21, 0), key=f"sl_{i}")
                        el = c3.time_input("Koniec Ostatniego Seansu", time(0, 0), key=f"el_{i}")

                    # SEKJA 2: OBSADA
                    st.markdown("### 👥 Obsada Stanowisk")
                    with st.container(border=True):
                        # Nagłówki tabeli
                        h1, h2, h3 = st.columns([2, 1, 1])
                        h1.markdown("**Stanowisko**")
                        h2.markdown("☀️ **Rano**")
                        h3.markdown("🌙 **Wieczór**")
                        st.divider()

                        # Helper do generowania wierszy
                        def config_row(label, key_base, def_m, def_e, max_v=4):
                            r1, r2, r3 = st.columns([2, 1, 1])
                            r1.markdown(f"##### {label}")
                            val_m = r2.number_input(f"Rano", 0, max_v, def_m, key=f"{key_base}_m_{i}", label_visibility="collapsed")
                            val_e = r3.number_input(f"Wieczór", 0, max_v, def_e, key=f"{key_base}_e_{i}", label_visibility="collapsed")
                            return val_m, val_e

                        # Wiersze konfiguracji
                        k_m, k_e   = config_row("🎟️ KASA", "k", 1, 1)
                        b1_m, b1_e = config_row("🍿 BAR 1", "b1", 1, 2)
                        b2_m, b2_e = config_row("🍿 BAR 2", "b2", 0, 1)
                        c_m, c_e   = config_row("☕ CAFE", "c", 1, 1)
                        o_m, o_e   = config_row("🧹 OBSŁUGA", "obs", 2, 3)

                        # Zapis konfiguracji dnia
                        week_config.append({
                            "date": week_days[i],
                            "times": (s1, sl, el),
                            "counts": {
                                "Kasa": (k_m, k_e),
                                "Bar 1": (b1_m, b1_e),
                                "Bar 2": (b2_m, b2_e),
                                "Cafe": (c_m, c_e),
                                "Obsługa": (o_m, o_e)
                            }
                        })

            st.divider()
            if st.button("⚡ GENERUJ GRAFIK (NADDPISZ OBECNY)", type="primary", use_container_width=True):
                conn = get_db_connection()
                # Usuń stare zmiany
                start_s, end_s = str(week_days[0]), str(week_days[-1])
                conn.execute("DELETE FROM shifts WHERE date >= ? AND date <= ?", (start_s, end_s))
                conn.commit()

                # Pobranie pracowników
                all_emps = [r[0] for r in conn.execute("SELECT name FROM employees").fetchall()]
                shift_counts = {name: 0 for name in all_emps}
                
                cnt = 0
                for cfg in week_config:
                    d_obj = cfg['date']
                    s1, sl, el = cfg['times']
                    
                    # Logika godzin
                    start_m = (datetime.combine(d_obj, s1) - timedelta(minutes=45)).strftime("%H:%M")
                    split_time = "16:00" # Punkt zmiany zmian
                    
                    # Wyliczenie końców
                    bar_end = (datetime.combine(d_obj, sl) + timedelta(minutes=15)).strftime("%H:%M")
                    obs_end = (datetime.combine(d_obj, el) + timedelta(minutes=15)).strftime("%H:%M")

                    tasks = []
                    
                    # Iteracja po rolach i liczbach (Rano / Wieczór)
                    for role_name, (count_m, count_e) in cfg['counts'].items():
                        # Generowanie zmian porannych
                        for _ in range(count_m):
                            tasks.append((role_name, "morning", start_m, split_time))
                        # Generowanie zmian wieczornych
                        for _ in range(count_e):
                            # Dla obsługi koniec jest inny niż dla baru/kasy
                            end_time = obs_end if role_name == "Obsługa" else bar_end
                            tasks.append((role_name, "evening", split_time, end_time))

                    assigned_today = []
                    
                    # Przydzielanie ludzi
                    for role, t_type, s, e in tasks:
                        worker_name = find_worker_for_shift_db(role, t_type, d_obj, assigned_today, shift_counts)
                        final = worker_name if worker_name else "WAKAT"
                        
                        conn.execute("INSERT INTO shifts (date, role, hours, employee_name, type) VALUES (?, ?, ?, ?, ?)",
                                     (str(d_obj), role, f"{s}-{e}", final, "Auto"))
                        
                        if worker_name:
                            assigned_today.append(worker_name)
                            shift_counts[worker_name] += 1
                        cnt += 1
                
                conn.commit()
                
                # Powiadomienia
                users = conn.execute("SELECT login FROM users WHERE role='worker'").fetchall()
                for u_login in users:
                    send_notification_db(u_login[0], f"Nowy grafik na tydzień {week_start.strftime('%d.%m')}!")
                
                conn.close()
                st.balloons()
                st.success(f"Sukces! Wygenerowano {cnt} zmian zgodnie z nową konfiguracją.")

    elif menu == "Dyspozycje (Podgląd)":
        st.title("📥 Dyspozycje")
        d_start = st.session_state.active_week_start
        days = [d_start + timedelta(days=i) for i in range(7)]
        
        conn = get_db_connection()
        emps = conn.execute("SELECT name FROM employees ORDER BY name").fetchall()
        
        data = []
        for emp in emps:
            row = {"Pracownik": emp[0]}
            for d in days:
                row[d.strftime('%a')] = get_avail_db(emp[0], d.strftime('%Y-%m-%d'))
            data.append(row)
        conn.close()
        
        st.dataframe(pd.DataFrame(data))

    elif menu == "Kadry (Edycja)":
        st.title("📇 Kadry")
        with st.expander("➕ Dodaj Pracownika i Konto"):
            with st.form("add_user"):
                u_name = st.text_input("Imię i Nazwisko")
                u_login = st.text_input("Login")
                u_pass = st.text_input("Hasło")
                u_roles = st.multiselect("Role", ["Obsługa", "Bar", "Kasa", "Cafe"])
                u_plec = st.selectbox("Płeć", ["K", "M"])
                if st.form_submit_button("Utwórz"):
                    conn = get_db_connection()
                    try:
                        conn.execute("INSERT INTO users (login, password_hash, role, name) VALUES (?, ?, ?, ?)",
                                     (u_login, hash_password(u_pass), "worker", u_name))
                        auto = calculate_auto_roles(u_roles)
                        conn.execute("INSERT INTO employees (name, roles, gender, auto_roles) VALUES (?, ?, ?, ?)",
                                     (u_name, str(u_roles), u_plec, str(auto)))
                        conn.commit()
                        st.success("Dodano!")
                    except Exception as e:
                        st.error(f"Błąd: {e}")
                    conn.close()

        st.write("---")
        conn = get_db_connection()
        users = pd.read_sql_query("SELECT login, name, role FROM users", conn)
        conn.close()
        st.dataframe(users)

    elif menu == "Grafik (WIZUALNY)":
        st.title("📋 Grafik")
        tab_g, tab_s = st.tabs(["Grafik", "📊 Statystyki"])
        d_start = st.session_state.active_week_start
        d_end = d_start + timedelta(days=6)

        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM shifts", conn)
        conn.close()

        if not df.empty:
            df['DataObj'] = pd.to_datetime(df['date']).dt.date
            df_view = df[(df['DataObj'] >= d_start) & (df['DataObj'] <= d_end)].copy()
        else:
            df_view = pd.DataFrame()

        with tab_g:
            new_start = st.date_input("Tydzień (PIĄTEK):", d_start)
            if new_start != d_start and new_start.weekday() == 4:
                st.session_state.active_week_start = new_start
                st.rerun()

            if not df_view.empty:
            components.html(
                render_html_schedule(df_view, d_start),
                height=600,
                scrolling=True
            )
                
                c1, c2 = st.columns(2)
                if c1.button("🖨️ PDF"):
                    pdf = generate_schedule_pdf(df_view, f"GRAFIK {d_start}")
                    st.download_button("Pobierz", pdf, "grafik.pdf", "application/pdf")
                
                st.write("---")
                st.subheader("🛠️ Szybka Korekta")
                opts = df_view.apply(lambda x: f"{x['id']}: {x['date']} | {x['role']} | {x['employee_name']}", axis=1).tolist()
                
                c1, c2 = st.columns([3, 1])
                if opts:
                    sel = c1.selectbox("Wybierz zmianę:", opts)
                    conn = get_db_connection()
                    emps = [r[0] for r in conn.execute("SELECT name FROM employees").fetchall()]
                    conn.close()
                    new_p = c2.selectbox("Nowa osoba:", ["WAKAT"] + emps)
                    
                    if st.button("Zapisz zmianę"):
                        sid = sel.split(":")[0]
                        conn = get_db_connection()
                        conn.execute("UPDATE shifts SET employee_name=? WHERE id=?", (new_p, sid))
                        conn.commit()
                        conn.close()
                        st.rerun()

        with tab_s:
            if not df_view.empty:
                real = df_view[df_view['employee_name'] != "WAKAT"]
                counts = real['employee_name'].value_counts().reset_index()
                counts.columns = ["Pracownik", "Liczba Zmian"]
                st.bar_chart(counts.set_index("Pracownik"))
                st.dataframe(counts)


