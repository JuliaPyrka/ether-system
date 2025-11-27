import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from fpdf import FPDF
from datetime import datetime

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | CFO EDITION", layout="wide")

# --- STYLE CSS (PRO MODE) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 15px; border-radius: 5px; }
    .cost-box { border-left: 4px solid #f44336; } /* Czerwony dla kosztów */
    .profit-box { border-left: 4px solid #4caf50; } /* Zielony dla zysku */
    </style>
    """, unsafe_allow_html=True)

# --- BAZA DANYCH (Symulowana) ---
USERS = { "admin": "AlastorRules", "kino": "film123", "sklep": "buty2024", "demo": "demo" }

# --- SŁOWNIK BRANŻOWY ---
INDUSTRY_TERMS = {
    "Uniwersalny": {"item": "Produkt", "value": "Wartość", "action": "Sprzedaż"},
    "Kino / Teatr": {"item": "Film/Spektakl", "value": "Przychód", "action": "Seans"},
    "Handel (Retail)": {"item": "Towar", "value": "Cena", "action": "Transakcja"},
}

# --- FUNKCJE ---
def check_login(username, password):
    return username in USERS and USERS[username] == password

def clean_text(text):
    if not isinstance(text, str): text = str(text)
    replacements = {'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z', '–':'-'}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text.encode('latin-1', 'ignore').decode('latin-1')

def generate_invoice(company_name, items_df, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 10, "FAKTURA VAT", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Data: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 10, clean_text(f"Nabywca: {company_name}"), ln=True)
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
    pdf.cell(0, 10, clean_text(f"SUMA: {total:,.2f} PLN"), ln=True, align='R')
    return pdf.output(dest='S').encode('latin-1')

# --- INITIALIZACJA SESJI KOSZTÓW ---
if 'expenses' not in st.session_state:
    # Tworzymy pustą tabelę kosztów na start
    st.session_state.expenses = pd.DataFrame(columns=["Nazwa", "Kategoria", "Kwota", "Data"])

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
            else: st.error("Błąd.")
    st.stop()

# ==========================================
# APLIKACJA
# ==========================================
with st.sidebar:
    st.title(f"👤 {st.session_state.user.upper()}")
    industry = st.selectbox("Branża:", list(INDUSTRY_TERMS.keys()))
    terms = INDUSTRY_TERMS[industry]
    st.divider()
    uploaded_file = st.file_uploader(f"📥 1. Wgraj Przychody", type=['csv', 'xlsx'])
    st.divider()
    # Rozbudowane menu
    page = st.radio("Moduł:", ["Pulpit Finansowy", "📉 Rejestr Kosztów", "Strategia", "Faktury"])
    st.divider()
    if st.button("Wyloguj"): st.session_state.logged_in = False; st.rerun()

# --- LOGIKA DANYCH ---
df_income = None
if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'): df_income = pd.read_csv(uploaded_file)
        else: df_income = pd.read_excel(uploaded_file)
    except: st.error("Błąd pliku.")
elif st.session_state.get('demo_mode'):
    df_income = pd.DataFrame({'Produkt':['A','B'], 'Kwota':[1000,2000], 'Data':['2024-01-01','2024-01-02']})

# --- EKRANY ---

if page == "📉 Rejestr Kosztów":
    st.title("Centrum Kosztów (Faktury Zakupowe)")
    st.markdown('<div class="info-box">Dodaj tutaj faktury kosztowe, aby system mógł wyliczyć realny zysk firmy.</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("➕ Dodaj Fakturę")
        with st.form("cost_form"):
            ex_name = st.text_input("Nazwa (np. Prąd, Towar)")
            ex_cat = st.selectbox("Kategoria", ["Zasoby/Towar", "Media/Prąd", "Pracownicy", "Marketing", "Inne"])
            ex_val = st.number_input("Kwota Brutto (PLN)", min_value=0.0, step=10.0)
            ex_date = st.date_input("Data Faktury")
            
            if st.form_submit_button("Zaksięguj Koszt"):
                new_row = pd.DataFrame({"Nazwa": [ex_name], "Kategoria": [ex_cat], "Kwota": [ex_val], "Data": [ex_date]})
                st.session_state.expenses = pd.concat([st.session_state.expenses, new_row], ignore_index=True)
                st.success("Dodano!")
                st.rerun()

    with col2:
        st.subheader("📋 Lista Wydatków")
        if not st.session_state.expenses.empty:
            st.dataframe(st.session_state.expenses, use_container_width=True)
            
            # Wykres kołowy wydatków
            fig = px.pie(st.session_state.expenses, values='Kwota', names='Kategoria', title="Gdzie uciekają pieniądze?", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Brak kosztów. Dodaj pierwszą fakturę po lewej.")

elif page == "Pulpit Finansowy":
    st.title("Pulpit CFO (Zysk i Straty)")
    
    if df_income is not None:
        # Konfiguracja kolumny przychodu
        cols = df_income.columns.tolist()
        col_val = cols[1] if len(cols)>1 else cols[0] # Automatyczny wybór (uproszczony)
        
        # 1. PRZYCHODY
        total_income = df_income[col_val].sum()
        
        # 2. KOSZTY
        total_costs = st.session_state.expenses['Kwota'].sum() if not st.session_state.expenses.empty else 0
        
        # 3. ZYSK
        net_profit = total_income - total_costs
        
        # WIZUALIZACJA KPI
        k1, k2, k3 = st.columns(3)
        k1.metric("💰 Przychody (Sprzedaż)", f"{total_income:,.2f} PLN")
        k2.metric("💸 Koszty (Faktury)", f"{total_costs:,.2f} PLN", delta_color="inverse")
        k3.metric("💎 Zysk Netto (Na rękę)", f"{net_profit:,.2f} PLN", delta=f"{(net_profit/total_income)*100:.1f}% Marży" if total_income>0 else "0%")
        
        st.divider()
        
        # Wykres Wodospadowy (Waterfall) - Profesjonalny wykres finansowy
        st.subheader("Analiza Rentowności")
        waterfall_data = pd.DataFrame({
            "Typ": ["Przychód", "Koszty", "Zysk"],
            "Kwota": [total_income, -total_costs, net_profit]
        })
        fig = px.bar(waterfall_data, x="Typ", y="Kwota", color="Kwota", title="Bilans Firmy", text_auto=True, color_continuous_scale="RdYlGn")
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.warning("Wgraj plik z Przychodami (Panel boczny), aby zobaczyć bilans.")

elif page == "Strategia":
    st.title("Strategia")
    if df_income is not None:
        cols = df_income.columns.tolist()
        c_cat = cols[0]
        c_val = cols[1] if len(cols)>1 else cols[0]
        top = df_income.groupby(c_cat)[c_val].sum().reset_index().sort_values(by=c_val, ascending=False).head(10)
        st.plotly_chart(px.bar(top, x=c_cat, y=c_val, title="Top Produkty"), use_container_width=True)

elif page == "Faktury":
    st.title("Generator Faktur Sprzedażowych")
    if df_income is not None:
        cols = df_income.columns.tolist()
        c_cat = cols[0]
        c_val = cols[1]
        items = df_income.groupby(c_cat)[c_val].sum().reset_index().head(5)
        st.dataframe(items)
        if st.button("Wystaw PDF"):
            pdf = generate_invoice("Klient", items, items[c_val].sum())
            st.download_button("Pobierz", pdf, "faktura.pdf", "application/pdf")
