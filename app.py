import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from sklearn.linear_model import LinearRegression
from fpdf import FPDF
from datetime import datetime

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | ENTERPRISE", layout="wide")

# --- BAZA UŻYTKOWNIKÓW (Symulacja Bazy Danych) ---
# W prawdziwym SaaS trzymalibyśmy to w SQL. Tutaj Ty jesteś administratorem.
USERS = {
    "admin": "AlastorRules",    # Ty (Pełny dostęp)
    "kino": "film123",          # Klient: Kino Bajka
    "sklep": "buty2024",        # Klient: Sklep Obuwniczy
    "demo": "demo"              # Klient testowy
}

# --- SŁOWNIK BRANŻOWY (Chameleon Mode) ---
INDUSTRY_TERMS = {
    "Uniwersalny": {"item": "Produkt", "value": "Wartość", "action": "Sprzedaż"},
    "Kino / Teatr": {"item": "Film/Spektakl", "value": "Przychód z biletów", "action": "Seans"},
    "Handel (Retail)": {"item": "Towar", "value": "Cena", "action": "Transakcja"},
    "Usługi B2B": {"item": "Usługa", "value": "Faktura", "action": "Wdrożenie"}
}

# --- FUNKCJE POMOCNICZE ---
def check_login(username, password):
    if username in USERS and USERS[username] == password:
        return True
    return False

def generate_invoice(company_name, items_df, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 10, "FAKTURA VAT (PRO-FORMA)", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Data wystawienia: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 10, f"Nabywca: {company_name}", ln=True)
    pdf.cell(0, 10, f"Sprzedawca: ETHER ANALYTICS LTD.", ln=True)
    pdf.ln(10)
    
    # Tabela
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, "Nazwa", border=1)
    pdf.cell(50, 10, "Wartość", border=1)
    pdf.ln()
    
    pdf.set_font("Arial", size=12)
    for idx, row in items_df.iterrows():
        # Ucinamy nazwę żeby się mieściła
        name = str(row.iloc[0])[:30]
        val = f"{row.iloc[1]:.2f}"
        pdf.cell(100, 10, name, border=1)
        pdf.cell(50, 10, val, border=1)
        pdf.ln()
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"DO ZAPLATY: {total:,.2f} PLN", ln=True, align='R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# EKRAN LOGOWANIA (GATEKEEPER v2.0)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #d93025;'>ETHER ENTERPRISE</h1>", unsafe_allow_html=True)
        st.info("Zaloguj się do przestrzeni roboczej.")
        
        user_input = st.text_input("Login")
        pass_input = st.text_input("Hasło", type="password")
        
        if st.button("ZALOGUJ DO SYSTEMU"):
            if check_login(user_input, pass_input):
                st.session_state.logged_in = True
                st.session_state.user = user_input
                st.rerun()
            else:
                st.error("Błędne dane. Skontaktuj się z administratorem.")
    st.stop()

# ==========================================
# GŁÓWNA APLIKACJA (Po zalogowaniu)
# ==========================================

# --- MENU BOCZNE ---
with st.sidebar:
    st.title(f"👤 Użytkownik: {st.session_state.user.upper()}")
    
    # 1. WYBÓR BRANŻY (Nowość!)
    industry_mode = st.selectbox("Branża / Tryb:", list(INDUSTRY_TERMS.keys()))
    terms = INDUSTRY_TERMS[industry_mode] # Pobieramy słownik słów
    
    st.divider()
    
    # 2. WGRYWANIE
    uploaded_file = st.file_uploader(f"Wgraj dane ({terms['action']})", type=['csv', 'xlsx'])
    
    st.divider()
    
    # 3. NAWIGACJA
    page = st.radio("Moduł:", ["Pulpit", "Strategia", "Symulator", "Fakturowanie"])
    
    st.divider()
    if st.button("Wyloguj"):
        st.session_state.logged_in = False
        st.rerun()

# --- LOGIKA ---
if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
        else: df = pd.read_excel(uploaded_file)

        # Mapowanie kolumn
        with st.expander("⚙️ Konfiguracja Kolumn", expanded=False):
            cols = df.columns.tolist()
            c1, c2, c3 = st.columns(3)
            col_cat = c1.selectbox(f"Kolumna: {terms['item']}", cols, index=1 if len(cols)>1 else 0)
            col_val = c2.selectbox(f"Kolumna: {terms['value']}", cols, index=3 if len(cols)>3 else 0)
            col_date = c3.selectbox("Kolumna: Data", cols, index=0)

        # --- MODUŁY ---
        
        if page == "Pulpit":
            st.title(f"Pulpit: {industry_mode}")
            total = df[col_val].sum()
            k1, k2 = st.columns(2)
            k1.metric(f"Całkowity {terms['value']}", f"{total:,.2f} PLN")
            k2.metric(f"Liczba {terms['action']}ów", len(df))
            
            # Wykres
            st.subheader("Dynamika Sprzedaży")
            try:
                chart_df = df.copy()
                chart_df[col_date] = pd.to_datetime(chart_df[col_date])
                st.area_chart(chart_df.groupby(col_date)[col_val].sum(), color="#d93025")
            except:
                st.line_chart(df[col_val])

        elif page == "Strategia":
            st.title("Analiza Kluczowych Klientów/Produktów")
            top = df.groupby(col_cat)[col_val].sum().reset_index().sort_values(by=col_val, ascending=False).head(10)
            fig = px.bar(top, x=col_cat, y=col_val, title=f"Top 10: {terms['item']}", color=col_val, color_continuous_scale='Reds')
            st.plotly_chart(fig, use_container_width=True)

        elif page == "Symulator":
            st.title("Symulator Decyzji Biznesowych")
            st.write(f"Co się stanie, jeśli zmienisz ceny dla: {terms['item']}?")
            change = st.slider("Zmiana ceny (%)", -50, 50, 10)
            current = df[col_val].sum()
            new_val = current * (1 + change/100)
            st.metric("Prognozowany Wynik", f"{new_val:,.2f} PLN", delta=f"{new_val-current:,.2f} PLN")

        elif page == "Fakturowanie":
            st.title("Generator Faktur i Raportów")
            st.info("Wygeneruj oficjalny dokument na podstawie wgranych danych.")
            
            client_name = st.text_input("Nazwa Klienta (na fakturze):", "Klient Detaliczny")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("Podgląd pozycji do faktury (Top 5):")
                top_items = df.groupby(col_cat)[col_val].sum().reset_index().sort_values(by=col_val, ascending=False).head(5)
                st.dataframe(top_items)
                
            with col2:
                st.write("Podsumowanie:")
                total_invoice = top_items[col_val].sum()
                st.metric("Suma Faktury", f"{total_invoice:,.2f} PLN")
                
                if st.button("📄 WYSTAW FAKTURĘ PDF"):
                    pdf_bytes = generate_invoice(client_name, top_items, total_invoice)
                    st.success("Faktura wygenerowana!")
                    st.download_button("Pobierz PDF", data=pdf_bytes, file_name="faktura.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"Błąd formatu danych: {e}")
else:
    st.title("Witaj w ETHER ENTERPRISE")
    st.write("Wybierz branżę w menu bocznym i wgraj plik, aby rozpocząć.")
