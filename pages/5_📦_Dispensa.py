import streamlit as st
import pandas as pd
from services.db import (
    get_conn, get_current_macros_db,
    get_dispensa_utente, aggiungi_item_dispensa, salva_modifiche_dispensa
)
from components.nav import render_top_nav

st.set_page_config(page_title="NutriLab24", layout="wide")

# # 1. Controllo di sicurezza centralizzato
from components.auth import require_login
require_login()

# 🧭 VISUALIZZA LA NAVIGAZIONE SUPERIORE
render_top_nav("Dispensa")

USER_ID = st.session_state.username
MACROS_DB = get_current_macros_db()

st.title("📦 La tua Dispensa")
st.markdown("#### *Gestisci i tuoi ingredienti a casa e monitora le scorte automaticamente.* 🥫")
st.write("")

# Recupero Dispensa tramite SQL
dispensa_user = get_dispensa_utente(USER_ID)

c_add1, c_add2, c_add3 = st.columns([2, 1, 1])
with c_add1:
    nuovo_ing = st.selectbox("Aggiungi prodotto alla dispensa:", ["-- Seleziona --"] + sorted(list(MACROS_DB.keys())))
with c_add2:
    nuova_qta = st.number_input("Quantità iniziale:", min_value=0.0, step=50.0, value=0.0)
with c_add3:
    st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
    if st.button("➕ Aggiungi alla Dispensa", use_container_width=True):
        if nuovo_ing != "-- Seleziona --":
            if dispensa_user.empty or (nuovo_ing not in dispensa_user['Nome'].values):
                unita_def = MACROS_DB[nuovo_ing][8] 
                # Salvataggio tramite query SQL strutturata
                success = aggiungi_item_dispensa(USER_ID, nuovo_ing, nuova_qta, unita_def, monitora=True)
                if success:
                    st.success(f"✅ {nuovo_ing} aggiunto in dispensa!")
                    st.rerun()
                else:
                    st.error("Errore durante l'aggiunta in dispensa.")
            else:
                st.warning("Il prodotto è già in dispensa. Modifica la quantità dalla tabella qui sotto.")

st.divider()

if not dispensa_user.empty:
    st.write("✏️ **Modifica le tue scorte:** Clicca sulla tabella per cambiare le quantità a mano o attivare/disattivare il monitoraggio. Se il monitoraggio è attivo (☑️), l'app scalerà in automatico la quantità quando inserisci un pasto nel Diario.")
    
    df_editor = dispensa_user[['Nome', 'Quantita', 'Unita', 'Monitora']].copy()
    df_editor['Monitora'] = df_editor['Monitora'].astype(bool)
    
    edited_df = st.data_editor(
        df_editor,
        column_config={
            "Nome": st.column_config.TextColumn("Prodotto", disabled=True),
            "Quantita": st.column_config.NumberColumn("Quantità Rimanente", min_value=0.0, format="%.1f"),
            "Unita": st.column_config.TextColumn("Unità", disabled=True),
            "Monitora": st.column_config.CheckboxColumn("Sottrai in automatico dal Diario?")
        },
        hide_index=True,
        use_container_width=True,
        key="editor_dispensa"
    )
    
    if st.button("💾 Salva Modifiche Dispensa", type="primary"):
        with st.spinner("Aggiornamento scorte..."):
            # Aggiornamento massivo via SQL
            success = salva_modifiche_dispensa(USER_ID, edited_df)
            if success:
                st.success("✅ Dispensa aggiornata!")
                st.rerun()
            else:
                st.error("Errore durante il salvataggio della dispensa.")
else:
    st.info("La tua dispensa è vuota. Aggiungi i prodotti che vuoi tenere sotto controllo!")