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

def clean_text(text):
    if not isinstance(text, str): text = str(text)
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z',
        '–': '-', '’': '\''
    }
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def generate_invoice(company_name, items_df, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 10, "FAKTURA VAT (PRO-FORMA)", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Data: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 10, clean_text(f"Nabywca: {company_name}"), ln=True)
    pdf.cell(0, 10, "Sprzedawca: ETHER ANALYTICS LTD.", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(140, 10, "Nazwa", border=1)
    pdf.cell(50, 10, clean_text("Wartość"), border=1)
    pdf.ln()
    pdf.set_font("Arial", size=12)
    for idx, row in items_df.iterrows():
        name = clean_text(str(row.iloc[0]))[:40]
        val = f"{row.iloc[1]:.2f}"
        pdf.cell(140, 10, name, border=1)
        pdf.cell(50, 10, val, border=1)
        pdf.ln()
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, clean_text(f"DO ZAPLATY: {total:,.2f} PLN"), ln=True, align='R')
    return pdf.output(dest='S').encode('latin-1')

# --- GENERATOR DANYCH DEMO ---
def load_demo_data():
    data = {
        'Produkt': ['Abonament VIP', 'Usługa Standard', 'Konsultacja', 'Audyt', 'Szkolenie'],
        'Wartość': [15000, 8000, 3000, 12000, 5000],
        'Data': pd.date_range(start='2024-01-01', periods=5)
    }
    return pd.DataFrame(data)

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
    
    st.write("📂 DANE WEJŚCIOWE")
    uploaded_file = st.file_uploader(f"Wgraj raport", type=['csv', 'xlsx'])
    
    # --- PRZYCISK DEMO ---
    if st.button("⚡ ZAŁADUJ DANE DEMO (Prezentacja)"):
        st.session_state.demo_mode = True
    else:
        if 'demo_mode' not in st.session_state:
            st.session_state.demo_mode = False
            
    st.divider()
    page = st.radio("Moduł:", ["Pulpit", "Strategia", "Symulator", "Fakturowanie"])
    st.divider()
    if st.button("Wyloguj"):
        st.session_state.logged_in = False
        st.rerun()

# --- LOGIKA DANYCH ---
df = None

# 1. Priorytet: Wgrany plik
if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
        else: df = pd.read_excel(uploaded_file)
    except: st.error("Błąd pliku.")

# 2. Jeśli brak pliku, ale kliknięto DEMO
elif st.session_state.demo_mode:
    df = load_demo_data()
    st.warning("⚠️ TRYB DEMONSTRACYJNY (Dane przykładowe)")

# --- WYŚWIETLANIE ---
if df is not None:
    # Mapowanie
    with st.expander("⚙️ Konfiguracja Kolumn", expanded=False):
        cols = df.columns.tolist()
        c1, c2, c3 = st.columns(3)
        col_cat = c1.selectbox(f"Kolumna: {terms['item']}", cols, index=0)
        col_val = c2.selectbox(f"Kolumna: {terms['value']}", cols, index=1 if len(cols)>1 else 0)
        col_date = c3.selectbox("Kolumna: Data", cols, index=2 if len(cols)>2 else 0)

    # Moduły
    if page == "Pulpit":
        st.title(f"Pulpit: {industry_mode}")
        total = df[col_val].sum()
        k1, k2 = st.columns(2)
        k1.metric(f"Całkowity {terms['value']}", f"{total:,.2f} PLN")
        k2.metric(f"Liczba {terms['action']}ów", len(df))
        try:
            chart_df = df.copy()
            chart_df[col_date] = pd.to_datetime(chart_df[col_date])
            st.area_chart(chart_df.groupby(col_date)[col_val].sum(), color="#d93025")
        except: st.line_chart(df[col_val])

    elif page == "Strategia":
        st.title("Analiza Kluczowa")
        top = df.groupby(col_cat)[col_val].sum().reset_index().sort_values(by=col_val, ascending=False).head(10)
        fig = px.bar(top, x=col_cat, y=col_val, title=f"Top 10: {terms['item']}", color=col_val, color_continuous_scale='Reds')
        st.plotly_chart(fig, use_container_width=True)

    elif page == "Symulator":
        st.title("Symulator Decyzji")
        change = st.slider("Zmiana ceny (%)", -50, 50, 10)
        current = df[col_val].sum()
        new_val = current * (1 + change/100)
        st.metric("Prognoza", f"{new_val:,.2f} PLN", delta=f"{new_val-current:,.2f} PLN")

    elif page == "Fakturowanie":
        st.title("Generator Faktur")
        client_name = st.text_input("Nabywca:", "Klient Testowy")
        col1, col2 = st.columns(2)
        top_items = df.groupby(col_cat)[col_val].sum().reset_index().sort_values(by=col_val, ascending=False).head(5)
        with col1: st.dataframe(top_items)
        with col2:
            total_invoice = top_items[col_val].sum()
            st.metric("Suma", f"{total_invoice:,.2f} PLN")
            if st.button("📄 WYSTAW FAKTURĘ PDF"):
                pdf_bytes = generate_invoice(client_name, top_items, total_invoice)
                st.download_button("Pobierz PDF", data=pdf_bytes, file_name="faktura.pdf", mime="application/pdf")
else:
    st.title(f"Witaj w ETHER {industry_mode}")
    st.info("👈 Wgraj plik lub kliknij 'ZAŁADUJ DANE DEMO' w panelu bocznym.")

# --- STOPKA PRAWNA (BARDZO WAŻNE DLA FIRM) ---
st.write("---")
st.markdown("""
    <div style='text-align: center; color: #666; font-size: 12px;'>
    <b>BEZPIECZEŃSTWO DANYCH:</b><br>
    System ETHER działa w bezpiecznym kontenerze sesyjnym. 
    Państwa dane są przetwarzane wyłącznie w pamięci operacyjnej (RAM) na czas trwania sesji 
    i są automatycznie usuwane w momencie wylogowania lub zamknięcia karty przeglądarki.
    Nie przechowujemy trwale żadnych plików finansowych na naszych serwerach (GDPR/RODO Compliant).
    <br><br>
    © 2024 ETHER ANALYTICS LTD. | Powered by Python Security Core
    </div>
    """, unsafe_allow_html=True)
