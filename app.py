import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | DUAL CORE", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    .worker-card { border: 1px solid #3b82f6; padding: 10px; border-radius: 5px; margin: 5px 0; }
    .manager-header { color: #fca5a5 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA UŻYTKOWNIKÓW (ROLA: manager / worker) ---
USERS = {
    "admin":  {"pass": "AlastorRules", "role": "manager", "name": "Szef Wszystkich Szefów"},
    "kierownik": {"pass": "film123", "role": "manager", "name": "Główny Kierownik"},
    "ania":   {"pass": "ania1", "role": "worker", "name": "Anna Kowalska"},
    "tomek":  {"pass": "tomek1", "role": "worker", "name": "Tomek Nowak"},
    "julia":  {"pass": "julia1", "role": "worker", "name": "Bak Julia"} 
}

# --- SŁOWNIKI ---
BASIC_ROLES = ["Obsługa", "Kasa", "Bar 1", "Bar 2", "Cafe", "Pomoc Bar", "Pomoc Obsługa"]
SPECIAL_TASKS = ["Plakaty (Techniczne)", "Inwentaryzacja", "Sprzątanie Generalne"]
ALL_SKILLS = BASIC_ROLES + SPECIAL_TASKS

# --- PAMIĘĆ SESJI ---
if 'employees' not in st.session_state:
    st.session_state.employees = pd.DataFrame([
        {"ID": 1, "Imie": "Anna Kowalska", "Role": ["Kasa", "Cafe"], "Start": time(8,0), "End": time(16,0)},
        {"ID": 2, "Imie": "Tomek Nowak", "Role": ["Obsługa", "Bar 1", "Bar 2", "Plakaty (Techniczne)"], "Start": time(16,0), "End": time(23,0)},
        {"ID": 3, "Imie": "Bak Julia", "Role": ["Bar 1", "Cafe"], "Start": time(15,0), "End": time(0,0)}
    ])

if 'shifts' not in st.session_state:
    st.session_state.shifts = pd.DataFrame([
        {"Data": datetime.now().date(), "Stanowisko": "Kasa", "Godziny": "09:00-16:00", "Pracownik_Imie": "Anna Kowalska", "Typ": "Standardowa", "Status": "Zatwierdzone"},
        {"Data": datetime.now().date(), "Stanowisko": "Obsługa", "Godziny": "16:00-23:00", "Pracownik_Imie": "Tomek Nowak", "Typ": "Standardowa", "Status": "Zatwierdzone"},
    ])

# Nowość: Giełda Zamian i Dyspozycyjność
if 'market' not in st.session_state:
    st.session_state.market = pd.DataFrame(columns=["Data", "Stanowisko", "Godziny", "Kto_Oddaje", "Komentarz"])

if 'availability' not in st.session_state:
    st.session_state.availability = pd.DataFrame(columns=["Pracownik", "Data_Od", "Data_Do", "Godziny_Pref"])

# --- FUNKCJE ---
def check_login(u, p):
    if u in USERS and USERS[u]["pass"] == p:
        return USERS[u]
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

# ==========================================
# EKRAN LOGOWANIA
# ==========================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #d93025;'>ETHER SYSTEM</h1>", unsafe_allow_html=True)
        st.info("Loginy testowe: 'admin' (szef), 'ania' (pracownik)")
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
            else:
                st.error("Błędne dane.")
    st.stop()

# ==========================================
# ROZDZIELENIE WIDOKÓW
# ==========================================

# ------------------------------------------
# WIDOK 1: PRACOWNIK (Worker)
# ------------------------------------------
if st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 Cześć, {st.session_state.user_name.split()[0]}")
        st.caption("Panel Pracownika")
        st.divider()
        menu = st.radio("Menu:", ["📅 Mój Grafik", "🙋 Zgłoś Dyspozycyjność", "🔄 Giełda Zamian"])
        st.divider()
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        # Filtrujemy zmiany TYLKO dla zalogowanego
        my_shifts = st.session_state.shifts[st.session_state.shifts['Pracownik_Imie'] == st.session_state.user_name]
        
        if not my_shifts.empty:
            st.dataframe(my_shifts[["Data", "Stanowisko", "Godziny", "Typ"]], use_container_width=True)
            
            st.subheader("Oddaj zmianę")
            shift_to_give = st.selectbox("Wybierz zmianę, której nie możesz wziąć:", my_shifts['Data'].astype(str) + " | " + my_shifts['Stanowisko'])
            reason = st.text_input("Powód (opcjonalnie):", placeholder="np. wizyta u lekarza")
            
            if st.button("Wystaw na Giełdę Zamian"):
                # Parsowanie wyboru
                selected_data = shift_to_give.split(" | ")[0]
                selected_pos = shift_to_give.split(" | ")[1]
                selected_shift = my_shifts[(my_shifts['Data'].astype(str) == selected_data) & (my_shifts['Stanowisko'] == selected_pos)].iloc[0]
                
                # Dodanie do giełdy
                st.session_state.market.loc[len(st.session_state.market)] = {
                    "Data": selected_shift['Data'],
                    "Stanowisko": selected_shift['Stanowisko'],
                    "Godziny": selected_shift['Godziny'],
                    "Kto_Oddaje": st.session_state.user_name,
                    "Komentarz": reason
                }
                st.success("Zmiana wystawiona! Czekaj aż ktoś ją weźmie.")
        else:
            st.info("Nie masz zaplanowanych zmian w najbliższym czasie.")

    elif menu == "🙋 Zgłoś Dyspozycyjność":
        st.title("Kiedy możesz pracować?")
        with st.form("avail_form"):
            d_start = st.date_input("Od dnia")
            d_end = st.date_input("Do dnia")
            pref_hours = st.text_input("Preferowane godziny (np. 'Po 16:00', 'Cały dzień')")
            if st.form_submit_button("Wyślij do Kierownika"):
                st.session_state.availability.loc[len(st.session_state.availability)] = {
                    "Pracownik": st.session_state.user_name,
                    "Data_Od": d_start, "Data_Do": d_end, "Godziny_Pref": pref_hours
                }
                st.success("Zgłoszenie wysłane!")

    elif menu == "🔄 Giełda Zamian":
        st.title("Giełda Zamian")
        st.markdown("Tutaj lądują zmiany, których inni nie mogą wziąć. **Kliknij 'Biorę', aby przejąć zmianę.**")
        
        if not st.session_state.market.empty:
            for idx, row in st.session_state.market.iterrows():
                # Nie pokazuj moich własnych zmian
                if row['Kto_Oddaje'] != st.session_state.user_name:
                    with st.container():
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.warning(f"📅 {row['Data']} | {row['Stanowisko']} ({row['Godziny']})\nOd: {row['Kto_Oddaje']} ({row['Komentarz']})")
                        if c3.button("🙋 BIORĘ TO", key=f"take_{idx}"):
                            # 1. Dodaj zmianę nowemu pracownikowi w grafiku
                            st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                                "Data": row['Data'], "Stanowisko": row['Stanowisko'],
                                "Godziny": row['Godziny'], "Pracownik_Imie": st.session_state.user_name, # Nowy właściciel
                                "Typ": "Przejęta", "Status": "Zatwierdzone"
                            }
                            # 2. Usuń zmianę staremu pracownikowi z grafiku
                            # (To uproszczona logika - w prawdziwym DB usuwamy po ID)
                            mask = (st.session_state.shifts['Data'] == row['Data']) & \
                                   (st.session_state.shifts['Stanowisko'] == row['Stanowisko']) & \
                                   (st.session_state.shifts['Pracownik_Imie'] == row['Kto_Oddaje'])
                            st.session_state.shifts = st.session_state.shifts[~mask]
                            
                            # 3. Usuń z giełdy
                            st.session_state.market = st.session_state.market.drop(idx)
                            st.success("Przejęto zmianę! Grafik zaktualizowany.")
                            st.rerun()
        else:
            st.info("Giełda jest pusta. Wszyscy pracują :)")

# ------------------------------------------
# WIDOK 2: MENEDŻER (Manager)
# ------------------------------------------
elif st.session_state.user_role == "manager":
    with st.sidebar:
        st.title("🔧 PANEL KIEROWNIKA")
        st.divider()
        menu = st.radio("Zarządzanie:", ["Kadry (Dodaj/Usuń)", "Planowanie Grafiku", "Podgląd Grafiku", "Zgłoszenia Pracowników"])
        st.divider()
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    if menu == "Kadry (Dodaj/Usuń)":
        st.title("📇 Zarządzanie Kadrami")
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.subheader("Edytor")
            # Lista rozwijana do wyboru (z opcją Dodaj Nowego)
            options = ["-- DODAJ NOWEGO --"] + st.session_state.employees['Imie'].tolist()
            selected = st.selectbox("Wybierz osobę:", options)
            
            # Wypełnianie pól w zależności od wyboru
            default_name = ""
            default_roles = []
            
            if selected != "-- DODAJ NOWEGO --":
                emp_data = st.session_state.employees[st.session_state.employees['Imie'] == selected].iloc[0]
                default_name = emp_data['Imie']
                default_roles = emp_data['Role']
            
            with st.form("hr_form"):
                f_name = st.text_input("Imię i Nazwisko", value=default_name)
                f_roles = st.multiselect("Uprawnienia", ALL_SKILLS, default=default_roles)
                
                col_save, col_del = st.columns(2)
                saved = col_save.form_submit_button("💾 ZAPISZ")
                deleted = False
                if selected != "-- DODAJ NOWEGO --":
                    deleted = col_del.form_submit_button("🗑️ USUŃ", type="primary") # Ten guzik widać tylko przy edycji
                
                if saved:
                    if selected == "-- DODAJ NOWEGO --":
                        new_id = len(st.session_state.employees) + 10
                        st.session_state.employees.loc[len(st.session_state.employees)] = {
                            "ID": new_id, "Imie": f_name, "Role": f_roles, "Start": time(8,0), "End": time(22,0)
                        }
                        st.success("Dodano!")
                    else:
                        # Aktualizacja (uproszczona po imieniu)
                        idx = st.session_state.employees[st.session_state.employees['Imie'] == selected].index[0]
                        st.session_state.employees.at[idx, 'Imie'] = f_name
                        st.session_state.employees.at[idx, 'Role'] = f_roles
                        st.success("Zaktualizowano!")
                    st.rerun()
                
                if deleted:
                    idx = st.session_state.employees[st.session_state.employees['Imie'] == selected].index[0]
                    st.session_state.employees = st.session_state.employees.drop(idx).reset_index(drop=True)
                    st.warning("Pracownik usunięty.")
                    st.rerun()

        with c2:
            st.subheader("Baza")
            st.dataframe(st.session_state.employees[["Imie", "Role"]], use_container_width=True)

    elif menu == "Planowanie Grafiku":
        st.title("🗓️ Planer")
        # --- Tu wklejamy logikę planowania z v11.0 ---
        c_date, c_type = st.columns(2)
        target_date = c_date.date_input("Dzień", datetime.now())
        shift_type = c_type.selectbox("Typ:", ["Standard", "BAR + CAFE (Combo)", "Inwentaryzacja/Zadania"])
        
        target_pos = None
        if shift_type == "Standard": target_pos = st.selectbox("Stanowisko", BASIC_ROLES)
        elif shift_type == "Inwentaryzacja/Zadania": target_pos = st.selectbox("Zadanie", SPECIAL_TASKS)
        elif shift_type == "BAR + CAFE (Combo)": target_pos = "Bar 1 + Cafe"

        candidates = pd.DataFrame()
        if shift_type == "BAR + CAFE (Combo)":
            candidates = st.session_state.employees[st.session_state.employees['Role'].apply(lambda x: "Bar 1" in x and "Cafe" in x)]
        else:
            candidates = st.session_state.employees[st.session_state.employees['Role'].apply(lambda x: target_pos in x)]

        with st.form("shift_maker"):
            hours_str = st.text_input("Godziny", "16:00-22:00")
            selected = st.multiselect("Wybierz pracowników:", candidates['Imie'].tolist())
            if st.form_submit_button("Dodaj do Grafiku"):
                for worker in selected:
                    st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                        "Data": target_date, "Stanowisko": target_pos, "Godziny": hours_str,
                        "Pracownik_Imie": worker, "Typ": shift_type, "Status": "Zatwierdzone"
                    }
                st.success("Gotowe")

    elif menu == "Podgląd Grafiku":
        st.title("📋 Grafik Całościowy")
        # Logika Matrix z v11.0
        d_start = st.date_input("Od dnia:", datetime.now())
        d_end = d_start + timedelta(days=6)
        mask = (st.session_state.shifts['Data'] >= d_start) & (st.session_state.shifts['Data'] <= d_end)
        df_view = st.session_state.shifts.loc[mask]
        
        if not df_view.empty:
            df_view['Info'] = df_view['Godziny'] + "\n" + df_view['Pracownik_Imie']
            matrix = df_view.pivot_table(index='Stanowisko', columns='Data', values='Info', aggfunc=lambda x: "\n---\n".join(x)).fillna("-")
            st.dataframe(matrix, use_container_width=True, height=600)
        else:
            st.info("Pusto.")

    elif menu == "Zgłoszenia Pracowników":
        st.title("📬 Skrzynka Odbiorcza")
        
        st.subheader("Dyspozycyjność (Kto kiedy chce pracować)")
        if not st.session_state.availability.empty:
            st.dataframe(st.session_state.availability, use_container_width=True)
        else:
            st.caption("Brak nowych zgłoszeń.")
            
        st.subheader("Aktywne Zamiany (Giełda)")
        if not st.session_state.market.empty:
            st.dataframe(st.session_state.market, use_container_width=True)
        else:
            st.caption("Nikt nie chce się zamieniać.")
