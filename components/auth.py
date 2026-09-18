import streamlit as st

# Dizionario utenti (puoi aggiungere chi vuoi in futuro)
UTENTI = {
    "vins": {"password": "admin!", "nome": "Vincenzo", "is_admin": True},
    "monella": {"password": "user1!", "nome": "Silvia", "is_admin": False},
    "matteo": {"password": "matt", "nome": "Utente Ospite", "is_admin": False},
    "ospite": {"password": "test!", "nome": "Utente Ospite", "is_admin": False}
}

def require_login():
    """Verifica il login. Se assente, mostra il form e blocca l'esecuzione del resto della pagina."""
    
    # Inizializza le variabili se non esistono
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if "username" not in st.session_state: st.session_state.username = ""
    if "is_admin" not in st.session_state: st.session_state.is_admin = False

    # Prova a ripristinare la sessione dai parametri URL (anti-scollegamento)
    if not st.session_state.logged_in and "user" in st.query_params:
        q_user = st.query_params["user"]
        if q_user in UTENTI:
            st.session_state.logged_in = True
            st.session_state.username = q_user
            st.session_state.is_admin = UTENTI[q_user]["is_admin"]

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
                        st.success("✅ Accesso effettuato!")
                        st.rerun()
                    else:
                        st.error("❌ Username o password errati.")
        
        # Blocca l'esecuzione del codice sottostante finché non si fa l'accesso
        st.stop()