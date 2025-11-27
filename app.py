import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, time, timedelta

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | AUTOMATOR", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    .worker-row { 
        background-color: #1f2937; 
        padding: 10px; 
        border-radius: 5px; 
        margin-bottom: 8px; 
        border-left: 4px solid #3b82f6;
    }
    .auto-role { color: #86efac; font-size: 0.8em; font-style: italic; }
    /* Ukrywanie indeksów tabeli */
    thead tr th:first-child { display:none }
    tbody th { display:none }
    </style>
    """, unsafe_allow_html=True)

# --- BAZA UŻYTKOWNIKÓW ---
USERS = {
    "admin":  {"pass": "AlastorRules", "role": "manager", "name": "Szef"},
    "kierownik": {"pass": "film123", "role": "manager", "name": "Kierownik"},
    "julia":  {"pass": "julia1", "role": "worker", "name": "Julia Bąk"},
}

# --- SŁOWNIKI ---
# SKILLS_LIST: To co wybierasz przy pracowniku
SKILLS_LIST = ["Bar", "Cafe", "Obsługa", "Kasa", "Plakaty (Techniczne)"]

# SCHEDULE_POSITIONS: To co wybierasz w grafiku
SCHEDULE_POSITIONS = ["Bar 1", "Bar 2", "Cafe", "Obsługa", "Kasa", "Plakaty", "Inwentaryzacja", "Pomoc Bar", "Pomoc Obsługa", "Sprzątanie Generalne"]

# --- FUNKCJA LOGICZNA (AUTOMATYZACJA) ---
def calculate_auto_roles(selected_roles):
    """
    Twoje zasady biznesowe:
    1. Każdy -> Sprzątanie Generalne
    2. Ma Bar -> Inwentaryzacja
    3. Ma Bar ORAZ Obsługę -> Pomoc Bar, Pomoc Obsługa
    """
    auto = ["Sprzątanie Generalne"]
    
    has_bar = "Bar" in selected_roles
    has_obs = "Obsługa" in selected_roles
    
    if has_bar:
        auto.append("Inwentaryzacja")
        
    if has_bar and has_obs:
        auto.append("Pomoc Bar")
        auto.append("Pomoc Obsługa")
        
    return list(set(auto)) # Usuwamy duplikaty

# --- PAMIĘĆ SESJI ---
if 'employees' not in st.session_state:
    # Baza wypełniona danymi z Twojego zdjęcia
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
    
    # Tworzymy DataFrame i obliczamy role automatyczne
    rows = []
    for i, person in enumerate(data):
        rows.append({
            "ID": i + 1,
            "Imie": person["Imie"],
            "Role": person["Role"],
            "Auto": calculate_auto_roles(person["Role"]),
            "Start": time(8,0),
            "End": time(23,0)
        })
    st.session_state.employees = pd.DataFrame(rows)

if 'shifts' not in st.session_state:
    st.session_state.shifts = pd.DataFrame([
        {"Data": datetime.now().date(), "Stanowisko": "Kasa", "Godziny": "09:00-16:00", "Pracownik_Imie": "Julia Pyrka", "Typ": "Standardowa"},
    ])

if 'market' not in st.session_state: st.session_state.market = pd.DataFrame(columns=["Data", "Stanowisko", "Godziny", "Kto_Oddaje", "Komentarz"])
if 'availability' not in st.session_state: st.session_state.availability = pd.DataFrame(columns=["Pracownik", "Data_Od", "Data_Do", "Godziny_Pref"])

# --- FUNKCJE POMOCNICZE ---
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

# ==========================================
# EKRAN LOGOWANIA
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
# WIDOK 1: PRACOWNIK
# ==========================================
if st.session_state.user_role == "worker":
    with st.sidebar:
        st.title(f"👋 {st.session_state.user_name}")
        menu = st.radio("Menu:", ["📅 Mój Grafik", "🙋 Zgłoś Dyspozycyjność", "🔄 Giełda Zamian"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    if menu == "📅 Mój Grafik":
        st.title("Mój Grafik")
        my_shifts = st.session_state.shifts[st.session_state.shifts['Pracownik_Imie'] == st.session_state.user_name]
        if not my_shifts.empty:
            st.dataframe(my_shifts[["Data", "Stanowisko", "Godziny", "Typ"]], use_container_width=True)
            shift_to_give = st.selectbox("Oddaj zmianę:", my_shifts['Data'].astype(str) + " | " + my_shifts['Stanowisko'])
            if st.button("Wystaw na Giełdę"):
                sel_d, sel_p = shift_to_give.split(" | ")
                sel_s = my_shifts[(my_shifts['Data'].astype(str)==sel_d)&(my_shifts['Stanowisko']==sel_p)].iloc[0]
                st.session_state.market.loc[len(st.session_state.market)] = {
                    "Data": sel_s['Data'], "Stanowisko": sel_s['Stanowisko'], "Godziny": sel_s['Godziny'],
                    "Kto_Oddaje": st.session_state.user_name, "Komentarz": "Prośba o zastępstwo"
                }
                st.success("Wystawiono!")
        else: st.info("Brak zmian.")
    
    elif menu == "🙋 Zgłoś Dyspozycyjność":
        st.title("Dyspozycyjność")
        with st.form("avail"):
            d_start = st.date_input("Od")
            d_end = st.date_input("Do")
            pref = st.text_input("Preferencje (np. tylko rano)")
            if st.form_submit_button("Wyślij"):
                st.session_state.availability.loc[len(st.session_state.availability)] = {
                    "Pracownik": st.session_state.user_name, "Data_Od": d_start, "Data_Do": d_end, "Godziny_Pref": pref
                }
                st.success("Wysłano!")

    elif menu == "🔄 Giełda Zamian":
        st.title("Giełda Zamian")
        if not st.session_state.market.empty:
            for idx, row in st.session_state.market.iterrows():
                if row['Kto_Oddaje'] != st.session_state.user_name:
                    c1, c2 = st.columns([3, 1])
                    c1.warning(f"{row['Data']} | {row['Stanowisko']} ({row['Godziny']}) od {row['Kto_Oddaje']}")
                    if c2.button("BIORĘ", key=f"take_{idx}"):
                        st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                            "Data": row['Data'], "Stanowisko": row['Stanowisko'], "Godziny": row['Godziny'],
                            "Pracownik_Imie": st.session_state.user_name, "Typ": "Przejęta"
                        }
                        mask = (st.session_state.shifts['Data']==row['Data'])&(st.session_state.shifts['Stanowisko']==row['Stanowisko'])&(st.session_state.shifts['Pracownik_Imie']==row['Kto_Oddaje'])
                        st.session_state.shifts = st.session_state.shifts[~mask]
                        st.session_state.market = st.session_state.market.drop(idx)
                        st.rerun()
        else: st.info("Pusto.")

# ==========================================
# WIDOK 2: MENEDŻER
# ==========================================
elif st.session_state.user_role == "manager":
    with st.sidebar:
        st.title("🔧 PANEL KIEROWNIKA")
        menu = st.radio("Zarządzanie:", ["Kadry (Automator)", "Planowanie", "Podgląd Grafiku"])
        if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

    # --- 1. KADRY (AUTOMATOR) ---
    if menu == "Kadry (Automator)":
        st.title("📇 Zarządzanie Kadrami")
        
        # Sekcja Dodawania
        with st.expander("➕ ZATRUDNIJ PRACOWNIKA", expanded=False):
            with st.form("new_hire"):
                n_name = st.text_input("Imię i Nazwisko")
                n_roles = st.multiselect("Główne Umiejętności (Wybierz tylko podstawowe):", SKILLS_LIST)
                c1, c2 = st.columns(2)
                n_start = c1.time_input("Start", time(8,0))
                n_end = c2.time_input("Koniec", time(23,0))
                
                if st.form_submit_button("Zatrudnij"):
                    auto_roles = calculate_auto_roles(n_roles) # Automatyka
                    new_id = len(st.session_state.employees) + 1
                    st.session_state.employees.loc[len(st.session_state.employees)] = {
                        "ID": new_id, "Imie": n_name, "Role": n_roles, "Auto": auto_roles, "Start": n_start, "End": n_end
                    }
                    st.success(f"Dodano: {n_name}. Uprawnienia automatyczne przeliczone.")
                    st.rerun()

        st.divider()
        st.subheader("Obecny Skład")
        
        # LISTA Z PRZYCISKIEM USUWANIA
        for index, row in st.session_state.employees.iterrows():
            with st.container():
                # Używamy kolumn do układu: Dane | Przycisk Usuń
                c1, c2 = st.columns([5, 1])
                
                with c1:
                    st.markdown(f"""
                    <div class="worker-row">
                        <div>
                            <strong style="font-size:1.1em">{row['Imie']}</strong><br>
                            <span style="color:#ddd">Role: {', '.join(row['Role'])}</span><br>
                            <span class="auto-role">Auto: {', '.join(row['Auto'])}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with c2:
                    st.write("") # Odstęp
                    if st.button("🗑️ USUŃ", key=f"del_{row['ID']}"):
                        st.session_state.employees = st.session_state.employees[st.session_state.employees.ID != row['ID']].reset_index(drop=True)
                        st.rerun()

    # --- 2. PLANOWANIE ZMIAN ---
    elif menu == "Planowanie":
        st.title("🗓️ Planer")
        
        c_date, c_pos = st.columns(2)
        target_date = c_date.date_input("Dzień", datetime.now())
        target_pos = c_pos.selectbox("Stanowisko do obsadzenia:", SCHEDULE_POSITIONS + ["Bar 1 + Cafe (Combo)"])

        # Sprawdzanie czy to Sobota Plakatowa
        is_poster_saturday = (target_date.weekday() == 5) and (target_date.isocalendar()[1] % 2 == 0)
        if is_poster_saturday: st.info("ℹ️ Sobota Plakatowa!")

        with st.form("shift_form"):
            hours = st.text_input("Godziny", "16:00-23:00")
            needed = st.number_input("Ile osób?", 1, 5, 1)
            
            # LOGIKA FILTROWANIA KANDYDATÓW
            candidates = pd.DataFrame()
            
            # 1. Bar 1 lub Bar 2 -> Szukamy skill "Bar"
            if target_pos in ["Bar 1", "Bar 2"]:
                candidates = st.session_state.employees[st.session_state.employees['Role'].apply(lambda x: "Bar" in x)]
                
            # 2. Combo
            elif target_pos == "Bar 1 + Cafe (Combo)":
                candidates = st.session_state.employees[st.session_state.employees['Role'].apply(lambda x: "Bar" in x and "Cafe" in x)]
                
            # 3. Pomoc / Inwentaryzacja -> Sprawdzamy role AUTOMATYCZNE
            elif target_pos in ["Pomoc Bar", "Pomoc Obsługa", "Inwentaryzacja", "Sprzątanie Generalne"]:
                 candidates = st.session_state.employees[st.session_state.employees['Auto'].apply(lambda x: target_pos in x)]
            
            # 4. Reszta (Cafe, Kasa, Obsługa, Plakaty) -> Szukamy w rolach głównych
            else:
                target_skill = target_pos.replace(" (Techniczne)", "")
                candidates = st.session_state.employees[st.session_state.employees['Role'].apply(lambda x: target_skill in x)]

            available_names = candidates['Imie'].tolist()
            
            if not available_names:
                st.error("Brak pracowników z wymaganym uprawnieniem!")
                selected = []
            else:
                selected = st.multiselect("Kandydaci:", available_names)

            if st.form_submit_button("Zapisz w Grafiku"):
                for worker in selected:
                    st.session_state.shifts.loc[len(st.session_state.shifts)] = {
                        "Data": target_date, "Stanowisko": target_pos, "Godziny": hours,
                        "Pracownik_Imie": worker, "Typ": "Standard", "Status": "Zatwierdzone"
                    }
                st.success("Dodano!")

    # --- 3. WIDOK GRAFIKU (MATRIX) ---
    elif menu == "Podgląd Grafiku":
        st.title("📋 Grafik Tygodniowy")
        d_start = st.date_input("Od dnia:", datetime.now())
        d_end = d_start + timedelta(days=6)
        mask = (st.session_state.shifts['Data'] >= d_start) & (st.session_state.shifts['Data'] <= d_end)
        df_view = st.session_state.shifts.loc[mask]
        
        if not df_view.empty:
            df_view['Info'] = df_view['Godziny'] + "\n" + df_view['Pracownik_Imie']
            matrix = df_view.pivot_table(index='Stanowisko', columns='Data', values='Info', aggfunc=lambda x: "\n---\n".join(x)).fillna("-")
            st.dataframe(matrix, use_container_width=True, height=600)
            if st.button("PDF"):
                pdf_bytes = generate_schedule_pdf(df_view, f"{d_start} - {d_end}")
                st.download_button("Pobierz", pdf_bytes, "grafik.pdf", "application/pdf")
        else:
            st.info("Pusto.")
