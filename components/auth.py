import streamlit as st
from streamlit_cookies_controller import CookieController
from sqlalchemy import text
from services.db import get_conn

cookie_controller = CookieController()

def get_utente_db(email):
    """Recupera l'utente dal database Supabase usando l'email come ID."""
    
    # 🪂 PARACADUTE DI EMERGENZA (Vincenzo entra sempre)
    if email.lower() == "iannovins@gmail.com":
        return {"password": "admin!", "nome": "Vincenzo", "is_admin": True, "is_active": True}
        
    conn = get_conn()
    try:
        # Rimossa la funzione text() per massima compatibilità con Streamlit
        query = "SELECT password, nome, is_admin, is_active FROM utenti WHERE LOWER(email) = LOWER(:e)"
        df = conn.query(query, params={"e": email.strip()}, ttl=0)
        
        if not df.empty:
            row = df.iloc[0]
            return {
                "password": str(row["password"]),
                "nome": str(row.get("nome", "")),
                "is_admin": bool(row["is_admin"]),
                "is_active": bool(row["is_active"])
            }
    except Exception as e:
        st.error(f"🚨 Errore di lettura dal database: {e}")
    return None

def require_login():
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if "username" not in st.session_state: st.session_state.username = ""
    if "is_admin" not in st.session_state: st.session_state.is_admin = False

    if not st.session_state.get("is_admin", False):
        st.markdown("""
            <style>
            [data-testid="stSidebarNav"] a[href*="Amministrazione"] {display: none !important;}
            </style>
        """, unsafe_allow_html=True)

    saved_user = None
    try: saved_user = cookie_controller.get('nutrilab_user')
    except Exception: pass

    if not st.session_state.logged_in and saved_user:
        user_data = get_utente_db(saved_user)
        if user_data and user_data["is_active"]:
            st.session_state.logged_in = True
            st.session_state.username = saved_user
            st.session_state.is_admin = user_data["is_admin"]

    if not st.session_state.logged_in and "user" in st.query_params:
        q_user = st.query_params["user"]
        user_data = get_utente_db(q_user)
        if user_data and user_data["is_active"]:
            st.session_state.logged_in = True
            st.session_state.username = q_user
            st.session_state.is_admin = user_data["is_admin"]
            try: cookie_controller.set('nutrilab_user', q_user, max_age=2592000)
            except Exception: pass

    if not st.session_state.logged_in:
        st.warning("⚠️ Sessione scaduta o non avviata. Effettua il login per continuare.")
        
        # 🔴 MODIFICA VISIVA: Se non vedi "(V2)", l'app sta leggendo il file vecchio!
        st.markdown("<h2 style='text-align: center;'>🔐 Accesso a NutriLab24 (V2)</h2>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            tab_login, tab_reg = st.tabs(["🔑 Accedi", "📝 Registrati"])
            
            with tab_login:
                with st.form("login_form_db"):
                    email_input = st.text_input("Email di accesso").lower().strip()
                    password_input = st.text_input("Password", type="password")
                    submit_login = st.form_submit_button("Accedi", use_container_width=True)
                    
                    if submit_login:
                        user_data = get_utente_db(email_input)
                        if user_data and user_data["password"] == password_input:
                            if user_data["is_active"]:
                                st.session_state.logged_in = True
                                st.session_state.username = email_input
                                st.session_state.is_admin = user_data["is_admin"]
                                st.query_params["user"] = email_input 
                                try: cookie_controller.set('nutrilab_user', email_input, max_age=2592000)
                                except Exception: pass
                                st.success(f"✅ Bentornato {user_data['nome']}!")
                                st.rerun()
                            else:
                                st.error("⏳ Il tuo account è in attesa di approvazione da parte dell'amministratore.")
                        else:
                            st.error("❌ Email o password errati.")
            
            with tab_reg:
                with st.form("reg_form_db"):
                    st.write("Crea il tuo account per accedere al diario.")
                    new_email = st.text_input("La tua Email").lower().strip()
                    new_nome = st.text_input("Il tuo Nome (come vuoi essere chiamato)")
                    new_pass = st.text_input("Scegli una Password", type="password")
                    submit_reg = st.form_submit_button("Invia Richiesta di Registrazione", type="primary", use_container_width=True)
                    
                    if submit_reg:
                        if not new_email or not new_pass or not new_nome:
                            st.warning("⚠️ Compila tutti i campi.")
                        elif "@" not in new_email or "." not in new_email:
                            st.error("⚠️ Inserisci un indirizzo email valido.")
                        else:
                            existing = get_utente_db(new_email)
                            if existing:
                                st.error("⚠️ Questa Email è già registrata. Vai alla scheda di accesso.")
                            else:
                                conn = get_conn()
                                try:
                                    with conn.engine.begin() as e:
                                        query = text("INSERT INTO utenti (email, password, nome, is_admin, is_active) VALUES (:e, :p, :n, FALSE, FALSE)")
                                        e.execute(query, {"e": new_email, "p": new_pass, "n": new_nome.title()})
                                    st.success("✅ Registrazione completata! Vincenzo dovrà approvare il tuo account prima che tu possa entrare.")
                                except Exception as ex:
                                    st.error(f"Errore di connessione al database: {ex}")
        st.stop()
