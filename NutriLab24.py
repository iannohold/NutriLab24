import streamlit as st

# Configurazione base della pagina (deve essere la prima istruzione)
st.set_page_config(page_title="NutriLab", page_icon="🧪", layout="wide")

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
# 🔐 DATABASE UTENTI LOCALE
# =========================================================
UTENTI = {
    "vins": {"password": "admin!", "nome": "Vincenzo", "is_admin": True},
    "monella": {"password": "user1!", "nome": "Silvia", "is_admin": False},
    "ospite": {"password": "test!", "nome": "Utente Ospite", "is_admin": False}
}

# =========================================================
# ⚙️ INIZIALIZZAZIONE STATO DI SESSIONE
# =========================================================
if "logged_in" not in st.session_state: 
    st.session_state.logged_in = False
if "username" not in st.session_state: 
    st.session_state.username = ""
if "is_admin" not in st.session_state: 
    st.session_state.is_admin = False

# Auto-login tramite URL (es. ?user=vins)
if not st.session_state.logged_in and "user" in st.query_params:
    q_user = st.query_params["user"]
    if q_user in UTENTI:
        st.session_state.logged_in = True
        st.session_state.username = q_user
        st.session_state.is_admin = UTENTI[q_user]["is_admin"]

# =========================================================
# 🚪 SCHERMATA DI LOGIN
# =========================================================
if not st.session_state.logged_in:
    st.markdown("<br><br><h1 style='text-align: center;'>🔐 Accesso a NutriLab</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Accedi per visualizzare le tue ricette e il tuo diario alimentare.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            username_input = st.text_input("Username").lower().strip()
            password_input = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Accedi", use_container_width=True)
            
            if submit_button:
                if username_input in UTENTI and UTENTI[username_input]["password"] == password_input:
                    st.session_state.logged_in = True
                    st.session_state.username = username_input
                    st.session_state.is_admin = UTENTI[username_input]["is_admin"]
                    st.query_params["user"] = username_input 
                    st.success("✅ Accesso effettuato!")
                    st.rerun()
                else:
                    st.error("❌ Username o password errati.")
    
    st.markdown("<br><br><div style='text-align: center; color: gray;'><small>⚡ Powered by iannovins</small></div>", unsafe_allow_html=True)
    st.stop()

# =========================================================
# 👋 DASHBOARD PRINCIPALE (A LOGIN EFFETTUATO)
# =========================================================
st.title(f"👋 Benvenuto, {UTENTI[st.session_state.username]['nome']}!")
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
    st.cache_data.clear()
    st.rerun()

st.markdown("<br><br><div style='text-align: center; color: gray;'><small>⚡ Powered by iannovins</small></div>", unsafe_allow_html=True)
