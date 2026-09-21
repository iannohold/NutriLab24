import streamlit as st
from streamlit_cookies_controller import CookieController

# Inizializziamo il controller in cima per renderlo disponibile subito
cookie_controller = CookieController()

# Dizionario utenti
UTENTI = {
    "vins": {"password": "admin!", "nome": "Vincenzo", "is_admin": True},
    "monella": {"password": "user1!", "nome": "Silvia", "is_admin": False},
    "matteo": {"password": "matt", "nome": "Utente Ospite", "is_admin": False},
    "ospite": {"password": "test!", "nome": "Utente Ospite", "is_admin": False}
}

def require_login():
    """Verifica il login tramite Session State o Cookie. Blocca l'esecuzione se assente."""
    
    # Inizializza le variabili se non esistono
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if "username" not in st.session_state: st.session_state.username = ""
    if "is_admin" not in st.session_state: st.session_state.is_admin = False

    # 1. Prova a ripristinare la sessione dal Cookie in modo sicuro (evita crash di caricamento)
    saved_user = None
    try:
        saved_user = cookie_controller.get('nutrilab_user')
    except Exception:
        pass

    if not st.session_state.logged_in and saved_user and saved_user in UTENTI:
        st.session_state.logged_in = True
        st.session_state.username = saved_user
        st.session_state.is_admin = UTENTI[saved_user]["is_admin"]

    # 2. Prova a ripristinare dai parametri URL (fallback di emergenza)
    if not st.session_state.logged_in and "user" in st.query_params:
        q_user = st.query_params["user"]
        if q_user in UTENTI:
            st.session_state.logged_in = True
            st.session_state.username = q_user
            st.session_state.is_admin = UTENTI[q_user]["is_admin"]
            try:
                cookie_controller.set('nutrilab_user', q_user, max_age=2592000)
            except Exception:
                pass

    # Se ancora non è loggato, mostra il box di accesso
    if not st.session_state.logged_in:
        st.warning("⚠️ Sessione scaduta o non avviata. Effettua il login per continuare.")
        st.markdown("<h2 style='text-align: center;'>🔐 Accesso a NutriLab</h2>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            with st.form("login_form_shared"):
                username_input = st.text_input("Username").lower().strip()
                password_input = st.text_input("Password", type="password")
                submit_button = st.form_submit_button("Accedi", use_container_width=True)
                
                if submit_button:
                    if username_input in UTENTI and UTENTI[username_input]["password"] == password_input:
                        st.session_state.logged_in = True
                        st.session_state.username = username_input
                        st.session_state.is_admin = UTENTI[username_input]["is_admin"]
                        st.query_params["user"] = username_input 
                        try:
                            # Salva il Cookie per 30 giorni
                            cookie_controller.set('nutrilab_user', username_input, max_age=2592000)
                        except Exception:
                            pass
                        st.success("✅ Accesso effettuato!")
                        st.rerun()
                    else:
                        st.error("❌ Username o password errati.")
        
        # Blocca l'esecuzione del codice sottostante finché non si fa l'accesso
        st.stop()