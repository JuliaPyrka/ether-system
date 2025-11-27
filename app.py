import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | WEEKLY MASTER", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    .success-slot { border-left: 5px solid #4caf50; padding-left: 10px; margin: 2px 0; background-color: #1e3a29; font-size: 0.9em; }
    .empty-slot { border-left: 5px solid #f44336; padding-left: 10px; margin: 2px 0; background-color: #3a1e1e; font-size: 0.9em; }
    .day-header { background-color: #3b82f6; color: white; padding: 5px 10px; border-radius: 5px; margin-top: 20px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA UŻYTKOWNIKÓW ---
USERS = {
    "admin":  {"pass": "AlastorRules", "role": "manager", "name": "Szef"},
    "kierownik": {"pass": "film123", "role": "manager", "name": "Kierownik"},
    "julia":  {"pass": "julia1", "role": "worker", "name": "Julia Bąk"},
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

def generate_schedule_pdf(df_shifts, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(title), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 10)
    
    # Grupujemy po dniach w PDF
    days = df_shifts['Data'].unique()
    days.sort()
    
    for day in days:
        d_str = day.strftime('%d.%m (%A)')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, clean_text(f"--- {d_str} ---"), ln=True)
        pdf.set_font("Arial", '', 10)
        
        day_shifts = df_shifts[df_shifts['Data'] == day]
        for index, row in day_shifts.sort_values(by=["Stanowisko"]).iterrows():
            line = f"{row['Stanowisko']} | {row['Godziny']} | {row['Pracownik_Imie']}"
            pdf.cell(0, 8, clean_text(line), ln=True, border=1)
        pdf.ln(5)
        
    return pdf.output(dest='S').encode('latin-1')

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
            # Obsługa 8-1 też powinna łapać się na wieczór!
            is_start_ok = (s <= 17)
            is_end_ok = (e <= 4 or e >= 22)
            if is_start_ok and is_end_ok: return True
    except: return False
    return False

def find_worker_for_shift(role_needed, shift_time_type, date_obj, employees_df, avail_grid):
    candidates = []
    for idx, emp in employees_df.iterrows():
        check_role = role_needed.replace(" 1", "").replace(" 2", "")
        if check_role in emp['Role'] or check_role in emp['Auto']:
            key = f"{emp['Imie']}_{date_obj.strftime('%Y-%m-%d')}"
            avail = avail_grid.get(key, "")
            if is_avail_compatible(avail, shift_time_type):
                candidates.append(emp['Imie'])
    
    if candidates: return random.choice(candidates)
    return None

# --- PAMIĘĆ SESJI ---
if 'employees' not in st.session_state:
    data = [
        {"Imie": "Julia Bąk", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"]},
        {"Imie": "Kacper Borzechowski", "Role": ["Bar", "Obsługa", "Plakaty (Techniczne)"]},
        {"Imie": "Wiktor Buc", "Role": ["Obsługa"]},
        {"Imie": "Anna Dubińska", "Role": ["Bar", "Obsługa"]},
        {"Imie": "Julia Fidor", "Role": ["Bar", "Obsługa"]},
        {"Imie": "Julia Głowacka", "Role": ["Cafe", "Bar", "Obsługa"]},
        {"Imie": "Martyna Grela", "Role": ["Bar", "Obsługa"]},
        {"Imie": "Weronika Jabłońska", "Role": ["Bar", "Obsługa"]},
        {"Imie": "Jarosław Kaca", "Role": ["Bar", "Obsługa"]},
        {"Imie": "Michał Kowalczyk", "Role": ["Obsługa"]},
        {"Imie": "Dominik Mleczkowski", "Role": ["Cafe", "Bar", "Obsługa"]},
        {"Imie": "Aleksandra Pacek", "Role": ["Cafe", "Bar", "Obsługa"]},
        {"Imie": "Paweł Pod", "Role": ["Obsługa"]},
        {"Imie": "Aleksander Prus", "Role": ["Obsługa"]},
        {"Imie": "Julia Pyrka", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"]},
        {"Imie": "Wiktoria Siara", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"]},
        {"Imie": "Damian Siwak", "Role": ["Obsługa"]},
        {"Imie": "Katarzyna Stanisławska", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"]},
        {"Imie": "Patryk Szczodry", "Role": ["Obsługa"]},
        {"Imie": "Anna Szymańska", "Role": ["Bar", "Obsługa"]},
        {"Imie": "Hubert War", "Role": ["Bar", "Obsługa", "Plakaty (Techniczne)"]},
        {"Imie": "Marysia Wojtysiak", "Role": ["Cafe", "Bar", "Obsługa"]},
        {"Imie": "Michał Wojtysiak", "Role": ["Obsługa"]},
        {"Imie": "Weronika Ziętkowska", "Role": ["Cafe", "Bar", "Obsługa"]},
        {"Imie": "Magda Żurowska", "Role": ["Bar", "Obsługa"]}
    ]
    rows = []
    for i, p in enumerate(data):
        rows.append({"ID": i+1, "Imie": p["Imie"], "Role": p["Role"], "Auto": calculate_auto_roles(p["Role"])})
    st.session_state.employees = pd.DataFrame(rows)

if 'shifts' not in st.session_state: st.session_state.shifts = pd.DataFrame(columns=["Data", "Stanowisko", "Godziny", "Pracownik_Imie", "Typ"])
if 'avail_grid' not in st.session_state: st.session_state.avail_grid = {}

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
        menu = st.radio("Nawigacja:", ["Auto-Planer (TYDZIEŃ)", "Dyspozycje (Szybkie)", "Kadry", "Grafik"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # --- 1. AUTO-PLANER (TYGODNIOWY) ---
    if menu == "Auto-Planer (TYDZIEŃ)":
        st.title("🚀 Generator Tygodniowy (Pt-Cz)")
        
        c1, c2 = st.columns(2)
        with c1:
            # Domyślnie najbliższy piątek
            today = datetime.now()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0: days_ahead += 7
            next_friday = today + timedelta(days=days_ahead)
            
            week_start = st.date_input("Start cyklu (Piątek):", next_friday)
            
            st.markdown("### 🎬 Godziny Filmów (Wzorzec)")
            st.caption("Te godziny zostaną zastosowane do całego tygodnia. (Później możesz edytować poszczególne dni).")
            first_movie = st.time_input("Start 1. filmu:", time(9,0))
            last_movie_start = st.time_input("Start ostatniego:", time(21,0))
            last_movie_end = st.time_input("Koniec ostatniego:", time(0,0))
            
        with c2:
            st.info("Logika generowania:")
            st.write(f"📅 Generuję grafik od: **{week_start.strftime('%d.%m')} (Pt)** do **{(week_start + timedelta(days=6)).strftime('%d.%m')} (Cz)**")
            st.write("---")
            # Przeliczenia
            dt_start = datetime.combine(datetime.today(), first_movie) - timedelta(minutes=45)
            t_open = dt_start.strftime("%H:%M")
            t_bar_end = (datetime.combine(datetime.today(), last_movie_start) + timedelta(minutes=15)).strftime("%H:%M")
            t_obs_end = (datetime.combine(datetime.today(), last_movie_end) + timedelta(minutes=15)).strftime("%H:%M")
            t_split = "16:00"
            
            st.success(f"""
            🕒 Rano: {t_open} - 16:00
            🕒 Wieczór Bar: 16:00 - {t_bar_end}
            🕒 Wieczór Obsługa: 16:00 - {t_obs_end}
            """)

        if st.button("⚡ GENERUJ CAŁY TYDZIEŃ", type="primary"):
            # Generujemy dni od 0 (Piątek) do 6 (Czwartek)
            days_to_generate = [week_start + timedelta(days=i) for i in range(7)]
            
            slots_pattern = [
                ("Kasa", "morning", t_open, t_split),
                ("Bar 1", "morning", t_open, t_split),
                ("Bar 2", "morning", t_open, t_split),
                ("Cafe", "morning", t_open, t_split),
                ("Obsługa", "morning", t_open, t_split),
                ("Obsługa", "morning", t_open, t_split),
                ("Kasa", "evening", t_split, t_bar_end),
                ("Bar 1", "evening", t_split, t_bar_end),
                ("Bar 2", "evening", t_split, t_bar_end),
                ("Cafe", "evening", t_split, t_bar_end),
                ("Obsługa", "evening", t_split, t_obs_end),
                ("Obsługa", "evening", t_split, t_obs_end)
            ]
            
            # Czyścimy stare zmiany z tego tygodnia (żeby nie dublować)
            # st.session_state.shifts = st.session_state.shifts[~st.session_state.shifts['Data'].isin(days_to_generate)]
            
            cnt = 0
            for day in days_to_generate:
                day_name = day.strftime('%A')
                # st.markdown(f"#### Generuję: {day.strftime('%d.%m')} ({day_name})")
                
                for role, t_type, s, e in slots_pattern:
                    worker = find_worker_for_shift(role, t_type, day, st.session_state.employees, st.session_state.avail_grid)
                    final = worker if worker else "WAKAT"
                    hours = f"{s}-{e}"
                    
                    st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                        "Data": day, "Stanowisko": role, "Godziny": hours, "Pracownik_Imie": final, "Typ": "Auto"
                    }
                    cnt += 1
            
            st.balloons()
            st.success(f"Gotowe! Wygenerowano {cnt} zmian na cały tydzień. Przejdź do zakładki 'Grafik' aby pobrać PDF.")

    # --- 2. DYSPOZYCJE (SZYBKIE) ---
    elif menu == "Dyspozycje (Szybkie)":
        st.title("📥 Wpisz Dyspozycyjność")
        
        d_start = st.date_input("Start tygodnia (Piątek):", datetime(2025, 11, 14))
        days = [d_start + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
        
        with st.form("grid_form"):
            # Nagłówki
            cols = st.columns([3, 2, 1, 2, 2, 2, 2, 2, 2]) # Imię, Pt, Copy, Sb...
            cols[0].write("**Pracownik**")
            cols[1].write(f"**Pt**")
            cols[2].write(">>") # Strzałka kopiowania
            for i in range(1, 7): cols[i+2].write(f"**{day_names[i]}**")
            
            # Stan checkboxów "Kopiuj"
            copy_states = {}
            
            for idx, emp in st.session_state.employees.iterrows():
                r_cols = st.columns([3, 2, 1, 2, 2, 2, 2, 2, 2])
                r_cols[0].write(f"👤 {emp['Imie']}")
                
                # PIĄTEK (Baza)
                key_fri = f"{emp['Imie']}_{days[0].strftime('%Y-%m-%d')}"
                val_fri = st.session_state.avail_grid.get(key_fri, "")
                new_fri = r_cols[1].text_input("Pt", val_fri, key=key_fri, label_visibility="collapsed")
                st.session_state.avail_grid[key_fri] = new_fri
                
                # Checkbox "Cały tydzień"
                copy = r_cols[2].checkbox("Tydzień", key=f"copy_{emp['ID']}", help="Skopiuj Piątek na resztę dni")
                
                # RESZTA DNI
                for i in range(1, 7):
                    d = days[i]
                    key = f"{emp['Imie']}_{d.strftime('%Y-%m-%d')}"
                    
                    # Jeśli checkbox zaznaczony -> nadpisz wartością z piątku
                    if copy:
                        st.session_state.avail_grid[key] = new_fri
                        val = new_fri
                        disabled = True
                    else:
                        val = st.session_state.avail_grid.get(key, "")
                        disabled = False
                        
                    # Wyświetl (jeśli skopiowano, pokaż jako disabled żeby widać było efekt)
                    new_val = r_cols[i+2].text_input(day_names[i], val, key=key, label_visibility="collapsed", disabled=disabled)
                    if not disabled: st.session_state.avail_grid[key] = new_val

            st.form_submit_button("💾 ZAPISZ WSZYSTKO")

    # --- KADRY ---
    elif menu == "Kadry":
        st.title("📇 Kadry")
        st.dataframe(st.session_state.employees[["Imie", "Role"]])

    # --- GRAFIK ---
    elif menu == "Grafik":
        st.title("📋 Grafik Tygodniowy")
        d = st.date_input("Pokaż tydzień od:", datetime(2025, 11, 14))
        mask = (st.session_state.shifts['Data'] >= d) & (st.session_state.shifts['Data'] <= d + timedelta(days=6))
        df = st.session_state.shifts.loc[mask]
        
        if not df.empty:
            # MATRIX
            df['I'] = df['Godziny'] + "\n" + df['Pracownik_Imie']
            mx = df.pivot_table(index='Stanowisko', columns='Data', values='I', aggfunc=lambda x: "\n".join(x)).fillna("-")
            st.dataframe(mx, use_container_width=True, height=800)
            
            if st.button("🖨️ POBIERZ PDF (CAŁY TYDZIEŃ)"):
                pdf_bytes = generate_schedule_pdf(df, f"GRAFIK: {d.strftime('%d.%m')} - {(d+timedelta(days=6)).strftime('%d.%m')}")
                st.download_button("Pobierz Plik", pdf_bytes, "grafik_tygodniowy.pdf", "application/pdf")
        else: st.info("Pusto. Użyj Auto-Planera.")

elif st.session_state.user_role == "worker":
    st.info("Panel Pracownika")
