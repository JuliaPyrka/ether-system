import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | SMART PARSER", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    .auto-generated { border: 2px dashed #fbbf24; padding: 10px; border-radius: 5px; }
    .success-slot { border-left: 5px solid #4caf50; padding-left: 10px; margin: 5px 0; background-color: #1e3a29; }
    .empty-slot { border-left: 5px solid #f44336; padding-left: 10px; margin: 5px 0; background-color: #3a1e1e; }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA UŻYTKOWNIKÓW ---
USERS = {
    "admin":  {"pass": "AlastorRules", "role": "manager", "name": "Szef"},
    "kierownik": {"pass": "film123", "role": "manager", "name": "Kierownik"},
    "julia":  {"pass": "julia1", "role": "worker", "name": "Julia Bąk"},
}

# --- SŁOWNIKI ---
SKILLS_LIST = ["Bar", "Cafe", "Obsługa", "Kasa", "Plakaty (Techniczne)"]
SCHEDULE_POSITIONS = ["Bar 1", "Bar 2", "Cafe", "Obsługa", "Kasa", "Plakaty", "Inwentaryzacja", "Pomoc Bar", "Pomoc Obsługa", "Sprzątanie Generalne"]

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
    for index, row in df_shifts.sort_values(by=["Data", "Stanowisko"]).iterrows():
        line = f"{row['Data']} | {row['Stanowisko']} | {row['Godziny']} | {row['Pracownik_Imie']}"
        pdf.cell(0, 8, clean_text(line), ln=True, border=1)
    return pdf.output(dest='S').encode('latin-1')

# --- KLUCZOWE: NOWY, MĄDRY PARSER DYSPOZYCJI ---
def is_avail_compatible(avail_str, shift_type):
    """
    Analizuje napisy typu: "8-16", "8 - 16", "16-1", "8-1/NM", "16-1?"
    Zwraca True, jeśli pracownik pasuje do zmiany.
    """
    if not avail_str or avail_str == "-" or len(avail_str) < 3:
        return False

    # 1. Normalizacja (usuwamy spacje, bierzemy część przed ukośnikiem)
    clean = avail_str.replace(" ", "").split("/")[0] # np. "8 - 1/NM" -> "8-1"
    
    # 2. Próba rozbicia na Start i Koniec
    try:
        # Szukamy dwóch liczb rozdzielonych czymś (myślnikiem)
        parts = re.split(r'[-–]', clean)
        if len(parts) != 2: return False
        
        s = int(parts[0]) # Start
        e = int(parts[1]) # End
        
        # 3. Logika dopasowania
        if shift_type == 'morning':
            # Zmiana ranna (np. 8:15 - 16:00)
            # Pracownik musi zacząć rano (7-11) I kończyć po 15:00 LUB kończyć w nocy (<=4)
            start_ok = (s >= 7 and s <= 12)
            end_ok = (e >= 15 or e <= 4)
            return start_ok and end_ok

        elif shift_type == 'evening':
            # Zmiana wieczorna (np. 16:00 - 00:15)
            # Pracownik musi być dostępny o 16:00.
            # Czyli start <= 16:00 ORAZ koniec w nocy (<=4) lub późno wieczorem (>=23)
            # UWAGA: Ktoś z "8-1" też pasuje na wieczór!
            
            # Przypadek A: Zaczyna po południu (15, 16, 17)
            starts_afternoon = (s >= 14 and s <= 18)
            # Przypadek B: Zaczął rano ale siedzi do nocy (8-1)
            starts_morning_stays_late = (s <= 12)
            
            ends_late = (e <= 4 or e >= 23)
            
            if starts_afternoon and ends_late: return True
            if starts_morning_stays_late and ends_late: return True
            return False
            
    except:
        return False # Jeśli wpisał głupoty, ignorujemy
    
    return False

def find_worker_for_shift(role_needed, shift_time_type, date_obj, employees_df, avail_grid):
    candidates = []
    
    for idx, emp in employees_df.iterrows():
        # 1. Sprawdź rolę
        has_role = False
        check_role = role_needed.replace(" 1", "").replace(" 2", "")
        if check_role in emp['Role'] or check_role in emp['Auto']:
            has_role = True
            
        if has_role:
            # 2. Sprawdź dyspozycję (SMART)
            key = f"{emp['Imie']}_{date_obj.strftime('%Y-%m-%d')}"
            avail = avail_grid.get(key, "")
            
            if is_avail_compatible(avail, shift_time_type):
                candidates.append(emp['Imie'])
    
    if candidates:
        return random.choice(candidates)
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
        rows.append({"ID": i+1, "Imie": p["Imie"], "Role": p["Role"], "Auto": calculate_auto_roles(p["Role"]), "Start": time(8,0), "End": time(23,0)})
    st.session_state.employees = pd.DataFrame(rows)

if 'shifts' not in st.session_state:
    st.session_state.shifts = pd.DataFrame([
         {"Data": datetime.now().date(), "Stanowisko": "Kasa", "Godziny": "09:00-16:00", "Pracownik_Imie": "Julia Bąk", "Typ": "Standardowa"},
    ])

if 'avail_grid' not in st.session_state: st.session_state.avail_grid = {}
if 'market' not in st.session_state: st.session_state.market = pd.DataFrame(columns=["Data", "Stanowisko", "Godziny", "Kto_Oddaje", "Komentarz"])

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
        menu = st.radio("Nawigacja:", ["Auto-Planer (Generator)", "Dyspozycje", "Kadry", "Grafik"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # --- AUTO-PLANER ---
    if menu == "Auto-Planer (Generator)":
        st.title("🚀 Generator Dnia")
        
        c1, c2 = st.columns(2)
        with c1:
            target_date = st.date_input("Data planowania:", datetime.now())
            first_movie = st.time_input("Początek 1. filmu:", time(9,0))
            last_movie_start = st.time_input("Start Ostatniego filmu:", time(21,0))
            last_movie_end = st.time_input("Koniec Ostatniego filmu:", time(0,0))
            
        with c2:
            dt_start = datetime.combine(datetime.today(), first_movie) - timedelta(minutes=45)
            t_open_str = dt_start.strftime("%H:%M")
            dt_bar_end = datetime.combine(datetime.today(), last_movie_start) + timedelta(minutes=15)
            t_bar_end_str = dt_bar_end.strftime("%H:%M")
            dt_obs_end = datetime.combine(datetime.today(), last_movie_end) + timedelta(minutes=15)
            t_obs_end_str = dt_obs_end.strftime("%H:%M")
            t_split = "16:00"
            
            st.info(f"""
            **Obliczone zmiany:**
            🌞 RANO: {t_open_str} - 16:00
            🌚 WIECZÓR BAR: 16:00 - {t_bar_end_str}
            🌚 WIECZÓR OBSŁUGA: 16:00 - {t_obs_end_str}
            """)

        if st.button("⚡ GENERUJ GRAFIK", type="primary"):
            slots = [
                ("Kasa", "morning", t_open_str, t_split),
                ("Bar 1", "morning", t_open_str, t_split),
                ("Bar 2", "morning", t_open_str, t_split),
                ("Cafe", "morning", t_open_str, t_split),
                ("Obsługa", "morning", t_open_str, t_split),
                ("Obsługa", "morning", t_open_str, t_split),
                
                ("Kasa", "evening", t_split, t_bar_end_str),
                ("Bar 1", "evening", t_split, t_bar_end_str),
                ("Bar 2", "evening", t_split, t_bar_end_str),
                ("Cafe", "evening", t_split, t_bar_end_str),
                ("Obsługa", "evening", t_split, t_obs_end_str),
                ("Obsługa", "evening", t_split, t_obs_end_str)
            ]
            
            st.write("### Wynik:")
            for role, time_type, s_time, e_time in slots:
                worker = find_worker_for_shift(role, time_type, target_date, st.session_state.employees, st.session_state.avail_grid)
                final_worker = worker if worker else "WAKAT (Brak chętnych)"
                hours = f"{s_time}-{e_time}"
                st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                    "Data": target_date, "Stanowisko": role, "Godziny": hours, "Pracownik_Imie": final_worker, "Typ": "Auto"
                }
                style = "success-slot" if worker else "empty-slot"
                st.markdown(f"<div class='{style}'><b>{role}</b> ({hours}): {final_worker}</div>", unsafe_allow_html=True)
            st.success("Gotowe!")

    # --- DYSPOZYCJE ---
    elif menu == "Dyspozycje":
        st.title("📥 Dyspozycje (Smart)")
        st.info("System akceptuje formaty: 8-16, 8 - 16, 16-1, 16-1/NM")
        d_start = st.date_input("Początek tygodnia:", datetime(2025, 11, 14))
        days = [d_start + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
        
        with st.form("grid_form"):
            cols = st.columns([2] + [1]*7)
            cols[0].write("**Pracownik**")
            for i, d in enumerate(days): cols[i+1].write(f"**{day_names[i]}**")
            
            for idx, emp in st.session_state.employees.iterrows():
                r_cols = st.columns([2] + [1]*7)
                r_cols[0].write(f"👤 {emp['Imie']}")
                for i, d in enumerate(days):
                    key = f"{emp['Imie']}_{d.strftime('%Y-%m-%d')}"
                    val = st.session_state.avail_grid.get(key, "")
                    new = r_cols[i+1].text_input("h", val, key=key, label_visibility="collapsed")
                    st.session_state.avail_grid[key] = new
            st.form_submit_button("Zapisz")

    # --- KADRY ---
    elif menu == "Kadry":
        st.title("📇 Kadry")
        st.dataframe(st.session_state.employees[["Imie", "Role"]])

    # --- GRAFIK ---
    elif menu == "Grafik":
        st.title("📋 Grafik")
        d = st.date_input("Od", datetime(2025, 11, 14))
        mask = (st.session_state.shifts['Data'] >= d) & (st.session_state.shifts['Data'] <= d + timedelta(days=6))
        df = st.session_state.shifts.loc[mask]
        if not df.empty:
            df['I'] = df['Godziny'] + "\n" + df['Pracownik_Imie']
            mx = df.pivot_table(index='Stanowisko', columns='Data', values='I', aggfunc=lambda x: "\n".join(x)).fillna("-")
            st.dataframe(mx, use_container_width=True, height=600)
        else: st.info("Pusto.")

# ==========================================
# PRACOWNIK
# ==========================================
elif st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        menu = st.radio("Menu:", ["📅 Mój Grafik"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()
    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        my = st.session_state.shifts[st.session_state.shifts['Pracownik_Imie'] == st.session_state.user_name]
        if not my.empty: st.dataframe(my, use_container_width=True)
