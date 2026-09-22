import streamlit as st
from streamlit_cookies_controller import CookieController
from components.auth import require_login, get_utente_db

# Configurazione base della pagina (deve essere la prima istruzione)
st.set_page_config(page_title="NutriLab", page_icon="🧪", layout="wide")

cookie_controller = CookieController()

# =========================================================
# 📱 STYLING RESPONSIVE (NASCONDI SIDEBAR SU MOBILE)
# =========================================================
st.markdown(
    """
    <style>
    @media (max-width: 768px) {
        /* Nasconde la barra laterale su smartphone e tablet */
        [data-testid="stSidebar"] {
            display: none;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# 🔐 CONTROLLO DI SICUREZZA CENTRALIZZATO (SUPABASE)
# =========================================================
require_login()

# =========================================================
# 👋 DASHBOARD PRINCIPALE (A LOGIN EFFETTUATO)
# =========================================================
dati_utente = get_utente_db(st.session_state.username)
nome_visibile = dati_utente['nome'] if dati_utente else st.session_state.username

st.title(f"👋 Benvenuto, {nome_visibile}!")
st.markdown("#### *Seleziona un'area di lavoro per iniziare:*")
st.write("")

# Griglia di pulsanti interattivi (ottima sia per desktop che per mobile senza menu)
col_a, col_b = st.columns(2)

with col_a:
    if st.button("🧪 **Laboratorio Ricette**\n\n*Progetta e bilancia le tue idee*", use_container_width=True):
        st.switch_page("pages/1_🧪_Laboratorio.py")
    
    if st.button("📆 **Meal Planner & Spesa**\n\n*Pianifica i pasti futuri*", use_container_width=True):
        st.switch_page("pages/3_📆_Meal_Planner.py")
        
    if st.button("📦 **Dispensa**\n\n*Monitora le scorte a casa*", use_container_width=True):
        st.switch_page("pages/5_📦_Dispensa.py")

with col_b:
    if st.button("📅 **Diario Alimentare**\n\n*Registra e segui i consumi*", use_container_width=True):
        st.switch_page("pages/2_📅_Diario.py")
        
    if st.button("🗄️ **Database Prodotti**\n\n*Gestisci gli ingredienti*", use_container_width=True):
        st.switch_page("pages/4_🗄️_Database.py")
        
    if st.button("👤 **Profilo e Obiettivi**\n\n*Calcola fabbisogno e target*", use_container_width=True):
        st.switch_page("pages/6_👤_Profilo.py")

st.divider()

col_logout, _ = st.columns([1, 4])
if col_logout.button("🚪 Logout", type="secondary", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.is_admin = False
    if "user" in st.query_params: 
        del st.query_params["user"]
    # Rimuove il Cookie al momento del logout
    cookie_controller.remove('nutrilab_user')
    st.cache_data.clear()
    st.rerun()

st.markdown("<br><br><div style='text-align: center; color: gray;'><small>⚡ Powered by iannovins</small></div>", unsafe_allow_html=True)
