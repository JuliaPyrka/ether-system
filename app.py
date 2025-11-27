import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from sklearn.linear_model import LinearRegression
from fpdf import FPDF
import base64

# --- KONFIGURACJA ---
st.set_page_config(page_title="ETHER | ULTIMATE", layout="wide")

# --- STYL ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    h1 { color: #ffffff !important; font-family: 'Helvetica', sans-serif; }
    div[data-testid="stMetric"] { background-color: #1a1c24; border-left: 4px solid #d93025; padding: 10px; border-radius: 5px; }
    .info-box { background-color: #1a1c24; padding: 15px; border-radius: 5px; border-left: 4px solid #5f6368; margin-bottom: 20px; color: #cfcfcf; }
    </style>
    """, unsafe_allow_html=True)

# --- ZMIENNE SESJI ---
if 'col_cat' not in st.session_state: st.session_state.col_cat = None
if 'col_val' not in st.session_state: st.session_state.col_val = None
if 'col_date' not in st.session_state: st.session_state.col_date = None

# --- FUNKCJA PDF (Uproszczona, usuwa polskie znaki bo FPDF ma z nimi problem bez czcionki) ---
def clean_text(text):
    replacements = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
                    'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def create_pdf(df, total_rev, best_item):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Nagłówek
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="RAPORT SYSTEMU ETHER", ln=1, align='C')
    pdf.ln(10)
    
    # Dane Główne
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=clean_text(f"Calkowity Obrot: {total_rev:,.2f} PLN"), ln=1)
    pdf.cell(200, 10, txt=clean_text(f"Najlepszy Produkt: {best_item}"), ln=1)
    pdf.ln(10)
    
    # Tabela (Top 5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="TOP 5 POZYCJI:", ln=1)
    pdf.set_font("Arial", size=10)
    for index, row in df.head(5).iterrows():
        line = f"{index+1}. {row.iloc[0]} - {row.iloc[1]:,.2f} PLN"
        pdf.cell(200, 8, txt=clean_text(line), ln=1)
        
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# PANEL BOCZNY
# ==========================================
with st.sidebar:
    st.title("🎙️ ETHER v5.0")
    st.caption("ULTIMATE EDITION")
    st.write("---")
    uploaded_file = st.file_uploader("📂 BAZA DANYCH (CSV/XLSX)", type=["csv", "xlsx"])
    st.write("---")
    page = st.radio("MODUŁ:", ["📡 Pulpit", "🧠 Strategia 80/20", "🔮 Wyrocznia AI", "🎛️ Symulator", "📑 Raport PDF"])

# ==========================================
# GŁÓWNA LOGIKA
# ==========================================
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
        else: df = pd.read_excel(uploaded_file)
            
        with st.expander("⚙️ KONFIGURACJA KOLUMN", expanded=False):
            cols = df.columns.tolist()
            c1, c2, c3 = st.columns(3)
            with c1: col_cat = st.selectbox("Produkt:", cols, index=1 if len(cols)>1 else 0)
            with c2: col_val = st.selectbox("Kwota:", cols, index=3 if len(cols)>3 else 0)
            with c3: col_date = st.selectbox("Data:", cols, index=0)

        # --- PULPIT ---
        if page == "📡 Pulpit":
            st.title("Pulpit Zarządczy")
            st.markdown('<div class="info-box">Centrum kontroli bieżącej.</div>', unsafe_allow_html=True)
            k1, k2, k3 = st.columns(3)
            k1.metric("Obrót", f"{df[col_val].sum():,.0f} PLN")
            k2.metric("Transakcje", len(df))
            k3.metric("Średnia", f"{df[col_val].mean():,.0f} PLN")
            try:
                chart_df = df.copy()
                chart_df[col_date] = pd.to_datetime(chart_df[col_date])
                st.area_chart(chart_df.groupby(col_date)[col_val].sum(), color="#d93025")
            except: st.line_chart(df[col_val])

        # --- STRATEGIA ---
        elif page == "🧠 Strategia 80/20":
            st.title("Analiza Pareto")
            pareto = df.groupby(col_cat)[col_val].sum().reset_index().sort_values(by=col_val, ascending=False)
            fig = px.bar(pareto.head(10), x=col_cat, y=col_val, color=col_val, color_continuous_scale='Reds')
            st.plotly_chart(fig, use_container_width=True)

        # --- WYROCZNIA AI (NOWOŚĆ 1) ---
        elif page == "🔮 Wyrocznia AI":
            st.title("Prognoza Przyszłości")
            st.markdown('<div class="info-box">Algorytm Regresji Liniowej analizuje historię i przewiduje trend na kolejne dni.</div>', unsafe_allow_html=True)
            
            try:
                # Przygotowanie danych
                forecast_df = df.copy()
                forecast_df[col_date] = pd.to_datetime(forecast_df[col_date])
                daily = forecast_df.groupby(col_date)[col_val].sum().reset_index()
                
                # Matematyka (AI)
                daily['days_numeric'] = (daily[col_date] - daily[col_date].min()).dt.days
                X = daily[['days_numeric']]
                y = daily[col_val]
                model = LinearRegression()
                model.fit(X, y)
                
                # Prognoza na 30 dni w przód
                future_days = st.slider("Ile dni w przód przewidzieć?", 7, 90, 30)
                last_day = daily['days_numeric'].max()
                future_X = np.array(range(last_day + 1, last_day + future_days + 1)).reshape(-1, 1)
                future_pred = model.predict(future_X)
                
                # Wykres
                st.subheader(f"Prognoza na {future_days} dni")
                
                # Łączenie danych do wykresu
                last_date = daily[col_date].max()
                future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, future_days + 1)]
                pred_df = pd.DataFrame({col_date: future_dates, 'Prognoza': future_pred})
                
                # Wyświetlanie
                combined = pd.concat([daily[[col_date, col_val]].rename(columns={col_val:'Historia'}), pred_df.rename(columns={'Prognoza':'Przyszłość'})])
                combined = combined.set_index(col_date)
                st.line_chart(combined)
                
                trend = "WZROSTOWY 📈" if model.coef_[0] > 0 else "SPADKOWY 📉"
                st.metric("Kierunek Trendu", trend, f"{model.coef_[0]:.2f} PLN / dzień")
                
            except Exception as e:
                st.warning(f"AI potrzebuje dat w formacie RRRR-MM-DD. Błąd: {e}")

        # --- SYMULATOR (NOWOŚĆ 2) ---
        elif page == "🎛️ Symulator":
            st.title("Symulator Rzeczywistości")
            st.markdown('<div class="info-box">Zmień parametry i zobacz, co się stanie (What-If Analysis).</div>', unsafe_allow_html=True)
            
            current_rev = df[col_val].sum()
            
            c1, c2 = st.columns(2)
            with c1:
                price_change = st.slider("Zmiana Ceny (%)", -50, 50, 0)
            with c2:
                volume_change = st.slider("Zmiana Liczby Klientów (%)", -50, 50, 0)
            
            # Matematyka symulacji
            new_rev = current_rev * (1 + price_change/100) * (1 + volume_change/100)
            diff = new_rev - current_rev
            
            st.divider()
            k1, k2 = st.columns(2)
            k1.metric("Obecny Wynik", f"{current_rev:,.0f} PLN")
            k2.metric("Symulacja", f"{new_rev:,.0f} PLN", f"{diff:,.0f} PLN")
            
            if diff > 0: st.success("To by była dobra decyzja!")
            elif diff < 0: st.error("Uważaj, stracisz pieniądze.")

        # --- PDF (NOWOŚĆ 3) ---
        elif page == "📑 Raport PDF":
            st.title("Generator Dokumentów")
            st.markdown('<div class="info-box">Pobierz oficjalny raport dla zarządu.</div>', unsafe_allow_html=True)
            
            if st.button("🖨️ WYGENERUJ PDF"):
                pareto_top = df.groupby(col_cat)[col_val].sum().reset_index().sort_values(by=col_val, ascending=False)
                best_item = pareto_top.iloc[0][col_cat]
                total_rev = df[col_val].sum()
                
                pdf_data = create_pdf(pareto_top, total_rev, best_item)
                
                st.success("Raport gotowy!")
                st.download_button(label="📥 POBIERZ PLIK", data=pdf_data, file_name="raport_ether.pdf", mime="application/pdf")

    except Exception as e: st.error(f"Błąd: {e}")
else:
    st.title("ETHER v5.0 [ULTIMATE]")
    st.write("Wgraj dane, aby uzyskać pełną kontrolę.")
    