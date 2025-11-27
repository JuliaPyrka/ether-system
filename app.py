import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | LOGISTIC COMMANDER", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    
    /* STYL GRAFIKU HTML */
    .schedule-table { width: 100%; border-collapse: collapse; color: #000; background-color: #fff; font-family: Arial, sans-serif; font-size: 11px; }
    .schedule-table th { background-color: #444; color: #fff; padding: 8px; border: 1px solid #777; text-align: center; }
    .schedule-table td { border: 1px solid #ccc; padding: 4px; vertical-align: top; text-align: center; height: 60px; width: 12.5%; }
    .role-header { background-color: #eee; font-weight: bold; text-align: center; vertical-align: middle !important; border: 1px solid #999; font-size: 12px; }
    .shift-box { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 3px; margin-bottom: 3px; padding: 2px; }
    .shift-time { font-weight: bold; display: block; color: #000; font-size: 10px; }
    .shift-name { display: block; color: #333; text-transform: uppercase; font-size: 9px; line-height: 1.1; }
    .day-header { font-size: 12px; text-transform: uppercase; font-weight: bold; }
    
    .success-slot { border-left: 5px solid #4caf50; padding-left: 10px; margin: 2px 0; background-color: #1e3a29; font-size: 0.9em; color: white; }
    .empty-slot { border-left: 5px solid #f44336; padding-left: 10px; margin: 2px 0; background-color: #3a1e1e; font-size: 0.9em; color: white; }
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

# --- PARSER DYSPOZYCJI ---
def is_avail_compatible(avail_str, shift_type):
    if not avail_str or avail_str == "-" or len(avail_str) < 3: return False
    clean = avail_str.replace(" ", "").split("/")[0]
    try:
        parts = re.split(r'[-–]', clean)
        if len(parts) != 2: return False
        s, e = int(parts[0]), int(parts[1])
        
        if shift_type == 'morning':
            # Rano (start 6-12)
            if (6 <= s <= 12) and (e >= 15 or e <= 4): return True
        elif shift_type == 'evening':
            # Wieczór (start <= 17)
            if (s <= 17) and (e <= 4 or e >= 22): return True
    except: return False
    return False

# --- INTELIGENTNY DOBÓR PRACOWNIKA (Z KONFLIKTAMI I PŁCIĄ) ---
def find_worker_for_shift(role_needed, shift_time_type, date_obj, employees_df, avail_grid, assigned_today):
    candidates = []
    
    # 1. Filtrowanie kandydatów
    for idx, emp in employees_df.iterrows():
        # Sprawdź czy już nie pracuje w tej porze (Conflict Guard)
        if emp['Imie'] in assigned_today[shift_time_type]:
            continue
            
        # Sprawdź rolę
        role_base = role_needed.replace(" 1", "").replace(" 2", "")
        if role_base in emp['Role'] or role_base in emp['Auto']:
            # Sprawdź dyspozycję
            key = f"{emp['Imie']}_{date_obj.strftime('%Y-%m-%d')}"
            avail = avail_grid.get(key, "")
            if is_avail_compatible(avail, shift_time_type):
                candidates.append(emp) # Zapisujemy cały wiersz (z płcią)

    if not candidates:
        return None

    # 2. Preferencje Płci (Gender Bias)
    final_candidate = None
    
    if role_needed == "Obsługa":
        # Najpierw szukamy Panów (M)
        men = [c['Imie'] for c in candidates if c['Plec'] == 'M']
        if men:
            final_candidate = random.choice(men)
        else:
            # Jak nie ma panów, bierzemy panie
            women = [c['Imie'] for c in candidates if c['Plec'] == 'K']
            if women: final_candidate = random.choice(women)
    else:
        # Inne stanowiska - losowo
        final_candidate = random.choice([c['Imie'] for c in candidates])
        
    return final_candidate

# --- GENERATOR HTML ---
def render_html_schedule(df_shifts, start_date):
    pl_days = {0: "PON", 1: "WTO", 2: "ŚRO", 3: "CZW", 4: "PT", 5: "SOB", 6: "ND"}
    days = [start_date + timedelta(days=i) for i in range(7)]
    html = '<table class="schedule-table"><thead><tr><th style="width: 8%;">STANOWISKO</th>'
    for d in days:
        d_name = pl_days[d.weekday()]
        html += f'<th><div class="day-header">{d_name}<br>{d.strftime("%d.%m")}</div></th>'
    html += '</tr></thead><tbody>'
    
    visual_roles = ["Obsługa", "Kasa", "Bar 1", "Bar 2", "Cafe"]
    for role in visual_roles:
        html += f'<tr><td class="role-header">{role.upper()}</td>'
        for d in days:
            current_shifts = df_shifts[(df_shifts['Data'] == d) & (df_shifts['Stanowisko'].str.contains(role, regex=False))]
            cell_content = ""
            for _, row in current_shifts.iterrows():
                display_pos = "(Combo)" if "+" in row['Stanowisko'] else ""
                short = row['Pracownik_Imie'].split(" ")[0] + " " + row['Pracownik_Imie'].split(" ")[-1][0] + "."
                cell_content += f'<div class="shift-box"><span class="shift-time">{row["Godziny"]}</span><span class="shift-name">{short} {display_pos}</span></div>'
            html += f'<td>{cell_content}</td>'
        html += '</tr>'
    html += '</tbody></table>'
    return html

def generate_schedule_pdf(df_shifts, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(title), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 10)
    days = sorted(df_shifts['Data'].unique())
    for day in days:
        d_str = day.strftime('%d.%m (%A)')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, clean_text(f"--- {d_str} ---"), ln=True)
        pdf.set_font("Arial", '', 10)
        day_shifts = df_shifts[df_shifts['Data'] == day]
        for _, row in day_shifts.sort_values(by=["Stanowisko"]).iterrows():
            line = f"{row['Stanowisko']} | {row['Godziny']} | {row['Pracownik_Imie']}"
            pdf.cell(0, 8, clean_text(line), ln=True, border=1)
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')

# --- DATA SEEDING (DANE STARTOWE) ---
def preload_demo_data(start_date):
    demo_avail = {
        "Julia Bąk": ["16-1", "-", "8-1", "-", "16-1", "-", "16-1"], 
        "Kacper Borzechowski": ["-", "8-1", "8-1", "16-1", "8-1", "16-1", "16-1"],
        "Wiktor Buc": ["8-1", "8-1", "-", "-", "-", "8-1", "-"],
        "Anna Dubińska": ["-", "15-1", "16-1", "16-1", "8-1", "-", "16-1"],
        "Julia Fidor": ["15-1", "8-1", "8-1", "-", "13-1", "8-11", "14-1"],
        "Julia Głowacka": ["-", "8-1", "8-16", "15-1", "10-1", "18-1", "12-1"],
        "Martyna Grela": ["-", "8-1", "8-1", "15-1", "12-1", "-", "15-1"],
        "Weronika Jabłońska": ["8-16", "8-1", "8-1", "15-1", "15-1", "15-1", "-"],
        "Dominik Mleczkowski": ["8-16", "16-1", "8-1", "16-1", "16-1", "-", "8-16"],
        "Aleksandra Pacek": ["8-16", "8-1", "8-1", "-", "-", "16-1", "16-1"],
        "Julia Pyrka": ["16-1", "8-1", "8-1", "-", "8-11", "8-1", "16-1"],
        "Wiktoria Siara": ["8-16", "-", "8-16", "8-1", "-", "8-1", "8-1"],
        "Hubert War": ["8-1", "8-1", "8-16", "8-1", "8-1", "8-1", "8-1"],
        "Marysia Wojtysiak": ["8-16", "12-1", "8-1", "8-16", "-", "16-1", "8-1"],
        "Paweł Pod": ["8-16", "8-1", "8-1", "-", "16-1", "-", "16-1"],
        "Patryk Szczodry": ["-", "-", "-", "16-1", "16-1", "16-1", "16-1"],
        "Damian Siwak": ["8-16", "-", "8-16", "8-16", "8-16", "8-16", "8-16"],
        "Michał Kowalczyk": ["-", "-", "8-16", "8-16", "8-16", "-", "16-1"]
    }
    days = [start_date + timedelta(days=i) for i in range(7)]
    for name, avails in demo_avail.items():
        for i, val in enumerate(avails):
            key = f"{name}_{days[i].strftime('%Y-%m-%d')}"
            st.session_state.avail_grid[key] = val

# --- PAMIĘĆ SESJI ---
if 'employees' not in st.session_state:
    # Dodałem pole Płeć (M/K) na podstawie imion
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
    rows = []
    for i, p in enumerate(raw_data):
        rows.append({"ID": i+1, "Imie": p["Imie"], "Role": p["Role"], "Plec": p["Plec"], "Auto": calculate_auto_roles(p["Role"])})
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
        menu = st.radio("Nawigacja:", ["Auto-Planer (LOGISTIC)", "Dyspozycje (Szybkie)", "Kadry", "Grafik (WIZUALNY)"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # --- 1. AUTO-PLANER (LOGISTIC) ---
    if menu == "Auto-Planer (LOGISTIC)":
        st.title("🚀 Generator Logistyczny")
        
        c1, c2 = st.columns(2)
        with c1:
            today = datetime.now()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0: days_ahead += 7
            next_friday = today + timedelta(days=days_ahead)
            week_start = st.date_input("Start cyklu (Piątek):", next_friday)
            preload_demo_data(week_start) # Ładowanie demo dla wybranego tygodnia
            
            st.markdown("### 🎬 Godziny Filmów")
            first_movie = st.time_input("Start 1. filmu:", time(9,0))
            last_movie_start = st.time_input("Start ostatniego:", time(21,0))
            last_movie_end = st.time_input("Koniec ostatniego:", time(0,0))
            
        with c2:
            st.markdown("### 🔢 Obsada (Ile osób?)")
            st.caption("Ustaw 0, jeśli stanowisko ma być zamknięte.")
            
            # SUWAKI DO ZARZĄDZANIA ILOŚCIĄ
            count_kasa = st.number_input("KASA", 0, 2, 1)
            count_bar1 = st.number_input("BAR 1 (Główny)", 0, 2, 1)
            count_bar2 = st.number_input("BAR 2 (Dodatkowy)", 0, 2, 1)
            count_cafe = st.number_input("CAFE", 0, 1, 1)
            count_obs_morn = st.number_input("OBSŁUGA (Rano)", 1, 3, 1)
            count_obs_even = st.number_input("OBSŁUGA (Wieczór)", 1, 4, 2)

        if st.button("⚡ GENERUJ CAŁY TYDZIEŃ", type="primary"):
            days_to_generate = [week_start + timedelta(days=i) for i in range(7)]
            
            # Czyścimy stare
            mask = (st.session_state.shifts['Data'] >= days_to_generate[0].date()) & (st.session_state.shifts['Data'] <= days_to_generate[-1].date())
            st.session_state.shifts = st.session_state.shifts[~mask]
            
            # Obliczenia czasu
            dt_start = datetime.combine(datetime.today(), first_movie) - timedelta(minutes=45)
            t_open = dt_start.strftime("%H:%M")
            t_bar_end = (datetime.combine(datetime.today(), last_movie_start) + timedelta(minutes=15)).strftime("%H:%M")
            t_obs_end = (datetime.combine(datetime.today(), last_movie_end) + timedelta(minutes=15)).strftime("%H:%M")
            t_split = "16:00"
            
            cnt = 0
            
            for day in days_to_generate:
                # Śledzimy, kto już pracuje w tym dniu (żeby nie klonować)
                assigned_today = {'morning': [], 'evening': []}
                
                # LISTA ZADAŃ (Dynamiczna na podstawie suwaków)
                daily_tasks = []
                
                # RANO
                for _ in range(count_kasa): daily_tasks.append(("Kasa", "morning", t_open, t_split))
                for _ in range(count_bar1): daily_tasks.append(("Bar 1", "morning", t_open, t_split))
                for _ in range(count_bar2): daily_tasks.append(("Bar 2", "morning", t_open, t_split))
                for _ in range(count_cafe): daily_tasks.append(("Cafe", "morning", t_open, t_split))
                for _ in range(count_obs_morn): daily_tasks.append(("Obsługa", "morning", t_open, t_split))
                
                # WIECZÓR
                for _ in range(count_kasa): daily_tasks.append(("Kasa", "evening", t_split, t_bar_end))
                for _ in range(count_bar1): daily_tasks.append(("Bar 1", "evening", t_split, t_bar_end))
                for _ in range(count_bar2): daily_tasks.append(("Bar 2", "evening", t_split, t_bar_end))
                for _ in range(count_cafe): daily_tasks.append(("Cafe", "evening", t_split, t_bar_end))
                for _ in range(count_obs_even): daily_tasks.append(("Obsługa", "evening", t_split, t_obs_end))
                
                # PRZYDZIAŁ
                for role, t_type, s, e in daily_tasks:
                    worker = find_worker_for_shift(role, t_type, day, st.session_state.employees, st.session_state.avail_grid, assigned_today)
                    
                    final = worker if worker else "WAKAT"
                    st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                        "Data": day.date(), "Stanowisko": role, "Godziny": f"{s}-{e}", "Pracownik_Imie": final, "Typ": "Auto"
                    }
                    if worker:
                        assigned_today[t_type].append(worker)
                    cnt += 1
            
            st.success(f"Wygenerowano {cnt} zmian! Konflikty rozwiązane. Płeć uwzględniona.")

    # --- 2. DYSPOZYCJE ---
    elif menu == "Dyspozycje (Szybkie)":
        st.title("📥 Dyspozycje")
        d_start = st.date_input("Start tygodnia (Piątek):", datetime(2025, 11, 28))
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
        st.title("📇 Kadry")
        st.dataframe(st.session_state.employees[["Imie", "Role", "Plec"]])

    # --- 4. GRAFIK (WIZUALNY) ---
    elif menu == "Grafik (WIZUALNY)":
        st.title("📋 Grafik Wizualny")
        d_start = st.date_input("Pokaż tydzień od (Piątek):", datetime(2025, 11, 28))
        d_end = d_start + timedelta(days=6)
        mask = (st.session_state.shifts['Data'] >= d_start.date()) & (st.session_state.shifts['Data'] <= d_end.date())
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

elif st.session_state.user_role == "worker":
    st.info("Panel Pracownika")
