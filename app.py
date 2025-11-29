import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re
import calendar

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | CONFIG MASTER", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .config-card { background-color: #1f2937; padding: 20px; border-radius: 10px; border-left: 5px solid #8b5cf6; margin-bottom: 20px; }
    .locked-box { opacity: 0.6; pointer-events: none; border: 1px solid #ff4b4b; }
    .success-slot { border-left: 5px solid #4caf50; padding-left: 10px; margin: 2px 0; background-color: #1e3a29; font-size: 0.9em; color: white; }
    .empty-slot { border-left: 5px solid #f44336; padding-left: 10px; margin: 2px 0; background-color: #3a1e1e; font-size: 0.9em; color: white; }
    .schedule-table { width: 100%; border-collapse: collapse; color: #000; background-color: #fff; font-size: 11px; }
    .schedule-table th { background-color: #444; color: #fff; padding: 8px; border: 1px solid #777; text-align: center; }
    .schedule-table td { border: 1px solid #ccc; padding: 4px; vertical-align: top; text-align: center; height: 60px; min-width: 80px; }
    .highlight-day { background-color: #e3f2fd !important; }
    .role-header { background-color: #eee; font-weight: bold; text-align: center; font-size: 12px; }
    .shift-box { background-color: #fff; border: 1px solid #aaa; border-radius: 3px; margin-bottom: 3px; padding: 2px; }
    .shift-time { font-weight: bold; display: block; color: #000; font-size: 10px; }
    .shift-name { display: block; color: #333; text-transform: uppercase; font-size: 9px; line-height: 1.1; }
    .day-header { font-size: 12px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA UŻYTKOWNIKÓW ---
USERS = {
    "admin":  {"pass": "AlastorRules", "role": "manager", "name": "Szef"},
    "kierownik": {"pass": "film123", "role": "manager", "name": "Kierownik"},
    "julia":  {"pass": "julia1", "role": "worker", "name": "Julia Bąk"},
    "kacper": {"pass": "kacper1", "role": "worker", "name": "Kacper Borzechowski"},
}

# --- GLOBALNA KONFIGURACJA (Domyślna) ---
if 'sys_config' not in st.session_state:
    st.session_state.sys_config = {
        "mode": "weekly_fri",  # Opcje: 'weekly_fri', 'weekly_mon', 'monthly'
        "lock_day_idx": 0,     # 0=Poniedziałek (Dla tygodniowych)
        "lock_day_num": 20,    # 20-ty dzień miesiąca (Dla miesięcznych)
        "lock_hour": 23        # Godzina blokady
    }

# --- FUNKCJE DATY (LOGIKA ROLOWANIA) ---
def get_planning_period():
    """Oblicza zakres dat do planowania na podstawie konfiguracji i dzisiejszej daty."""
    cfg = st.session_state.sys_config
    now = datetime.now()
    today = now.date()
    
    is_locked = False
    
    # 1. TRYB TYGODNIOWY (PIĄTEK - CZWARTEK)
    if cfg['mode'] == 'weekly_fri':
        # Znajdź najbliższy piątek (start cyklu)
        days_ahead = 4 - today.weekday() # 4=Piątek
        if days_ahead <= 0: days_ahead += 7
        next_start = today + timedelta(days=days_ahead)
        
        # Sprawdź blokadę (np. Poniedziałek 23:00)
        # Jeśli dziś > dzień_blokady LUB (dziś == dzień_blokady I godzina >= limit)
        current_weekday = now.weekday()
        lock_day = cfg['lock_day_idx']
        
        # Logika blokady w bieżącym tygodniu "zbierania"
        # Przyjmujemy: Zbieramy do Poniedziałku na tydzień zaczynający się w PIĄTEK
        # Jeśli minął termin, przesuwamy cel na KOLEJNY tydzień
        
        # Czy jesteśmy po terminie w tym tygodniu?
        # (Uproszczenie: jeśli dziś > lock_day, to blokada aktywna dla najbliższego cyklu, więc otwieramy następny)
        if current_weekday > lock_day or (current_weekday == lock_day and now.hour >= cfg['lock_hour']):
            is_locked = True
            # Jeśli zablokowane, pracownik widzi okres JESZCZE NASTĘPNY (+7 dni)
            # Ale uwaga: To zależy czy chcesz, żeby widział zablokowane, czy edytował nowe.
            # Twoje życzenie: "jednocześnie doda się możliwość wpisywania na następny"
            # Więc zwracamy następny okres jako "aktywny do edycji"
            next_start += timedelta(days=7)
            
        return next_start, 7 # Start, Długość (dni)

    # 2. TRYB TYGODNIOWY (PONIEDZIAŁEK - NIEDZIELA)
    elif cfg['mode'] == 'weekly_mon':
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_start = today + timedelta(days=days_ahead)
        
        current_weekday = now.weekday()
        lock_day = cfg['lock_day_idx']
        
        if current_weekday > lock_day or (current_weekday == lock_day and now.hour >= cfg['lock_hour']):
            is_locked = True
            next_start += timedelta(days=7)
            
        return next_start, 7

    # 3. TRYB MIESIĘCZNY
    elif cfg['mode'] == 'monthly':
        # Następny miesiąc
        if today.month == 12:
            next_month = datetime(today.year + 1, 1, 1).date()
        else:
            next_month = datetime(today.year, today.month + 1, 1).date()
            
        # Sprawdzenie blokady (np. do 20-go dnia miesiąca)
        if today.day > cfg['lock_day_num'] or (today.day == cfg['lock_day_num'] and now.hour >= cfg['lock_hour']):
            is_locked = True
            # Przeskok o kolejny miesiąc
            if next_month.month == 12:
                next_month = datetime(next_month.year + 1, 1, 1).date()
            else:
                next_month = datetime(next_month.year, next_month.month + 1, 1).date()
        
        # Ile dni w tym miesiącu?
        _, num_days = calendar.monthrange(next_month.year, next_month.month)
        return next_month, num_days

    return today, 7 # Fallback

# --- POZOSTAŁE FUNKCJE ---
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

# --- INITIALIZACJA ---
def init_session():
    if 'employees' not in st.session_state:
        # Baza startowa
        raw = [
            {"Imie": "Julia Bąk", "Role": ["Cafe", "Bar", "Obsługa", "Kasa"], "Plec": "K"},
            {"Imie": "Kacper Borzechowski", "Role": ["Bar", "Obsługa", "Plakaty (Techniczne)"], "Plec": "M"},
            {"Imie": "Wiktor Buc", "Role": ["Obsługa"], "Plec": "M"}
        ]
        rows = []
        for i, p in enumerate(raw):
            rows.append({"ID": i+1, "Imie": p["Imie"], "Role": p["Role"], "Plec": p["Plec"], "Auto": calculate_auto_roles(p["Role"])})
        st.session_state.employees = pd.DataFrame(rows)
    
    if 'shifts' not in st.session_state: st.session_state.shifts = pd.DataFrame(columns=["Data", "Stanowisko", "Godziny", "Pracownik_Imie", "Typ"])
    if 'avail_grid' not in st.session_state: st.session_state.avail_grid = {}
    if 'work_logs' not in st.session_state: st.session_state.work_logs = pd.DataFrame(columns=["Pracownik", "Data", "Start", "Koniec", "Godziny"])

init_session()

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
        menu = st.radio("Nawigacja:", ["Auto-Planer", "Dyspozycje (Podgląd)", "⚙️ Ustawienia Systemu"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # --- USTAWIENIA ---
    if menu == "⚙️ Ustawienia Systemu":
        st.title("⚙️ Konfiguracja ETHER")
        st.markdown("<div class='config-card'>Tu decydujesz, jak działa czas w Twoim kinie.</div>", unsafe_allow_html=True)
        
        cfg = st.session_state.sys_config
        
        new_mode = st.selectbox("1. Tryb Grafiku", 
                     ["weekly_fri", "weekly_mon", "monthly"], 
                     index=["weekly_fri", "weekly_mon", "monthly"].index(cfg['mode']),
                     format_func=lambda x: "Tygodniowy (Piątek-Czwartek)" if x=="weekly_fri" else ("Tygodniowy (Poniedziałek-Niedziela)" if x=="weekly_mon" else "Miesięczny"))
        
        st.write("---")
        st.write("2. Blokada Dyspozycyjności (Deadline)")
        
        if "weekly" in new_mode:
            day_map = {0:"Poniedziałek", 1:"Wtorek", 2:"Środa", 3:"Czwartek", 4:"Piątek", 5:"Sobota", 6:"Niedziela"}
            new_day = st.selectbox("Dzień blokady:", list(day_map.keys()), index=cfg['lock_day_idx'], format_func=lambda x: day_map[x])
            st.session_state.sys_config['lock_day_idx'] = new_day
        else:
            new_day_num = st.number_input("Dzień miesiąca (np. 20-go):", 1, 31, cfg['lock_day_num'])
            st.session_state.sys_config['lock_day_num'] = new_day_num
            
        new_hour = st.slider("Godzina blokady:", 0, 23, cfg['lock_hour'])
        
        if st.button("💾 ZAPISZ USTAWIENIA"):
            st.session_state.sys_config['mode'] = new_mode
            st.session_state.sys_config['lock_hour'] = new_hour
            st.success("Zapisano! System przeliczy okresy planowania.")

    # --- AUTO PLANER ---
    elif menu == "Auto-Planer":
        st.title("🚀 Generator")
        
        # Pobieramy aktywny okres z funkcji
        start_d, duration = get_planning_period()
        end_d = start_d + timedelta(days=duration-1)
        
        st.info(f"📅 Aktywny okres planowania: **{start_d.strftime('%d.%m')} - {end_d.strftime('%d.%m')}** (Typ: {st.session_state.sys_config['mode']})")
        
        # Tutaj normalna logika generatora (skrócona dla czytelności)
        st.write("(Tu pojawi się panel generowania dla wybranego okresu...)")

    # --- DYSPOZYCJE ---
    elif menu == "Dyspozycje (Podgląd)":
        st.title("📥 Podgląd Dyspozycji")
        start_d, duration = get_planning_period()
        days = [start_d + timedelta(days=i) for i in range(duration)]
        
        # Tabela (może być szeroka przy miesiącu)
        st.write(f"Okres: {start_d} - {start_d + timedelta(days=duration-1)}")
        
        with st.container(border=True):
            # Dynamiczne kolumny
            cols = st.columns([2] + [1]*len(days))
            cols[0].write("**Pracownik**")
            for i, d in enumerate(days): 
                cols[i+1].write(f"**{d.strftime('%d.%m')}**")
            
            for idx, emp in st.session_state.employees.iterrows():
                cols = st.columns([2] + [1]*len(days))
                cols[0].write(f"👤 {emp['Imie']}")
                for i, d in enumerate(days):
                    key = f"{emp['Imie']}_{d.strftime('%Y-%m-%d')}"
                    val = st.session_state.avail_grid.get(key, "-")
                    cols[i+1].write(val)

# ==========================================
# PRACOWNIK
# ==========================================
elif st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        menu = st.radio("Menu:", ["✍️ Moja Dyspozycyjność", "📅 Mój Grafik"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    if menu == "✍️ Moja Dyspozycyjność":
        st.title("Moja Dyspozycyjność")
        
        # MAGICZNA FUNKCJA ROLOWANIA
        start_d, duration = get_planning_period()
        end_d = start_d + timedelta(days=duration-1)
        
        st.success(f"🔓 Edytujesz dyspozycyjność na okres: **{start_d.strftime('%d.%m.%Y')} - {end_d.strftime('%d.%m.%Y')}**")
        st.caption("Poprzedni okres został zamknięty do edycji.")
        
        days = [start_d + timedelta(days=i) for i in range(duration)]
        
        # Formularz
        with st.form("worker_avail"):
            # Jeśli miesiąc - robimy wiersze po 7 dni dla czytelności
            chunk_size = 7
            for i in range(0, len(days), chunk_size):
                chunk = days[i:i+chunk_size]
                cols = st.columns(len(chunk))
                for j, d in enumerate(chunk):
                    # Nazwa dnia
                    day_name = d.strftime('%A') # Angielska, można spolszczyć mapą
                    cols[j].write(f"**{d.strftime('%d.%m')}**")
                    
                    key = f"{st.session_state.user_name}_{d.strftime('%Y-%m-%d')}"
                    val = st.session_state.avail_grid.get(key, "")
                    new_val = cols[j].text_input("h", val, key=f"w_{key}", label_visibility="collapsed")
                    st.session_state.avail_grid[key] = new_val
                st.write("---")
            
            st.form_submit_button("💾 ZAPISZ DYSPOZYCJE")
