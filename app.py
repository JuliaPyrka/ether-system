import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | GRID MASTER", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    .avail-input { background-color: #262626; color: white; border: 1px solid #444; border-radius: 4px; padding: 5px; width: 100%; }
    .worker-row { border-bottom: 1px solid #333; padding: 5px 0; }
    /* Ukrywamy nagłówki w edytorze dyspozycyjności żeby było gęściej */
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

# --- PAMIĘĆ SESJI ---
if 'employees' not in st.session_state:
    # Pełna lista z Twojego zdjęcia
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

# Baza dyspozycyjności (GRID)
# Struktura: Klucz to "IMIE_DATA" (np. "Julia Bąk_2024-11-14"), Wartość to string (np. "16-1")
if 'avail_grid' not in st.session_state:
    st.session_state.avail_grid = {}

# ==========================================
# LOGIN
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
# PRACOWNIK
# ==========================================
if st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        menu = st.radio("Menu:", ["📅 Mój Grafik"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()
    
    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        my = st.session_state.shifts[st.session_state.shifts['Pracownik_Imie'] == st.session_state.user_name]
        if not my.empty: st.dataframe(my, use_container_width=True)
        else: st.info("Brak zmian.")

# ==========================================
# MENEDŻER
# ==========================================
elif st.session_state.user_role == "manager":
    with st.sidebar:
        st.title("🔧 PANEL KIEROWNIKA")
        menu = st.radio("Zarządzanie:", ["Kadry", "📥 Dyspozycje (Kartka)", "🗓️ Planer", "📋 Grafik"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # 1. KADRY (Uproszczone dla czytelności)
    if menu == "Kadry":
        st.title("📇 Lista Załogi")
        with st.expander("➕ Zatrudnij"):
            with st.form("new"):
                n = st.text_input("Imię")
                r = st.multiselect("Role", SKILLS_LIST)
                if st.form_submit_button("Dodaj"):
                    st.session_state.employees.loc[len(st.session_state.employees)] = {
                        "ID": len(st.session_state.employees)+1, "Imie": n, "Role": r, "Auto": calculate_auto_roles(r), "Start": time(8,0), "End": time(23,0)
                    }
                    st.rerun()
        
        st.dataframe(st.session_state.employees[["Imie", "Role"]])

    # 2. DYSPOZYCJE (GRID MASTER)
    elif menu == "📥 Dyspozycje (Kartka)":
        st.title("📥 Cyfryzacja Kartki")
        st.info("Przepisz godziny z kartki papieru. System zapamięta to automatycznie.")
        
        # Wybór tygodnia
        d_start = st.date_input("Początek tygodnia (np. Piątek 14.11):", datetime(2025, 11, 14))
        days = [d_start + timedelta(days=i) for i in range(7)]
        day_names = ["Pt", "Sb", "Nd", "Pn", "Wt", "Śr", "Cz"]
        
        # BUDOWANIE TABELI (FORMULARZ)
        with st.form("grid_form"):
            # Nagłówki
            cols = st.columns([2] + [1]*7)
            cols[0].write("**Pracownik**")
            for i, d in enumerate(days):
                cols[i+1].write(f"**{day_names[i]}** {d.strftime('%d.%m')}")
            
            st.divider()
            
            # Wiersze pracowników
            for idx, emp in st.session_state.employees.iterrows():
                row_cols = st.columns([2] + [1]*7)
                row_cols[0].write(f"👤 {emp['Imie']}")
                
                for i, d in enumerate(days):
                    key = f"{emp['Imie']}_{d.strftime('%Y-%m-%d')}"
                    val = st.session_state.avail_grid.get(key, "")
                    # Input box
                    new_val = row_cols[i+1].text_input(label="h", value=val, key=f"in_{key}", label_visibility="collapsed")
                    st.session_state.avail_grid[key] = new_val
            
            st.form_submit_button("💾 ZAPISZ DYSPOZYCJE (Samo się zapisuje, ale kliknij dla pewności)")

    # 3. PLANER (INTELIGENTNY)
    elif menu == "🗓️ Planer":
        st.title("🗓️ Planowanie")
        
        c_date, c_pos = st.columns(2)
        target_date = c_date.date_input("Dzień", datetime(2025, 11, 14))
        target_pos = c_pos.selectbox("Stanowisko", SCHEDULE_POSITIONS)
        
        with st.form("shift_form"):
            hours = st.text_input("Godziny", "16-1")
            
            # FILTROWANIE Z PODGLĄDEM DYSPOZYCJI
            candidates_df = st.session_state.employees[st.session_state.employees['Role'].apply(lambda x: "Bar" in x)] # Uproszczone filtrowanie dla demo
            
            candidate_names = []
            for name in candidates_df['Imie']:
                # Sprawdzamy dyspozycję w Gridzie
                key = f"{name}_{target_date.strftime('%Y-%m-%d')}"
                avail = st.session_state.avail_grid.get(key, "")
                
                if avail and avail != "-":
                    candidate_names.append(f"{name} (Dostępny: {avail})")
                else:
                    # Jeśli nie ma wpisu lub kreska, oznaczamy jako niedostępny (opcjonalnie można ukryć)
                    candidate_names.append(f"{name} [BRAK DANYCH/NIEDOSTĘPNY]")

            selected = st.multiselect("Wybierz ludzi:", candidate_names)
            
            if st.form_submit_button("Zapisz"):
                for s in selected:
                    clean_name = s.split(" (")[0].split(" [")[0] # Wyciągamy czyste imię
                    st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                        "Data": target_date, "Stanowisko": target_pos, "Godziny": hours, "Pracownik_Imie": clean_name, "Typ": "Standard"
                    }
                st.success("Dodano!")

    # 4. GRAFIK
    elif menu == "📋 Grafik":
        st.title("📋 Podgląd")
        d = st.date_input("Od", datetime(2025, 11, 14))
        mask = (st.session_state.shifts['Data'] >= d) & (st.session_state.shifts['Data'] <= d + timedelta(days=6))
        df = st.session_state.shifts.loc[mask]
        if not df.empty:
            df['I'] = df['Godziny'] + "\n" + df['Pracownik_Imie']
            mx = df.pivot_table(index='Stanowisko', columns='Data', values='I', aggfunc=lambda x: "\n".join(x)).fillna("-")
            st.dataframe(mx, use_container_width=True, height=600)
        else: st.info("Pusto.")
