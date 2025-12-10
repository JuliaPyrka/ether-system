import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re
import sqlite3
import hashlib

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | SYNC MASTER v3", layout="wide", page_icon="⚛️")
DB_FILE = "ether_v3.db"
HOURLY_RATE = 30.50

# --- STYLE CSS (DARK MODE & MOBILE FRIENDLY) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stat-card { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #333; text-align: center; }
    .stat-val { font-size: 24px; font-weight: bold; color: #4caf50; }
    .shift-card { background-color: #262730; padding: 15px; margin-bottom: 10px; border-radius: 8px; border-left: 5px solid #3b82f6; }
    .shift-card h4 { margin: 0; color: white; }
    .shift-card p { margin: 5px 0; font-size: 14px; color: #ccc; }
    .schedule-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .schedule-table th { background-color: #333; color: white; padding: 8px; border: 1px solid #555; }
    .schedule-table td { border: 1px solid #444; padding: 5px; text-align: center; vertical-align: top; width: 12.5%; }
    .shift-box { background-color: #e3f2fd; color: #000; padding: 2px; margin-bottom: 2px; border-radius: 3px; font-size: 10px; }
    .wakat-box { background-color: #ffcdd2; color: #b71c1c; padding: 2px; border: 1px dashed red; border-radius: 3px; font-size: 10px; font-weight: bold;}
    </style>
    """, unsafe_allow_html=True)

# --- BAZA DANYCH ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Użytkownicy
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        login TEXT PRIMARY KEY, password_hash TEXT, role TEXT, name TEXT
    )""")
    
    # Pracownicy (Dane kadrowe)
    c.execute("""CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, roles TEXT, gender TEXT, auto_roles TEXT
    )""")
    
    # Zmiany (Grafik)
    c.execute("""CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, role TEXT, hours TEXT, 
        employee_name TEXT, type TEXT, start_ts INTEGER, end_ts INTEGER
    )""")
    
    # Dostępność (Dyspozycje)
    c.execute("""CREATE TABLE IF NOT EXISTS availability (
        key_id TEXT PRIMARY KEY, employee_name TEXT, date TEXT, val TEXT
    )""")
    
    # Logi pracy (Ewidencja)
    c.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, employee TEXT, date TEXT, start TEXT, end TEXT, hours REAL
    )""")
    
    conn.commit()
    conn.close()
    
    # Konto admina (startowe)
    create_user_if_not_exists("admin", "admin", "manager", "Szef")

def get_db():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()

def create_user_if_not_exists(login, password, role, name):
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (login, password_hash, role, name) VALUES (?, ?, ?, ?)",
                     (login, hash_password(password), role, name))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def check_login(u, p):
    conn = get_db()
    res = conn.execute("SELECT role, name FROM users WHERE login=? AND password_hash=?", 
                       (u, hash_password(p))).fetchone()
    conn.close()
    return {"role": res[0], "name": res[1]} if res else None

# --- NARZĘDZIA POMOCNICZE ---

def parse_availability(avail_str):
    """
    Parsuje ciąg typu '8-16', '8-16/18-23', 'caly dzien' na listę krotek (start_h, end_h).
    Zwraca listę zakresów godzinowych dostępności.
    """
    if not avail_str or len(avail_str) < 3:
        return []
    
    ranges = []
    # Usuwamy spacje i dzielimy po "/"
    segments = avail_str.replace(" ", "").split("/")
    
    for seg in segments:
        try:
            if "-" in seg:
                parts = seg.split("-")
                s, e = int(parts[0]), int(parts[1])
                # Obsługa godzin nocnych (np. 18-2 w nocy) -> zamieniamy na 26 dla uproszczenia obliczeń w ramach doby
                if e < s: 
                    e += 24 
                ranges.append((s, e))
            elif "cały" in seg.lower() or "full" in seg.lower():
                ranges.append((0, 24))
        except:
            continue
    return ranges

def is_available_for_shift(avail_str, shift_start_h, shift_end_h):
    """Sprawdza czy dany ciąg dostępności pokrywa godziny zmiany."""
    avail_ranges = parse_availability(avail_str)
    
    # Normalizacja godzin zmiany (np. koniec 01:00 to 25:00)
    if shift_end_h < shift_start_h:
        shift_end_h += 24
        
    for (a_start, a_end) in avail_ranges:
        # Sprawdzamy czy przedział dostępności obejmuje przedział zmiany
        # Dostępność: 8-16 (8, 16), Zmiana: 10-14 (10, 14) -> OK
        if a_start <= shift_start_h and a_end >= shift_end_h:
            return True
    return False

def get_employees_available_for_time(date_str, shift_start_str, shift_end_str, current_user_name):
    """
    JARVIS Logic: Znajduje pracowników, którzy mogą wziąć zmianę, a nie mają jej jeszcze przypisanej.
    """
    conn = get_db()
    
    # 1. Pobierz godziny zmiany jako liczby
    try:
        sh_s = int(shift_start_str.split(":")[0])
        sh_e = int(shift_end_str.split(":")[0])
    except:
        return [] # Błąd formatu

    # 2. Pobierz wszystkich pracowników
    all_emps = pd.read_sql("SELECT name FROM employees", conn)['name'].tolist()
    
    candidates = []
    
    for emp in all_emps:
        if emp == current_user_name: continue # Nie szukamy siebie

        # 3. Sprawdź dostępność z bazy
        res = conn.execute("SELECT val FROM availability WHERE employee_name=? AND date=?", (emp, date_str)).fetchone()
        avail_val = res[0] if res else ""
        
        if is_available_for_shift(avail_val, sh_s, sh_e):
            # 4. Sprawdź czy ten pracownik nie ma już innej zmiany tego dnia, która koliduje
            # Uproszczenie: sprawdzamy czy ma jakąkolwiek zmianę tego dnia (w kinach zazwyczaj 1 zmiana dziennie)
            shift_check = conn.execute("SELECT id FROM shifts WHERE employee_name=? AND date=?", (emp, date_str)).fetchone()
            if not shift_check:
                candidates.append({'name': emp, 'avail': avail_val})
                
    conn.close()
    return candidates

# --- WIDOKI UI ---

def render_schedule_html(df, start_date):
    days = [start_date + timedelta(days=i) for i in range(7)]
    
    html = "<table class='schedule-table'><thead><tr><th style='width:10%'>ROLA</th>"
    for d in days:
        bg = "#444" if d.weekday() < 4 else "#2c5282" # Weekend na niebiesko
        html += f"<th style='background-color:{bg}'>{d.strftime('%a')}<br>{d.strftime('%d.%m')}</th>"
    html += "</tr></thead><tbody>"
    
    roles = ["Kierownik", "Kasa", "Bar", "Cafe", "Obsługa"] # Kolejność ról
    existing_roles = df['role'].unique() if not df.empty else []
    
    # Filtrujemy tylko role, które są w grafiku, ale trzymamy porządek
    display_roles = [r for r in roles if any(r in er for er in existing_roles)]
    if not display_roles: display_roles = list(existing_roles)

    df['DataObj'] = pd.to_datetime(df['date']).dt.date
    
    for role_cat in display_roles:
        html += f"<tr><td style='font-weight:bold; background:#eee; color:black'>{role_cat}</td>"
        for d in days:
            shifts = df[(df['DataObj'] == d) & (df['role'].str.contains(role_cat, na=False))]
            cell = ""
            for _, row in shifts.iterrows():
                emp = row['employee_name']
                hours = row['hours']
                if emp == "WAKAT":
                    cell += f"<div class='wakat-box'>{hours}<br>WAKAT</div>"
                else:
                    parts = emp.split(" ")
                    short_name = parts[0] + (" " + parts[1][0] + "." if len(parts)>1 else "")
                    cell += f"<div class='shift-box'>{hours}<br>{short_name}</div>"
            html += f"<td>{cell}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

# --- GŁÓWNA APLIKACJA ---
init_db()

# Sesja logowania
if "user" not in st.session_state:
    st.session_state.user = None

# LOGOWANIE
if not st.session_state.user:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.title("🔐 ETHER SYSTEM")
        l = st.text_input("Login")
        p = st.text_input("Hasło", type="password")
        if st.button("Zaloguj", type="primary", use_container_width=True):
            user = check_login(l, p)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Błąd logowania")
    st.stop()

# --- PANEL GŁÓWNY ---
user = st.session_state.user
role = user['role']
name = user['name']

with st.sidebar:
    st.header(f"Witaj, {name.split(' ')[0]}")
    st.caption(f"Rola: {role.upper()}")
    
    if role == "manager":
        page = st.radio("Menu", ["📊 Panel Główny", "📅 Generator Grafiku", "📥 Dyspozycyjność (Edycja)", "👥 Pracownicy"])
    else:
        page = st.radio("Menu", ["📅 Mój Grafik", "✍️ Moja Dyspozycyjność", "🌍 Grafik Ogólny"])
        
    st.divider()
    if st.button("Wyloguj"):
        st.session_state.user = None
        st.rerun()

# --- LOGIKA KIEROWNIKA ---
if role == "manager":
    
    if page == "📊 Panel Główny":
        st.title("Centrum Dowodzenia")
        
        # Statystyki miesiąca
        conn = get_db()
        current_month = datetime.now().strftime("%Y-%m")
        df_shifts = pd.read_sql(f"SELECT * FROM shifts WHERE date LIKE '{current_month}%'", conn)
        conn.close()
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='stat-card'>Liczba zmian w tym m-cu<div class='stat-val'>{len(df_shifts)}</div></div>", unsafe_allow_html=True)
        with c2:
            wakaty = len(df_shifts[df_shifts['employee_name'] == "WAKAT"])
            color = "#f44336" if wakaty > 0 else "#4caf50"
            st.markdown(f"<div class='stat-card'>Wakaty (do obsadzenia)<div class='stat-val' style='color:{color}'>{wakaty}</div></div>", unsafe_allow_html=True)
        with c3:
             # Proste sumowanie godzin
             total_h = 0
             for h_str in df_shifts['hours']:
                 try:
                     s, e = h_str.split("-")
                     s, e = int(s.split(":")[0]), int(e.split(":")[0])
                     if e < s: e += 24
                     total_h += (e - s)
                 except: pass
             st.markdown(f"<div class='stat-card'>Suma godzin zespołu<div class='stat-val'>{total_h}h</div></div>", unsafe_allow_html=True)

        st.subheader("Ranking godzinowy (Miesiąc)")
        if not df_shifts.empty:
            df_shifts['h_count'] = df_shifts['hours'].apply(lambda x: (int(x.split('-')[1].split(':')[0]) + 24 - int(x.split('-')[0].split(':')[0])) % 24 if '-' in x else 0)
            stats = df_shifts[df_shifts['employee_name'] != "WAKAT"].groupby('employee_name')['h_count'].sum().sort_values(ascending=False)
            st.bar_chart(stats)

    elif page == "📅 Generator Grafiku":
        st.title("Generator Grafiku")
        
        col_d, col_info = st.columns([1, 2])
        with col_d:
            start_date = st.date_input("Wybierz PIĄTEK rozpoczynający tydzień", value=datetime.now())
        
        if start_date.weekday() != 4:
            st.warning("⚠️ Grafik kinowy powinien zaczynać się od PIĄTKU.")
        
        days = [start_date + timedelta(days=i) for i in range(7)]
        day_labels = [d.strftime("%A %d.%m") for d in days]
        
        # Konfiguracja zapotrzebowania
        with st.expander("⚙️ Konfiguracja zapotrzebowania", expanded=True):
            # Uproszczony interfejs - jeden slider dla wszystkich dni dla demo, 
            # w pełnej wersji można robić per dzień jak w Twoim kodzie
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Zmiany Poranne (Start ~9:00)")
                req_morning_bar = st.number_input("Barmani Rano", 0, 5, 1)
                req_morning_obs = st.number_input("Obsługa Rano", 0, 5, 2)
            with col2:
                st.markdown("#### Zmiany Wieczorne (Start ~16:00)")
                req_evening_bar = st.number_input("Barmani Wieczór", 0, 5, 2)
                req_evening_obs = st.number_input("Obsługa Wieczór", 0, 5, 4)

        if st.button("🚀 GENERUJ GRAFIK (AUTO-BALANS)", type="primary"):
            conn = get_db()
            
            # 1. Wyczyść stary grafik na ten tydzień
            d_start_str = days[0].strftime("%Y-%m-%d")
            d_end_str = days[-1].strftime("%Y-%m-%d")
            conn.execute("DELETE FROM shifts WHERE date >= ? AND date <= ?", (d_start_str, d_end_str))
            
            # 2. Pobierz pracowników i ich role
            emps_df = pd.read_sql("SELECT * FROM employees", conn)
            
            # Pobierz statystyki godzin (żeby wyrównywać sprawiedliwie)
            # W prostym modelu zaczynamy od 0, w pełnym pobieralibyśmy z historii
            emp_hours_load = {name: 0 for name in emps_df['name']}
            
            generated_count = 0
            
            for day in days:
                d_str = day.strftime("%Y-%m-%d")
                
                # Definicja slotów (uproszczona)
                slots = []
                # Rano
                for _ in range(req_morning_bar): slots.append(("Bar", "09:00-16:00", 9, 16))
                for _ in range(req_morning_obs): slots.append(("Obsługa", "09:00-16:00", 9, 16))
                # Wieczór
                for _ in range(req_evening_bar): slots.append(("Bar", "16:00-01:00", 16, 1))
                for _ in range(req_evening_obs): slots.append(("Obsługa", "16:00-01:00", 16, 1))
                
                for role_req, hours_str, s_h, e_h in slots:
                    # Szukaj kandydata
                    candidates = []
                    
                    for _, emp in emps_df.iterrows():
                        # Czy ma rolę?
                        if role_req not in emp['roles'] and role_req not in emp['auto_roles']: continue
                        
                        # Czy dostępny?
                        avail = conn.execute("SELECT val FROM availability WHERE employee_name=? AND date=?", (emp['name'], d_str)).fetchone()
                        avail_str = avail[0] if avail else ""
                        
                        if is_available_for_shift(avail_str, s_h, e_h):
                            # Czy nie pracuje już dzisiaj?
                            check = conn.execute("SELECT id FROM shifts WHERE employee_name=? AND date=?", (emp['name'], d_str)).fetchone()
                            if not check:
                                candidates.append(emp['name'])
                    
                    chosen_one = "WAKAT"
                    if candidates:
                        # ALGORYTM SPRAWIEDLIWOŚCI: Sortuj po najmniejszym obciążeniu godzinami
                        candidates.sort(key=lambda x: emp_hours_load.get(x, 0))
                        # Bierz pierwszego (najmniej obciążonego) z elementem losowości dla top 2
                        pick_index = 0
                        if len(candidates) > 1:
                            pick_index = random.choice([0, 0, 1]) # 66% szans na tego z najmniejszą liczbą godzin
                        
                        chosen_one = candidates[pick_index]
                        
                        # Zwiększ licznik godzin (estymata)
                        duration = (e_h - s_h) if e_h > s_h else (24 - s_h + e_h)
                        emp_hours_load[chosen_one] += duration
                        
                    conn.execute("INSERT INTO shifts (date, role, hours, employee_name, type) VALUES (?, ?, ?, ?, ?)",
                                 (d_str, role_req, hours_str, chosen_one, "Auto"))
                    generated_count += 1
            
            conn.commit()
            conn.close()
            st.success(f"Wygenerowano {generated_count} zmian. Sprawiedliwość została zachowana, szefie.")

        # Podgląd grafiku
        conn = get_db()
        df = pd.read_sql("SELECT * FROM shifts", conn)
        conn.close()
        
        # Filtrujemy do wybranego tygodnia
        d_start_ts = pd.to_datetime(start_date)
        d_end_ts = d_start_ts + timedelta(days=6)
        
        if not df.empty:
            df['DataObj'] = pd.to_datetime(df['date'])
            mask = (df['DataObj'] >= d_start_ts) & (df['DataObj'] <= d_end_ts)
            df_view = df.loc[mask]
            
            if not df_view.empty:
                st.markdown(render_schedule_html(df_view, start_date), unsafe_allow_html=True)
            else:
                st.info("Brak zmian w tym tygodniu.")
    
    elif page == "📥 Dyspozycyjność (Edycja)":
        st.title("Edycja Dyspozycyjności")
        st.info("Jako Manager możesz edytować dyspozycje każdego pracownika.")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            sel_date = st.date_input("Wybierz datę początkową (Poniedziałek lub Piątek)", datetime.now())
        
        days_view = [sel_date + timedelta(days=i) for i in range(7)]
        
        conn = get_db()
        emps = pd.read_sql("SELECT name FROM employees ORDER BY name", conn)['name'].tolist()
        
        # Tabela edycyjna
        data = []
        for emp in emps:
            row = {"Pracownik": emp}
            for d in days_view:
                d_str = d.strftime("%Y-%m-%d")
                res = conn.execute("SELECT val FROM availability WHERE employee_name=? AND date=?", (emp, d_str)).fetchone()
                row[d.strftime("%Y-%m-%d")] = res[0] if res else ""
            data.append(row)
        conn.close()
        
        df_avail = pd.DataFrame(data)
        edited_df = st.data_editor(df_avail, use_container_width=True, num_rows="dynamic")
        
        if st.button("Zapisz zmiany w bazie"):
            conn = get_db()
            for index, row in edited_df.iterrows():
                emp_name = row['Pracownik']
                for d in days_view:
                    d_str = d.strftime("%Y-%m-%d")
                    val = row[d_str]
                    conn.execute("INSERT OR REPLACE INTO availability (key_id, employee_name, date, val) VALUES (?, ?, ?, ?)",
                                 (f"{emp_name}_{d_str}", emp_name, d_str, val))
            conn.commit()
            conn.close()
            st.toast("Zapisano pomyślnie!", icon="✅")

    elif page == "👥 Pracownicy":
        st.title("Zarządzanie Zespołem")
        
        with st.form("add_emp"):
            st.subheader("Nowy Pracownik")
            c1, c2 = st.columns(2)
            new_name = c1.text_input("Imię i Nazwisko")
            new_roles = c2.multiselect("Role", ["Obsługa", "Bar", "Kasa", "Cafe", "Kierownik"])
            new_login = c1.text_input("Login do systemu")
            new_pass = c2.text_input("Hasło startowe")
            
            if st.form_submit_button("Dodaj do systemu"):
                if new_name and new_login:
                    conn = get_db()
                    # 1. Dodaj konto usera
                    create_user_if_not_exists(new_login, new_pass, "worker", new_name)
                    # 2. Dodaj dane kadrowe
                    auto_roles = []
                    if "Bar" in new_roles: auto_roles.append("Inwentaryzacja")
                    if "Kierownik" in new_roles: create_user_if_not_exists(new_login, new_pass, "manager", new_name)
                    
                    conn.execute("INSERT INTO employees (name, roles, gender, auto_roles) VALUES (?, ?, ?, ?)",
                                 (new_name, str(new_roles), "K/M", str(auto_roles)))
                    conn.commit()
                    conn.close()
                    st.success(f"Dodano {new_name} do bazy JARVIS.")

# --- LOGIKA PRACOWNIKA ---
else:
    if page == "📅 Mój Grafik":
        st.title("Mój Grafik")
        
        conn = get_db()
        my_shifts = pd.read_sql("SELECT * FROM shifts WHERE employee_name=? ORDER BY date", conn, params=(name,))
        conn.close()
        
        # Funkcja modalna do wymiany (Streamlit 1.34+)
        @st.dialog("🔁 Znajdź zastępstwo")
        def show_swap_options(shift_id, date, hours):
            st.write(f"Szukam kogoś na twoją zmianę: **{date} ({hours})**")
            st.caption("Lista osób, które mają wpisaną dyspozycyjność w tych godzinach i nie pracują:")
            
            candidates = get_employees_available_for_time(date, hours.split("-")[0], hours.split("-")[1], name)
            
            if not candidates:
                st.error("Brak dostępnych osób spełniających kryteria.")
            else:
                for cand in candidates:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"👤 **{cand['name']}**")
                    c1.caption(f"Dyspozycje: {cand['avail']}")
                    # Tu w prawdziwej aplikacji byłoby wysłanie powiadomienia
                    if c2.button("Poproś", key=f"btn_{cand['name']}"):
                        st.success(f"Wysłano prośbę do {cand['name']}!")
        
        if my_shifts.empty:
            st.info("Brak nadchodzących zmian. Odpoczywaj, szefie.")
        else:
            today = datetime.now().date()
            for _, row in my_shifts.iterrows():
                shift_date = datetime.strptime(row['date'], "%Y-%m-%d").date()
                if shift_date >= today:
                    with st.container():
                        st.markdown(f"""
                        <div class='shift-card'>
                            <h4>{row['date']} | {row['role']}</h4>
                            <p>Godziny: {row['hours']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("Znajdź zastępstwo", key=f"swap_{row['id']}"):
                            show_swap_options(row['id'], row['date'], row['hours'])

    elif page == "✍️ Moja Dyspozycyjność":
        st.title("Moja Dyspozycyjność")
        
        # Ustalanie aktywnego tygodnia (zawsze zaczynamy od najbliższego piątku lub aktualnego jeśli dziś piątek)
        today = datetime.now().date()
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        if today.weekday() == 4: next_friday = today
        else: next_friday = today + timedelta(days=days_ahead)
        
        st.subheader(f"Tydzień od: {next_friday.strftime('%d.%m.%Y')}")
        st.caption("Formaty: '8-16', '18-2', '8-16/18-23', 'cały dzień'")
        
        conn = get_db()
        
        with st.form("avail_form"):
            cols = st.columns(7)
            week_dates = [next_friday + timedelta(days=i) for i in range(7)]
            day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
            
            input_data = {}
            
            for i, d in enumerate(week_dates):
                d_str = d.strftime("%Y-%m-%d")
                # Pobierz obecną wartość
                curr = conn.execute("SELECT val FROM availability WHERE employee_name=? AND date=?", (name, d_str)).fetchone()
                val = curr[0] if curr else ""
                
                with cols[i]:
                    st.write(f"**{day_names[i]}**")
                    st.caption(d.strftime("%d.%m"))
                    new_val = st.text_input(f"d_{i}", value=val, label_visibility="collapsed")
                    input_data[d_str] = new_val
            
            if st.form_submit_button("Zapisz dyspozycje"):
                for d_str, v in input_data.items():
                    conn.execute("INSERT OR REPLACE INTO availability (key_id, employee_name, date, val) VALUES (?, ?, ?, ?)",
                                 (f"{name}_{d_str}", name, d_str, v))
                conn.commit()
                st.success("Dane zapisane.")
        conn.close()

    elif page == "🌍 Grafik Ogólny":
        st.title("Grafik Zespołu")
        conn = get_db()
        
        # Pobieramy daty z bazy (tydzień, w którym są zmiany)
        last_shift = conn.execute("SELECT date FROM shifts ORDER BY date DESC LIMIT 1").fetchone()
        if last_shift:
            ref_date = datetime.strptime(last_shift[0], "%Y-%m-%d")
            # Znajdź piątek tego tygodnia
            start_of_week = ref_date - timedelta(days=(ref_date.weekday() - 4) % 7)
        else:
            start_of_week = datetime.now()

        df = pd.read_sql("SELECT * FROM shifts", conn)
        conn.close()
        
        if not df.empty:
            st.markdown(render_schedule_html(df, start_of_week), unsafe_allow_html=True)
        else:
            st.info("Grafik nie został jeszcze opublikowany.")

# Stopka JARVISA
st.divider()
st.caption("ETHER SYSTEM v3.0 | Powered by JARVIS Logic Module | Leszno, PL")



