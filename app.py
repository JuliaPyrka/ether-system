import streamlit as st
import pandas as pd
import plotly.express as px
from fpdf import FPDF
from datetime import datetime, time, timedelta

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | TASKMASTER", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    .hr-card { background-color: #1f2937; padding: 10px; border-radius: 5px; margin-bottom: 5px; border-left: 3px solid #3b82f6; }
    .combo-role { border-left: 3px solid #f44336 !important; } /* Czerwony dla Hybrydy */
    .task-role { border-left: 3px solid #4caf50 !important; } /* Zielony dla Plakatów */
    </style>
    """, unsafe_allow_html=True)

# --- BAZA DANYCH ---
USERS = {"admin": "AlastorRules", "kino": "film123", "demo": "demo"}

# Definicje Stanowisk
BASIC_ROLES = ["Obsługa", "Kasa", "Bar 1", "Bar 2", "Cafe"]
SPECIAL_TASKS = ["Plakaty (Techniczne)", "Inwentaryzacja", "Sprzątanie Generalne"]

# --- PAMIĘĆ SESJI (HR) ---
if 'employees' not in st.session_state:
    st.session_state.employees = pd.DataFrame([
        {"ID": 1, "Imie": "Anna Kowalska", "Role": ["Kasa", "Cafe"], "Start": time(8,0), "End": time(16,0)},
        {"ID": 2, "Imie": "Tomek Nowak", "Role": ["Obsługa", "Bar 1", "Bar 2", "Plakaty (Techniczne)"], "Start": time(16,0), "End": time(23,0)},
        {"ID": 3, "Imie": "Julia Manager", "Role": BASIC_ROLES + SPECIAL_TASKS, "Start": time(9,0), "End": time(22,0)},
        {"ID": 4, "Imie": "Kamil Hybryda", "Role": ["Bar 1", "Cafe", "Bar 2"], "Start": time(12,0), "End": time(20,0)}
    ])

if 'shifts' not in st.session_state:
    st.session_state.shifts = pd.DataFrame(columns=["Data", "Stanowisko", "Godziny", "Pracownik_ID", "Pracownik_Imie", "Typ"])

# --- FUNKCJE POMOCNICZE ---
def check_login(u, p): return u in USERS and USERS[u] == p

def clean_text(text):
    if not isinstance(text, str): text = str(text)
    replacements = {'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z', '–':'-'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def generate_schedule_pdf(df_shifts, date_str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(f"GRAFIK PRACY - KINO BAJKA ({date_str})"), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(50, 10, "Stanowisko/Zadanie", 1)
    pdf.cell(40, 10, "Godziny", 1)
    pdf.cell(60, 10, "Pracownik", 1)
    pdf.ln()
    pdf.set_font("Arial", '', 10)
    for _, row in df_shifts.iterrows():
        pos = row['Stanowisko']
        # Oznaczamy hybrydy w PDF gwiazdką
        if "+" in pos: pos = f"[*] {pos}"
        pdf.cell(50, 10, clean_text(pos), 1)
        pdf.cell(40, 10, clean_text(row['Godziny']), 1)
        pdf.cell(60, 10, clean_text(row['Pracownik_Imie']), 1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- LOGIKA HYBRYDOWA ---
def can_employee_do_combo(employee_roles, combo_string):
    """Sprawdza czy pracownik umie obie rzeczy z combo 'Bar 1 + Cafe'"""
    parts = combo_string.split(" + ")
    # Sprawdzamy czy pracownik ma WSZYSTKIE części składowe w swoich rolach
    return all(part in employee_roles for part in parts)

# ==========================================
# LOGIN
# ==========================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.title("ETHER SYSTEM")
        u = st.text_input("Login")
        p = st.text_input("Hasło", type="password")
        if st.button("ZALOGUJ"):
            if check_login(u, p):
                st.session_state.logged_in = True
                st.session_state.user = u
                st.rerun()
    st.stop()

# ==========================================
# APLIKACJA
# ==========================================
with st.sidebar:
    st.title(f"👤 {st.session_state.user.upper()}")
    app_mode = st.radio("WYBIERZ SYSTEM:", ["📊 ANALITYKA", "👥 GRAFIK (HR)"])
    if app_mode == "👥 GRAFIK (HR)":
        page_hr = st.radio("Moduł HR:", ["1. Baza Pracowników", "2. Planowanie Zmian", "3. Widok Grafiku"])
    st.divider()
    if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

# ==========================================
# SYSTEM HR
# ==========================================
if app_mode == "👥 GRAFIK (HR)":
    
    # --- 1. BAZA PRACOWNIKÓW ---
    if page_hr == "1. Baza Pracowników":
        st.title("📇 Baza Kadr")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("➕ Dodaj Osobę")
            with st.form("add_employee"):
                e_name = st.text_input("Imię i Nazwisko")
                # Łączymy listy ról, żeby można było zaznaczyć też plakaty
                e_roles = st.multiselect("Umiejętności:", BASIC_ROLES + SPECIAL_TASKS)
                col_t1, col_t2 = st.columns(2)
                e_start = col_t1.time_input("Od", time(8,0))
                e_end = col_t2.time_input("Do", time(22,0))
                if st.form_submit_button("Zapisz"):
                    new_id = len(st.session_state.employees) + 1
                    st.session_state.employees.loc[len(st.session_state.employees)] = {
                        "ID": new_id, "Imie": e_name, "Role": e_roles, "Start": e_start, "End": e_end
                    }
                    st.success("Dodano!")
                    st.rerun()
        with c2:
            st.subheader("Załoga")
            st.dataframe(st.session_state.employees[["ID", "Imie", "Role", "Start", "End"]], use_container_width=True)

    # --- 2. PLANOWANIE ZMIAN ---
    elif page_hr == "2. Planowanie Zmian":
        st.title("🗓️ Układanie Grafiku")
        
        # WYBÓR DATY
        c_date, c_type = st.columns(2)
        target_date = c_date.date_input("Dzień", datetime.now())
        
        # LOGIKA PLAKATÓW (Co 2 tygodnie w sobotę)
        is_saturday = target_date.weekday() == 5
        # Prosta symulacja parzystości tygodnia (numer tygodnia % 2)
        week_num = target_date.isocalendar()[1]
        is_poster_week = (week_num % 2 == 0) # Zakładamy, że w parzyste
        
        if is_saturday:
            if is_poster_week:
                st.info("ℹ️ To jest SOBOTA PLAKATOWA! Pamiętaj o zaplanowaniu osoby do plakatów.")
            else:
                st.caption("Sobota bez plakatów.")

        # KONFIGURATOR ZMIANY
        shift_type = c_type.selectbox("Rodzaj Zmiany:", ["Standardowa", "Hybryda (Combo)", "Zadanie Specjalne"])
        
        target_pos = None
        
        if shift_type == "Standardowa":
            target_pos = st.selectbox("Stanowisko", BASIC_ROLES)
        elif shift_type == "Zadanie Specjalne":
            target_pos = st.selectbox("Zadanie", SPECIAL_TASKS)
        elif shift_type == "Hybryda (Combo)":
            st.warning("⚠️ Hybryda wymaga pracownika z wieloma umiejętnościami.")
            p1 = st.selectbox("Część 1", ["Bar 1", "Bar 2"])
            p2 = st.selectbox("Część 2", ["Cafe", "Obsługa"])
            target_pos = f"{p1} + {p2}"
            st.write(f"Tworzysz stanowisko: **{target_pos}**")

        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            s_start = st.time_input("Start", time(16,0))
            s_end = st.time_input("Koniec", time(22,0))
            needed = st.number_input("Ile osób?", 1, 5, 1)
        
        with c2:
            st.subheader("Kandydaci")
            
            # FILTROWANIE INTELIGENTNE
            candidates = pd.DataFrame()
            
            if shift_type == "Standardowa" or shift_type == "Zadanie Specjalne":
                # Szukamy po prostu czy ma rolę na liście
                candidates = st.session_state.employees[
                    st.session_state.employees['Role'].apply(lambda x: target_pos in x)
                ]
            elif shift_type == "Hybryda (Combo)":
                # Używamy naszej funkcji do sprawdzania obu części
                candidates = st.session_state.employees[
                    st.session_state.employees['Role'].apply(lambda roles: can_employee_do_combo(roles, target_pos))
                ]

            available = candidates['Imie'].tolist()
            
            if not available:
                st.error("❌ Brak pracowników z takimi kwalifikacjami!")
            else:
                selected = st.multiselect(f"Dostępni ({len(available)}):", available, max_selections=needed)
                if st.button("✅ PRZYDZIEL ZMIANĘ"):
                    for worker in selected:
                        w_id = candidates[candidates['Imie'] == worker].iloc[0]['ID']
                        new_s = {
                            "Data": target_date, "Stanowisko": target_pos,
                            "Godziny": f"{s_start.strftime('%H:%M')}-{s_end.strftime('%H:%M')}",
                            "Pracownik_ID": w_id, "Pracownik_Imie": worker, "Typ": shift_type
                        }
                        st.session_state.shifts.loc[len(st.session_state.shifts)] = new_s
                    st.success("Zapisano!")

    # --- 3. WIDOK GRAFIKU ---
    elif page_hr == "3. Widok Grafiku":
        st.title("📋 Grafik")
        v_date = st.date_input("Data:", datetime.now())
        day_s = st.session_state.shifts[st.session_state.shifts['Data'] == v_date]
        
        if not day_s.empty:
            # Kolorowanie wierszy (hack CSS w dataframe)
            def highlight_rows(row):
                if "Hybryda" in row['Typ']: return ['background-color: #3b1c1c'] * len(row) # Ciemna czerwień
                if "Specjalne" in row['Typ']: return ['background-color: #1c3b2a'] * len(row) # Ciemna zieleń
                return [''] * len(row)

            st.dataframe(day_s[["Stanowisko", "Godziny", "Pracownik_Imie", "Typ"]].style.apply(highlight_rows, axis=1), use_container_width=True)
            
            if st.button("🖨️ PDF"):
                pdf_bytes = generate_schedule_pdf(day_s, str(v_date))
                st.download_button("Pobierz", pdf_bytes, "grafik.pdf", "application/pdf")
        else:
            st.info("Pusto.")

# --- ANALITYKA ---
elif app_mode == "📊 ANALITYKA":
    st.title("Finanse")
    st.info("Moduł finansowy z wersji v8.0")
