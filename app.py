import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta
import random
import re

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | VISUAL MASTER", layout="wide")

# --- STYLE CSS (WIZUALIZACJA JAK W PDF) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    
    /* STYL GRAFIKU (TABELA) */
    .schedule-table { width: 100%; border-collapse: collapse; color: black; background-color: white; font-family: Arial, sans-serif; font-size: 12px; }
    .schedule-table th { background-color: #333; color: white; padding: 10px; border: 1px solid #555; text-align: center; }
    .schedule-table td { border: 1px solid #000; padding: 5px; vertical-align: top; text-align: center; height: 80px; width: 12.5%; }
    .role-header { background-color: #ddd; font-weight: bold; text-align: center; padding: 5px; border: 1px solid #000; font-size: 14px; }
    .shift-box { margin-bottom: 8px; border-bottom: 1px dotted #aaa; padding-bottom: 2px; }
    .shift-time { font-weight: bold; font-size: 13px; display: block; color: #000; }
    .shift-name { font-size: 11px; display: block; color: #333; text-transform: uppercase; }
    .day-header { font-size: 14px; text-transform: uppercase; }
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

# --- GENERATOR HTML (WIZUALIZACJA) ---
def render_html_schedule(df_shifts, start_date):
    # Dni tygodnia PL
    pl_days = {0: "PONIEDZIAŁEK", 1: "WTOREK", 2: "ŚRODA", 3: "CZWARTEK", 4: "PIĄTEK", 5: "SOBOTA", 6: "NIEDZIELA"}
    
    # Generujemy listę 7 dni od start_date
    days = [start_date + timedelta(days=i) for i in range(7)]
    
    html = '<table class="schedule-table">'
    
    # NAGŁÓWEK (DNI)
    html += '<thead><tr><th style="width: 10%;">STANOWISKO</th>'
    for d in days:
        d_name = pl_days[d.weekday()]
        d_str = d.strftime('%d.%m')
        html += f'<th><div class="day-header">{d_name}<br>{d_str}</div></th>'
    html += '</tr></thead><tbody>'
    
    # WIERSZE (STANOWISKA) - Kolejność jak w PDF
    visual_roles = ["Obsługa", "Kasa", "Bar 1", "Bar 2", "Cafe"]
    
    for role in visual_roles:
        html += f'<tr><td class="role-header">{role.upper()}</td>'
        
        for d in days:
            # Filtrujemy zmiany dla danego dnia i roli
            # Uwaga: Bar 1 łapie też "Bar 1 + Cafe" (Combo)
            current_shifts = df_shifts[
                (df_shifts['Data'] == d) & 
                (df_shifts['Stanowisko'].str.contains(role, regex=False))
            ]
            
            cell_content = ""
            if not current_shifts.empty:
                for _, row in current_shifts.iterrows():
                    # Formatowanie wyświetlania
                    display_pos = ""
                    if "+" in row['Stanowisko'] and role in row['Stanowisko']:
                        display_pos = "(Combo)" # Oznaczenie dla combo
                    
                    cell_content += f'''
                    <div class="shift-box">
                        <span class="shift-time">{row['Godziny']}</span>
                        <span class="shift-name">{row['Pracownik_Imie']} {display_pos}</span>
                    </div>
                    '''
            
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
    for index, row in df_shifts.sort_values(by=["Data", "Stanowisko"]).iterrows():
        line = f"{row['Data']} | {row['Stanowisko']} | {row['Godziny']} | {row['Pracownik_Imie']}"
        pdf.cell(0, 8, clean_text(line), ln=True, border=1)
    return pdf.output(dest='S').encode('latin-1')

# --- PARSER DYSPOZYCJI ---
def is_avail_compatible(avail_str, shift_type):
    if not avail_str or avail_str == "-" or len(avail_str) < 3: return False, "Pusto"
    clean = avail_str.replace(" ", "").split("/")[0]
    try:
        parts = re.split(r'[-–]', clean)
        if len(parts) != 2: return False, "Format"
        s, e = int(parts[0]), int(parts[1])
        if shift_type == 'morning':
            if (6 <= s <= 12) and (e >= 15 or e <= 4): return True, "Ok"
        elif shift_type == 'evening':
            if (s <= 17) and (e <= 4 or e >= 22): return True, "Ok"
    except: return False, "Błąd"
    return False, "Nie pasuje"

def find_worker_for_shift(role_needed, shift_time_type, date_obj, employees_df, avail_grid):
    candidates = []
    for idx, emp in employees_df.iterrows():
        check_role = role_needed.replace(" 1", "").replace(" 2", "")
        if check_role in emp['Role'] or check_role in emp['Auto']:
            key = f"{emp['Imie']}_{date_obj.strftime('%Y-%m-%d')}"
            avail = avail_grid.get(key, "")
            ok, _ = is_avail_compatible(avail, shift_time_type)
            if ok: candidates.append(emp['Imie'])
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
        menu = st.radio("Nawigacja:", ["Auto-Planer (TYDZIEŃ)", "Dyspozycje (Szybkie)", "Kadry", "Grafik (WIZUALNY)"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # --- 1. AUTO-PLANER ---
    if menu == "Auto-Planer (TYDZIEŃ)":
        st.title("🚀 Generator Tygodniowy")
        
        c1, c2 = st.columns(2)
        with c1:
            today = datetime.now()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0: days_ahead += 7
            next_friday = today + timedelta(days=days_ahead)
            week_start = st.date_input("Start cyklu (Piątek):", next_friday)
            
            st.markdown("### 🎬 Godziny Filmów")
            first_movie = st.time_input("Start 1. filmu:", time(9,0))
            last_movie_start = st.time_input("Start ostatniego:", time(21,0))
            last_movie_end = st.time_input("Koniec ostatniego:", time(0,0))
            
        with c2:
            dt_start = datetime.combine(datetime.today(), first_movie) - timedelta(minutes=45)
            t_open = dt_start.strftime("%H:%M")
            t_bar_end = (datetime.combine(datetime.today(), last_movie_start) + timedelta(minutes=15)).strftime("%H:%M")
            t_obs_end = (datetime.combine(datetime.today(), last_movie_end) + timedelta(minutes=15)).strftime("%H:%M")
            t_split = "16:00"
            st.info(f"Otwarcie: {t_open} | Zamknięcie Bar: {t_bar_end} | Zamknięcie Obsługa: {t_obs_end}")

        if st.button("⚡ GENERUJ CAŁY TYDZIEŃ", type="primary"):
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
            cnt = 0
            for day in days_to_generate:
                for role, t_type, s, e in slots_pattern:
                    worker = find_worker_for_shift(role, t_type, day, st.session_state.employees, st.session_state.avail_grid)
                    final = worker if worker else "WAKAT"
                    st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                        "Data": day, "Stanowisko": role, "Godziny": f"{s}-{e}", "Pracownik_Imie": final, "Typ": "Auto"
                    }
                    cnt += 1
            st.success(f"Wygenerowano {cnt} zmian! Zobacz zakładkę 'Grafik (WIZUALNY)'.")

    # --- 2. DYSPOZYCJE ---
    elif menu == "Dyspozycje (Szybkie)":
        st.title("📥 Dyspozycje")
        d_start = st.date_input("Start tygodnia (Piątek):", datetime(2025, 11, 14))
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
        st.dataframe(st.session_state.employees[["Imie", "Role"]])

    # --- 4. GRAFIK (WIZUALNY) ---
    elif menu == "Grafik (WIZUALNY)":
        st.title("📋 Grafik Wizualny")
        
        d_start = st.date_input("Pokaż tydzień od (Piątek):", datetime(2025, 11, 28))
        
        # Filtrowanie danych do podglądu
        d_end = d_start + timedelta(days=6)
        mask = (st.session_state.shifts['Data'] >= d_start) & (st.session_state.shifts['Data'] <= d_end)
        df_view = st.session_state.shifts.loc[mask]
        
        if not df_view.empty:
            # RENDEROWANIE HTML
            html_table = render_html_schedule(df_view, d_start)
            st.markdown(html_table, unsafe_allow_html=True)
            
            st.write("---")
            if st.button("🖨️ POBIERZ PDF (LISTA)"):
                pdf_bytes = generate_schedule_pdf(df_view, f"GRAFIK: {d_start.strftime('%d.%m')} - {d_end.strftime('%d.%m')}")
                st.download_button("Pobierz Plik", pdf_bytes, "grafik.pdf", "application/pdf")
        else:
            st.info("Brak grafiku na ten tydzień. Użyj Auto-Planera.")

elif st.session_state.user_role == "worker":
    st.info("Panel Pracownika")
