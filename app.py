import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re
import json
import os

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | FULL INTEGRITY", layout="wide")
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
    .notification-box { background-color: #2e3b55; border-left: 5px solid #fbbf24; padding: 10px; margin-bottom: 10px; border-radius: 5px; font-size: 14px; }

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

# --- SYSTEM PLIKÓW ---
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

def check_login(u, p):
    users = st.session_state.db_users
    if u in users and users[u]["pass"] == p:
        return {"role": users[u]["role"], "name": users[u]["name"]}
    return None

def clean_text(text):
    if not isinstance(text, str): text = str(text)
    replacements = {'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z', '–':'-'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def is_availability_locked():
    now = datetime.now()
    if now.weekday() in [1, 2, 3]: return True 
    if now.weekday() == 0 and now.hour >= 23: return True 
    return False 

def send_notification(to_user_login, message):
    if 'db_inbox' not in st.session_state: st.session_state.db_inbox = {}
    if to_user_login not in st.session_state.db_inbox: st.session_state.db_inbox[to_user_login] = []
    timestamp = datetime.now().strftime("%d.%m %H:%M")
    st.session_state.db_inbox[to_user_login].insert(0, f"[{timestamp}] {message}")
    save_json('db_inbox.json', st.session_state.db_inbox)

def preload_demo_data(start_date):
    if not st.session_state.db_avail:
        demo_avail = {
            "Julia Bąk": ["16-1", "-", "8-1", "-", "16-1", "-", "16-1"], 
            "Kacper Borzechowski": ["-", "8-1", "8-1", "16-1", "8-1", "16-1", "16-1"],
        }
        days = [start_date + timedelta(days=i) for i in range(7)]
        for name, avails in demo_avail.items():
            for i, val in enumerate(avails):
                key = f"{name}_{days[i].strftime('%Y-%m-%d')}"
                st.session_state.db_avail[key] = val
        save_json('db_avail.json', st.session_state.db_avail)

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

def find_worker_for_shift(role_needed, shift_time_type, date_obj, employees_list, avail_grid, assigned_today, shift_counts):
    candidates = []
    date_str = date_obj.strftime('%Y-%m-%d')
    
    for emp in employees_list:
        if emp['Imie'] in assigned_today[shift_time_type]: continue
        
        role_base = role_needed.replace(" 1", "").replace(" 2", "")
        if role_base in emp['Role'] or role_base in emp['Auto']:
            key = f"{emp['Imie']}_{date_str}"
            avail = avail_grid.get(key, "")
            if is_avail_compatible(avail, shift_time_type):
                candidates.append(emp)

    if not candidates: return None

    candidates.sort(key=lambda x: (shift_counts.get(x['Imie'], 0), random.random()))
    
    final_candidate_name = None
    if role_needed == "Obsługa":
        men = [c for c in candidates if c.get('Plec') == 'M']
        if men: final_candidate_name = men[0]['Imie']
        else:
            women = [c for c in candidates if c.get('Plec') == 'K']
            if women: final_candidate_name = women[0]['Imie']
    else:
        final_candidate_name = candidates[0]['Imie']
        
    return final_candidate_name

# --- HTML RENDER ---
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
    df = pd.DataFrame(shifts_data)
    if not df.empty:
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

# --- INICJALIZACJA ---
if 'db_users' not in st.session_state:
    st.session_state.db_users = load_json('db_users.json', {"admin": {"pass": "admin123", "role": "manager", "name": "Kierownik"}})
if 'db_employees' not in st.session_state:
    default_employees = []
    st.session_state.db_employees = load_json('db_employees.json', default_employees)
if 'db_shifts' not in st.session_state:
    st.session_state.db_shifts = load_json('db_shifts.json', [])
if 'db_avail' not in st.session_state:
    st.session_state.db_avail = load_json('db_avail.json', {})
if 'db_logs' not in st.session_state:
    st.session_state.db_logs = load_json('db_logs.json', [])
if 'db_inbox' not in st.session_state:
    st.session_state.db_inbox = load_json('db_inbox.json', {})

# DEMO DATA (TYLKO GDY PUSTE)
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
    
    if "julia" not in st.session_state.db_users:
        st.session_state.db_users["julia"] = {"pass": "julia1", "role": "worker", "name": "Julia Bąk"}
        st.session_state.db_users["kacper"] = {"pass": "kacper1", "role": "worker", "name": "Kacper Borzechowski"}
    
    save_all()

def save_all():
    save_json('db_users.json', st.session_state.db_users)
    save_json('db_employees.json', st.session_state.db_employees)
    save_json('db_shifts.json', st.session_state.db_shifts)
    save_json('db_avail.json', st.session_state.db_avail)
    save_json('db_logs.json', st.session_state.db_logs)
    save_json('db_inbox.json', st.session_state.db_inbox)

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
                st.session_state.user_login = u
                st.rerun()
            else: st.error("Błąd.")
    st.stop()

# ==========================================
# PRACOWNIK
# ==========================================
if st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        st.caption("Panel Pracownika")
        menu = st.radio("Menu:", ["📅 Mój Grafik", "✍️ Moja Dyspozycyjność", "⏱️ Karta Czasu"])
        st.divider()
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    my_msgs = st.session_state.db_inbox.get(st.session_state.user_login, [])
    if my_msgs:
        with st.expander(f"🔔 Masz powiadomienia ({len(my_msgs)})", expanded=True):
            for m in my_msgs: st.markdown(f"<div class='notification-box'>{m}</div>", unsafe_allow_html=True)
            if st.button("Wyczyść"): 
                st.session_state.db_inbox[st.session_state.user_login] = []
                save_all()
                st.rerun()

    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        df = pd.DataFrame(st.session_state.db_shifts)
        if not df.empty:
            my = df[df['Pracownik_Imie'] == st.session_state.user_name]
            if not my.empty:
                st.dataframe(my[["Data", "Stanowisko", "Godziny"]], use_container_width=True)
                st.write("---")
                st.subheader("🔄 Giełda Zmian")
                shift_to_swap = st.selectbox("Oddaj zmianę:", my['Data'].astype(str) + " | " + my['Stanowisko'])
                if st.button("Szukaj zastępstwa"):
                    s_date, s_role = shift_to_swap.split(" | ")
                    role_base = s_role.replace(" 1", "").replace(" 2", "")
                    found = []
                    for emp in st.session_state.db_employees:
                        if emp['Imie'] == st.session_state.user_name: continue
                        if role_base in emp['Role'] or role_base in emp['Auto']:
                            key = f"{emp['Imie']}_{s_date}"
                            avail = st.session_state.db_avail.get(key, "")
                            if len(avail) > 2: found.append(f"{emp['Imie']} ({avail})")
                    if found: st.success(f"Zapytaj: {', '.join(found)}")
                    else: st.error("Brak chętnych.")
            else: st.info("Brak zmian.")
        else: st.info("Brak grafiku.")

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
        
        st.write("---")
        st.subheader("👀 Podgląd Zespołu")
        with st.expander("Kto kiedy może?"):
            avail_data = []
            for emp in st.session_state.db_employees:
                row = {"Pracownik": emp['Imie']}
                has_val = False
                for d in days:
                    k = f"{emp['Imie']}_{d.strftime('%Y-%m-%d')}"
                    v = st.session_state.db_avail.get(k, "")
                    if v: has_val = True
                    row[d.strftime('%a')] = v
                if has_val: avail_data.append(row)
            if avail_data: st.dataframe(pd.DataFrame(avail_data))

    elif menu == "⏱️ Karta Czasu":
        st.title("Ewidencja")
        df_shifts = pd.DataFrame(st.session_state.db_shifts)
        my_shifts = pd.DataFrame()
        if not df_shifts.empty:
            my_shifts = df_shifts[df_shifts['Pracownik_Imie'] == st.session_state.user_name]
        
        if my_shifts.empty:
            st.warning("Brak zmian w grafiku.")
        else:
            opts = my_shifts.apply(lambda x: f"{x['Data']} | {x['Stanowisko']} ({x['Godziny']})", axis=1).tolist()
            with st.container():
                st.markdown("<div class='timesheet-card'>", unsafe_allow_html=True)
                sel = st.selectbox("Wybierz zmianę:", opts)
                def_s, def_e = time(16,0), time(0,0)
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
                    st.session_state.db_logs.append({
                        "Pracownik": st.session_state.user_name, "Data": str(ld), "Start": str(ls), "Koniec": str(le), "Godziny": round(h, 2)
                    })
                    save_all()
                    st.success("Dodano!")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            
            st.divider()
            df_logs = pd.DataFrame(st.session_state.db_logs)
            if not df_logs.empty:
                my_logs_view = df_logs[df_logs['Pracownik'] == st.session_state.user_name]
                if not my_logs_view.empty:
                    rate = 30.50
                    total = my_logs_view['Godziny'].sum()
                    st.markdown(f"<div class='wallet-card'><div>Szacunkowy zarobek:</div><div class='wallet-amount'>{total * rate:.2f} PLN</div></div>", unsafe_allow_html=True)
                    st.dataframe(my_logs_view, use_container_width=True)

# ==========================================
# MENEDŻER
# ==========================================
elif st.session_state.user_role == "manager":
    with st.sidebar:
        st.title("🔧 PANEL KIEROWNIKA")
        menu = st.radio("Nawigacja:", ["Auto-Planer (LOGISTIC)", "Dyspozycje (Podgląd)", "Kadry (Edycja)", "Grafik (WIZUALNY)"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    if menu == "Auto-Planer (LOGISTIC)":
        st.title("🚀 Generator Logistyczny")
        today = datetime.now().date()
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_friday = today + timedelta(days=days_ahead)
        if today.weekday() == 4: next_friday = today
        with st.container(border=True):
            week_start = st.date_input("Start (Piątek):", next_friday, min_value=today)
            if week_start.weekday() != 4: st.error("⛔ Wybierz PIĄTEK!"); st.stop()
        
        preload_demo_data(week_start)
        week_days = [week_start + timedelta(days=i) for i in range(7)]
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
            current_shifts = st.session_state.db_shifts
            start_s = str(week_days[0])
            end_s = str(week_days[-1])
            st.session_state.db_shifts = [s for s in current_shifts if not (start_s <= s['Data'] <= end_s)]
            
            shift_counts = {emp['Imie']: 0 for emp in st.session_state.db_employees}
            cnt = 0
            for cfg in week_config:
                d_obj = cfg['date']
                s1, sl, el = cfg['times']
                k, b, o = cfg['counts']
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
                
                assigned = {'morning': [], 'evening': []}
                for role, t_type, s, e in tasks:
                    worker = find_worker_for_shift(role, t_type, d_obj, st.session_state.db_employees, st.session_state.db_avail, assigned, shift_counts)
                    final = worker if worker else "WAKAT"
                    st.session_state.db_shifts.append({
                        "Data": str(d_obj), "Stanowisko": role, "Godziny": f"{s}-{e}", "Pracownik_Imie": final, "Typ": "Auto"
                    })
                    if worker:
                        assigned[t_type].append(worker)
                        # Bonus za weekend i dyspozycyjność
                        points = 2 if d_obj.weekday() >= 4 else 1
                        shift_counts[worker] += points
                    cnt += 1
            
            for user_login in st.session_state.db_users:
                if st.session_state.db_users[user_login]['role'] == 'worker':
                    send_notification(user_login, f"Grafik na tydzień {week_start.strftime('%d.%m')} gotowy!")
            save_all()
            st.success(f"Wygenerowano {cnt} zmian!")

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

    elif menu == "Kadry (Edycja)":
        st.title("📇 Kadry i Konta")
        
        # --- PRZYWRÓCONA SEKCJA EDYCJI ---
        c_edit, c_table = st.columns([1, 2])
        
        with c_edit:
            st.subheader("Edytor")
            emp_names = [e['Imie'] for e in st.session_state.db_employees]
            selected = st.selectbox("Wybierz osobę:", ["-- NOWY --"] + emp_names)
            
            with st.form("edit_hr"):
                if selected == "-- NOWY --":
                    f_name = st.text_input("Imię i Nazwisko")
                    f_login = st.text_input("Login (opcjonalnie)")
                    f_pass = st.text_input("Hasło (opcjonalnie)")
                    f_role = st.multiselect("Role", ["Obsługa", "Bar", "Kasa", "Cafe"])
                    f_plec = st.selectbox("Płeć", ["K", "M"])
                    if st.form_submit_button("Utwórz"):
                        auto = calculate_auto_roles(f_role)
                        st.session_state.db_employees.append({
                            "ID": len(st.session_state.db_employees)+1, "Imie": f_name, 
                            "Role": f_role, "Plec": f_plec, "Auto": auto
                        })
                        if f_login and f_pass:
                            st.session_state.db_users[f_login] = {"pass": f_pass, "role": "worker", "name": f_name}
                        save_all()
                        st.rerun()
                else:
                    # Znajdź index
                    idx = next(i for i, e in enumerate(st.session_state.db_employees) if e['Imie'] == selected)
                    curr = st.session_state.db_employees[idx]
                    
                    f_name = st.text_input("Imię", value=curr['Imie'])
                    f_role = st.multiselect("Role", ["Obsługa", "Bar", "Kasa", "Cafe"], default=curr['Role'])
                    f_plec = st.selectbox("Płeć", ["K", "M"], index=0 if curr['Plec']=="K" else 1)
                    
                    c_save, c_del = st.columns(2)
                    if c_save.form_submit_button("Zapisz"):
                        st.session_state.db_employees[idx]['Imie'] = f_name
                        st.session_state.db_employees[idx]['Role'] = f_role
                        st.session_state.db_employees[idx]['Plec'] = f_plec
                        save_all()
                        st.rerun()
                    
                    if c_del.form_submit_button("Usuń"):
                        del st.session_state.db_employees[idx]
                        save_all()
                        st.rerun()

        with c_table:
            df = pd.DataFrame(st.session_state.db_employees)
            if not df.empty: st.dataframe(df[["Imie", "Role", "Plec"]], use_container_width=True, height=600)

    elif menu == "Grafik (WIZUALNY)":
        st.title("📋 Grafik")
        tab_g, tab_s = st.tabs(["Widok", "Statystyki"])
        today = datetime.now().date()
        d_start = st.date_input("Pokaż tydzień od (Piątek):", today)
        
        df = pd.DataFrame(st.session_state.db_shifts)
        if not df.empty:
            df['DataObj'] = pd.to_datetime(df['Data']).dt.date
            d_end = d_start + timedelta(days=6)
            mask = (df['DataObj'] >= d_start) & (df['DataObj'] <= d_end)
            df_view = df.loc[mask]
            
            if not df_view.empty:
                with tab_g:
                    st.markdown(render_html_schedule(df_view, d_start), unsafe_allow_html=True)
                    st.write("---")
                    if st.button("🖨️ PDF"):
                        pdf = generate_schedule_pdf(df_view, f"GRAFIK {d_start}")
                        st.download_button("Pobierz", pdf, "grafik.pdf", "application/pdf")
                    
                    # SZYBKA KOREKTA
                    st.write("---")
                    st.subheader("🛠️ Szybka Korekta")
                    # Etykiety zmian
                    df_view['Label'] = df_view.apply(lambda x: f"{x['Data']} | {x['Stanowisko']} | {x['Pracownik_Imie']}", axis=1)
                    shift_list = df_view['Label'].tolist()
                    
                    c1, c2 = st.columns([3,1])
                    target_shift = c1.selectbox("Zmiana:", shift_list)
                    new_person = c2.selectbox("Nowa osoba:", ["WAKAT"] + [e['Imie'] for e in st.session_state.db_employees])
                    
                    if st.button("Zmień"):
                        t_date, t_role, t_curr = target_shift.split(" | ")
                        # Znajdź w bazie i podmień
                        for s in st.session_state.db_shifts:
                            if s['Data'] == t_date and s['Stanowisko'] == t_role and s['Pracownik_Imie'] == t_curr:
                                s['Pracownik_Imie'] = "" if new_person == "WAKAT" else new_person
                                break
                        save_all()
                        st.rerun()

                with tab_s:
                    st.subheader("📊 Obciążenie")
                    real = df_view[df_view['Pracownik_Imie'].str.len() > 2]
                    if not real.empty:
                        counts = real['Pracownik_Imie'].value_counts().reset_index()
                        counts.columns = ["Pracownik", "Liczba Zmian"]
                        st.bar_chart(counts.set_index("Pracownik"))
                        st.dataframe(counts)
            else: st.info("Brak zmian.")
        else: st.info("Baza pusta.")
