import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from fpdf import FPDF
from datetime import datetime

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | ENTERPRISE", layout="wide")

# --- BAZA UŻYTKOWNIKÓW ---
USERS = {
    "admin": "AlastorRules",
    "kino": "film123",
    "sklep": "buty2024",
    "demo": "demo"
}

# --- SŁOWNIK BRANŻOWY ---
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

# Funkcja czyszcząca tekst (NAPRAWA BŁĘDU LATIN-1)
def clean_text(text):
    if not isinstance(text, str):
        text = str(text)
    
    # Mapa polskich znaków
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z',
        '–': '-', '’': '\''
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    
    # Ostateczne zabezpieczenie - usuwa inne dziwne znaki
    return text.encode('latin-1', 'ignore').decode('latin-1')

def generate_invoice(company_name, items_df, total):
    pdf = FPDF()
    pdf.add_page()
    
    # Ustawiamy czcionkę (Arial jest standardem)
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 10, "FAKTURA VAT (PRO-FORMA)", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    # Używamy clean_text dla każdej zmiennej tekstowej
    pdf.cell(0, 10, f"Data wystawienia: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 10, clean_text(f"Nabywca: {company_name}"), ln=True)
    pdf.cell(0, 10, "Sprzedawca: ETHER ANALYTICS LTD.", ln=True)
    pdf.ln(10)
    
    # Tabela Nagłówki
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(140, 10, "Nazwa", border=1)
    pdf.cell(50, 10, clean_text("Wartość"), border=1)
    pdf.ln()
    
    # Tabela Wiersze
    pdf.set_font("Arial", size=12)
    for idx, row in items_df.iterrows():
        # Czyścimy nazwę produktu z polskich znaków
        raw_name = str(row.iloc[0])
        name = clean_text(raw_name)[:40] # Ucinamy za długie nazwy
        val = f"{row.iloc[1]:.2f}"
        
        pdf.cell(140, 10, name, border=1)
        pdf.cell(50, 10, val, border=1)
        pdf.ln()
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean_text(f"DO ZAPLATY: {total:,.2f} PLN"), ln=True, align='R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# EKRAN LOGOWANIA
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
                st.error("Błędne dane.")
    st.stop()

# ==========================================
# GŁÓWNA APLIKACJA
# ==========================================

with st.sidebar:
    st.title(f"👤 {st.session_state.user.upper()}")
    industry_mode = st.selectbox("Branża / Tryb:", list(INDUSTRY_TERMS.keys()))
    terms = INDUSTRY_TERMS[industry_mode]
    st.divider()
    uploaded_file = st.file_uploader(f"Wgraj dane ({terms['action']})", type=['csv', 'xlsx'])
    st.divider()
    page = st.radio("Moduł:", ["Pulpit", "Strategia", "Symulator", "Fakturowanie"])
    st.divider()
    if st.button("Wyloguj"):
        st.session_state.logged_in = False
        st.rerun()

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

        # MODUŁY
        if page == "Pulpit":
            st.title(f"Pulpit: {industry_mode}")
            total = df[col_val].sum()
            k1, k2 = st.columns(2)
            k1.metric(f"Całkowity {terms['value']}", f"{total:,.2f} PLN")
            k2.metric(f"Liczba {terms['action']}ów", len(df))
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
            change = st.slider("Zmiana ceny (%)", -50, 50, 10)
            current = df[col_val].sum()
            new_val = current * (1 + change/100)
            st.metric("Prognozowany Wynik", f"{new_val:,.2f} PLN", delta=f"{new_val-current:,.2f} PLN")

        elif page == "Fakturowanie":
            st.title("Generator Faktur")
            client_name = st.text_input("Nabywca (Nazwa):", "Klient Detaliczny")
            
            col1, col2 = st.columns(2)
            top_items = df.groupby(col_cat)[col_val].sum().reset_index().sort_values(by=col_val, ascending=False).head(5)
            
            with col1:
                st.dataframe(top_items)
            with col2:
                total_invoice = top_items[col_val].sum()
                st.metric("Suma Faktury", f"{total_invoice:,.2f} PLN")
                
                if st.button("📄 WYSTAW FAKTURĘ PDF"):
                    # Tu wywołujemy nową, bezpieczną funkcję
                    pdf_bytes = generate_invoice(client_name, top_items, total_invoice)
                    st.success("Faktura wygenerowana!")
                    st.download_button("Pobierz PDF", data=pdf_bytes, file_name="faktura.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"Błąd formatu danych: {e}")
else:
    st.title("Witaj w ETHER ENTERPRISE")
    st.write("Wybierz branżę i wgraj plik.")
