import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | HR MASTER", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    .combo-role { color: #fca5a5 !important; font-weight: bold; }
    .task-role { color: #86efac !important; font-style: italic; }
    /* Stylizacja Tabeli Grafiku */
    thead tr th:first-child { display:none }
    tbody th { display:none }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA DANYCH ---
USERS = {"admin": "AlastorRules", "kino": "film123", "demo": "demo"}

# ROLE (Zaktualizowane o Inwentaryzację itp.)
BASIC_ROLES = ["Obsługa", "Kasa", "Bar 1", "Bar 2", "Cafe", "Pomoc Bar", "Pomoc Obsługa"]
SPECIAL_TASKS = ["Plakaty (Techniczne)", "Inwentaryzacja", "Sprzątanie Generalne"]
ALL_SKILLS = BASIC_ROLES + SPECIAL_TASKS

# --- PAMIĘĆ SESJI ---
if 'employees' not in st.session_state:
    # Startowa baza pracowników
    st.session_state.employees = pd.DataFrame([
        {"ID": 1, "Imie": "Anna Kowalska", "Role": ["Kasa", "Cafe", "Inwentaryzacja"], "Start": time(8,0), "End": time(16,0)},
        {"ID": 2, "Imie": "Tomek Nowak", "Role": ["Obsługa", "Bar 1", "Bar 2", "Plakaty (Techniczne)"], "Start": time(16,0), "End": time(23,0)},
        {"ID": 3, "Imie": "Julia Manager", "Role": ALL_SKILLS, "Start": time(9,0), "End": time(22,0)},
        {"ID": 4, "Imie": "Wojcieszek Maria", "Role": ["Bar 1", "Bar 2", "Cafe"], "Start": time(8,0), "End": time(20,0)},
        {"ID": 5, "Imie": "Bak Julia", "Role": ["Bar 1", "Cafe"], "Start": time(15,0), "End": time(0,0)}
    ])

if 'shifts' not in st.session_state:
    st.session_state.shifts = pd.DataFrame([
        {"Data": datetime.now().date(), "Stanowisko": "Kasa", "Godziny": "09:00-16:00", "Pracownik_Imie": "Anna Kowalska", "Typ": "Standardowa"},
        {"Data": datetime.now().date(), "Stanowisko": "Bar 1 + Cafe", "Godziny": "08:45-15:45", "Pracownik_Imie": "Wojcieszek Maria", "Typ": "Hybryda (Combo)"},
    ])

# --- FUNKCJE ---
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
    pdf.cell(0, 10, clean_text(f"GRAFIK TYGODNIOWY - HELIOS"), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 8)
    for index, row in df_shifts.sort_values(by=["Data", "Stanowisko"]).iterrows():
        line = f"{row['Data']} | {row['Stanowisko']} | {row['Godziny']} | {row['Pracownik_Imie']}"
        pdf.cell(0, 8, clean_text(line), ln=True, border=1)
    return pdf.output(dest='S').encode('latin-1')

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
        page_hr = st.radio("Moduł HR:", ["1. Baza Pracowników (Edycja)", "2. Planowanie Zmian", "3. Widok Grafiku (Matrix)"])
    st.divider()
    if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

if app_mode == "👥 GRAFIK (HR)":
    
    # --- 1. BAZA PRACOWNIKÓW (EDYCJA) ---
    if page_hr == "1. Baza Pracowników (Edycja)":
        st.title("📇 Zarządzanie Kadrami")
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.subheader("🛠️ Panel Menedżera")
            
            # Wybór: Dodaj nowego CZY Edytuj istniejącego
            options = ["-- DODAJ NOWEGO --"] + st.session_state.employees['Imie'].tolist()
            selected_employee = st.selectbox("Wybierz osobę do edycji:", options)
            
            # Zmienne formularza (domyślne puste)
            f_name = ""
            f_roles = []
            f_start = time(8,0)
            f_end = time(22,0)
            emp_index = None # Żeby wiedzieć kogo nadpisać

            if selected_employee != "-- DODAJ NOWEGO --":
                # Pobieramy dane wybranej osoby
                emp_data = st.session_state.employees[st.session_state.employees['Imie'] == selected_employee].iloc[0]
                emp_index = st.session_state.employees[st.session_state.employees['Imie'] == selected_employee].index[0]
                
                f_name = emp_data['Imie']
                f_roles = emp_data['Role']
                f_start = emp_data['Start']
                f_end = emp_data['End']
                
                st.info(f"Edytujesz: **{f_name}**")
            else:
                st.info("Tworzysz nowego pracownika.")

            # Formularz (wspólny dla dodawania i edycji)
            with st.form("employee_form"):
                new_name = st.text_input("Imię i Nazwisko", value=f_name)
                new_roles = st.multiselect("Umiejętności / Uprawnienia:", ALL_SKILLS, default=f_roles)
                c_t1, c_t2 = st.columns(2)
                new_start = c_t1.time_input("Dostępny Od:", value=f_start)
                new_end = c_t2.time_input("Dostępny Do:", value=f_end)
                
                # Przyciski
                col_save, col_del = st.columns(2)
                
                saved = col_save.form_submit_button("💾 ZAPISZ DANE")
                deleted = False
                
                # Przycisk usuwania (tylko jeśli edytujemy)
                if selected_employee != "-- DODAJ NOWEGO --":
                    deleted = col_del.form_submit_button("🗑️ USUŃ OSOBĘ", type="primary")

                if saved:
                    if selected_employee == "-- DODAJ NOWEGO --":
                        # Dodajemy nowego
                        new_id = len(st.session_state.employees) + 10 # +10 żeby się ID nie dublowały
                        st.session_state.employees.loc[len(st.session_state.employees)] = {
                            "ID": new_id, "Imie": new_name, "Role": new_roles, "Start": new_start, "End": new_end
                        }
                        st.success(f"Zatrudniono: {new_name}")
                    else:
                        # Aktualizujemy istniejącego
                        st.session_state.employees.at[emp_index, 'Imie'] = new_name
                        st.session_state.employees.at[emp_index, 'Role'] = new_roles
                        st.session_state.employees.at[emp_index, 'Start'] = new_start
                        st.session_state.employees.at[emp_index, 'End'] = new_end
                        st.success(f"Zaktualizowano dane: {new_name}")
                    st.rerun()

                if deleted:
                    # Usuwamy
                    st.session_state.employees = st.session_state.employees.drop(emp_index).reset_index(drop=True)
                    st.warning(f"Usunięto pracownika: {f_name}")
                    st.rerun()

        with c2:
            st.subheader("Aktualna Załoga")
            # Ładniejszy podgląd z rolami jako tekst
            view_df = st.session_state.employees.copy()
            view_df['Umiejętności'] = view_df['Role'].apply(lambda x: ", ".join(x))
            st.dataframe(
                view_df[["Imie", "Umiejętności", "Start", "End"]], 
                use_container_width=True, 
                height=500,
                hide_index=True
            )

    # --- 2. PLANOWANIE ZMIAN (Bez zmian, działa dobrze) ---
    elif page_hr == "2. Planowanie Zmian":
        st.title("🗓️ Planer")
        
        c_date, c_type = st.columns(2)
        target_date = c_date.date_input("Dzień", datetime.now())
        shift_type = c_type.selectbox("Typ:", ["Standard", "BAR + CAFE (Combo)", "Inwentaryzacja/Zadania"])
        
        target_pos = None
        if shift_type == "Standard": target_pos = st.selectbox("Stanowisko", BASIC_ROLES)
        elif shift_type == "Inwentaryzacja/Zadania": target_pos = st.selectbox("Zadanie", SPECIAL_TASKS)
        elif shift_type == "BAR + CAFE (Combo)": target_pos = "Bar 1 + Cafe"

        c1, c2 = st.columns(2)
        with c1:
            hours_str = st.text_input("Godziny (np. 15:45-00:00)", "08:30-16:00")
            needed = st.number_input("Ile osób?", 1, 10, 1)
        
        with c2:
            st.subheader("Dostępni:")
            candidates = pd.DataFrame()
            if shift_type == "BAR + CAFE (Combo)":
                candidates = st.session_state.employees[
                    st.session_state.employees['Role'].apply(lambda x: "Bar 1" in x and "Cafe" in x)
                ]
            else:
                candidates = st.session_state.employees[
                    st.session_state.employees['Role'].apply(lambda x: target_pos in x)
                ]

            available = candidates['Imie'].tolist()
            if not available: st.error("Brak ludzi z takimi uprawnieniami!")
            else:
                selected = st.multiselect("Wybierz:", available, max_selections=needed)
                if st.button("ZATWIERDŹ"):
                    for worker in selected:
                        st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                            "Data": target_date, "Stanowisko": target_pos,
                            "Godziny": hours_str,
                            "Pracownik_Imie": worker, "Typ": shift_type
                        }
                    st.success("Zapisano!")

    # --- 3. MATRIX GRAFIKU ---
    elif page_hr == "3. Widok Grafiku (Matrix)":
        st.title("📋 Grafik Tygodniowy")
        d_start = st.date_input("Od dnia:", datetime.now())
        d_end = d_start + timedelta(days=6)
        
        mask = (st.session_state.shifts['Data'] >= d_start) & (st.session_state.shifts['Data'] <= d_end)
        df_view = st.session_state.shifts.loc[mask]
        
        if not df_view.empty:
            df_view['Info'] = df_view['Godziny'] + "\n" + df_view['Pracownik_Imie']
            schedule_matrix = df_view.pivot_table(
                index='Stanowisko', columns='Data', values='Info', 
                aggfunc=lambda x: "\n---\n".join(x)
            ).fillna("-")
            st.dataframe(schedule_matrix, use_container_width=True, height=600)
            if st.button("Pobierz PDF"):
                pdf_bytes = generate_schedule_pdf(df_view, f"{d_start} - {d_end}")
                st.download_button("Pobierz", pdf_bytes, "grafik.pdf", "application/pdf")
        else:
            st.info("Brak zmian w tym tygodniu.")

elif app_mode == "📊 ANALITYKA":
    st.title("Finanse")
    st.info("System finansowy aktywny.")
