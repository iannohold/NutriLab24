import streamlit as st
import pandas as pd
from sqlalchemy import text
from services.db import get_conn, ADMIN_ID
from components.nav import render_top_nav
from components.auth import require_login

st.set_page_config(page_title="Amministrazione - NutriLab24", layout="wide")

require_login()

if st.session_state.get("username", "").lower() != ADMIN_ID.lower():
    st.error("⛔ Accesso negato: area riservata alla direzione.")
    st.stop()

render_top_nav("Amministrazione Sistema")
st.title("🛠️ Pannello di Controllo Accessi")
st.markdown("#### *Gestisci le registrazioni, blocca utenti o creali manualmente.* 🚦")

conn = get_conn()

def get_utenti():
    try:
        return conn.query("SELECT email, nome, is_active FROM utenti ORDER BY is_active ASC, email ASC", ttl=0)
    except: 
        return pd.DataFrame()

def cambia_stato(email, stato):
    try:
        with conn.engine.begin() as e:
            e.execute(text("UPDATE utenti SET is_active = :s WHERE email = :e"), {"s": stato, "e": email})
        st.cache_data.clear()
    except Exception as ex: 
        st.error(ex)

df_utenti = get_utenti()

tab_attesa, tab_attivi, tab_crea = st.tabs(["🔔 Richieste in Attesa", "🟢 Utenti Attivi", "➕ Crea Utente Manualmente"])

with tab_attesa:
    if df_utenti.empty:
        st.info("⚠️ Tabella utenti non trovata o vuota.")
    else:
        da_approvare = df_utenti[df_utenti['is_active'] == False]
        if da_approvare.empty:
            st.success("✅ Nessuna nuova richiesta di registrazione in sospeso.")
        else:
            for _, r in da_approvare.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.warning(f"👤 **{r['nome']}** (Email: `{r['email']}`) ha richiesto l'accesso.")
                if c2.button("🟢 Approva", key=f"app_{r['email']}", type="primary", use_container_width=True):
                    cambia_stato(r['email'], True)
                    st.rerun()

with tab_attivi:
    if not df_utenti.empty:
        attivi = df_utenti[df_utenti['is_active'] == True]
        for _, r in attivi.iterrows():
            c1, c2 = st.columns([3, 1])
            if r['email'].lower() == ADMIN_ID.lower():
                c1.success(f"👑 **{r['nome']}** (Email: `{r['email']}`) - Admin")
                c2.button("🔒 Intoccabile", disabled=True, key=f"dis_{r['email']}", use_container_width=True)
            else:
                c1.info(f"👤 **{r['nome']}** (Email: `{r['email']}`)")
                if c2.button("🔴 Sospendi", key=f"sos_{r['email']}", use_container_width=True):
                    cambia_stato(r['email'], False)
                    st.rerun()

with tab_crea:
    st.write("Crea un account direttamente dal sistema (sarà già attivo e approvato).")
    with st.form("form_creazione_manuale"):
        new_email = st.text_input("Email Utente").lower().strip()
        new_nome = st.text_input("Nome Visualizzato")
        new_pass = st.text_input("Password", type="password")
        
        submitted = st.form_submit_button("💾 Salva e Attiva Utente", type="primary")
        
        if submitted:
            if not new_email or not new_nome or not new_pass:
                st.warning("⚠️ Compila tutti i campi.")
            elif not df_utenti.empty and new_email in df_utenti['email'].values:
                st.error("⚠️ Questa email esiste già nel database.")
            else:
                try:
                    with conn.engine.begin() as e:
                        query = text("INSERT INTO utenti (email, password, nome, is_admin, is_active) VALUES (:e, :p, :n, FALSE, TRUE)")
                        e.execute(query, {"e": new_email, "p": new_pass, "n": new_nome.title()})
                    st.success(f"✅ L'utente **{new_nome}** è stato creato ed è pronto ad accedere!")
                    st.cache_data.clear()
                except Exception as ex:
                    st.error(f"Errore: {ex}")