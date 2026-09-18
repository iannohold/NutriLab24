import streamlit as st
import pandas as pd
from sqlalchemy import text
from services.db import (
    get_conn, ADMIN_ID, get_current_macros_db, 
    salva_su_cloud, elimina_da_cloud, cerca_alimento_web, cerca_locale
)
from components.nav import render_top_nav

# # 1. Controllo di sicurezza centralizzato
from components.auth import require_login
require_login()

# 🧭 VISUALIZZA LA NAVIGAZIONE SUPERIORE
render_top_nav("Database")

USER_ID = st.session_state.username
IS_ADMIN = st.session_state.get("is_admin", False)
conn = get_conn()
MACROS_DB = get_current_macros_db()

st.title("🗄️ Database Prodotti")
st.markdown("#### *Gestisci i tuoi ingredienti, consulta la lista e importa dal web.* 🛒")
st.write("")

# Lettura mirata della tabella macros via SQL
try:
    df_db = conn.query("SELECT * FROM macros", ttl=600)
    if not df_db.empty:
        df_db.columns = [c.lower() for c in df_db.columns]
        if 'user_id' not in df_db.columns: 
            df_db['user_id'] = ADMIN_ID
    else:
        df_db = pd.DataFrame(columns=["nome", "user_id"])
except:
    df_db = pd.DataFrame(columns=["nome", "user_id"])

azione_db = st.radio("Scegli un'azione:", [
    "📋 Archivio e Gestione Prodotti", 
    "➕ Aggiungi Nuovo (Web / Manuale)", 
    "🗂️ Duplica Esistente"
], horizontal=True)

st.divider()

if azione_db == "📋 Archivio e Gestione Prodotti":
    st.markdown("### ✏️ Cerca e Modifica al volo")
    prodotto_mod = st.selectbox("Cerca qui il prodotto da gestire:", ["-- Seleziona --"] + sorted(list(MACROS_DB.keys())), key="sel_mod_db")
    
    if prodotto_mod != "-- Seleziona --":
        cal_m, p_m, c_m, f_m, fib_m, sat_m, var_m, peso_m, unita_m = MACROS_DB[prodotto_mod]
        
        is_global = not df_db[(df_db['nome'].str.lower() == prodotto_mod.lower()) & (df_db['user_id'] == ADMIN_ID)].empty
        can_edit = IS_ADMIN or not is_global
        
        if not can_edit:
            st.error("🔒 **Prodotto di Nutrilab.** Non hai i permessi per modificarlo o eliminarlo. Se vuoi personalizzarlo, vai nella scheda 'Duplica Esistente'.")
        
        st.write("")
        c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns([1.5, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1, 1, 1.2])
        
        mod_n = c1.text_input("Nome", value=prodotto_mod, key="mod_n", disabled=not can_edit)
        mod_cal = c2.number_input("Cal", value=float(cal_m), step=1.0, key="mod_cal", disabled=not can_edit)
        mod_c = c3.number_input("Carb", value=float(c_m), step=0.1, key="mod_c", disabled=not can_edit)
        mod_p = c4.number_input("Prot", value=float(p_m), step=0.1, key="mod_p", disabled=not can_edit)
        mod_f = c5.number_input("Gras", value=float(f_m), step=0.1, key="mod_f", disabled=not can_edit)
        mod_sat = c6.number_input("Sat", value=float(sat_m), step=0.1, key="mod_sat", disabled=not can_edit)
        mod_fib = c7.number_input("Fib", value=float(fib_m), step=0.1, key="mod_fib", disabled=not can_edit)
        mod_var = c8.number_input("% V.Cott", value=float(var_m), step=1.0, key="mod_var", disabled=not can_edit)
        mod_peso = c9.number_input("Peso 1pz", value=float(peso_m), step=1.0, key="mod_peso", disabled=not can_edit)
        
        idx_u_mod = ["g", "ml", "pz"].index(unita_m) if unita_m in ["g", "ml", "pz"] else 0
        mod_unita = c10.selectbox("Unità Default", options=["g", "ml", "pz"], index=idx_u_mod, key="mod_udef", disabled=not can_edit)
        
        if can_edit:
            st.write("")
            col_save, col_del = st.columns(2)
            if col_save.button("💾 Aggiorna Modifiche", type="primary", use_container_width=True):
                with st.spinner("Aggiornamento in corso..."):
                    if mod_n.strip().lower() != prodotto_mod.lower():
                        elimina_da_cloud(prodotto_mod)
                    salva_su_cloud(mod_n, mod_cal, mod_p, mod_c, mod_f, mod_sat, mod_fib, mod_var, mod_peso, mod_unita)
                    st.success("✅ Prodotto aggiornato con successo!")
                    st.rerun()
                    
            if col_del.button("🗑️ Elimina Prodotto", type="secondary", use_container_width=True):
                st.session_state.confirm_del_prod = prodotto_mod
                
            if st.session_state.get('confirm_del_prod') == prodotto_mod:
                st.warning(f"⚠️ Sei sicuro di voler eliminare definitivamente '{prodotto_mod}' dal tuo archivio?")
                cy, cn = st.columns(2)
                if cy.button("🚨 Sì, Elimina", type="primary"):
                    with st.spinner("Eliminazione in corso..."):
                        successo = elimina_da_cloud(prodotto_mod)
                        st.session_state.confirm_del_prod = None
                        if successo: st.success("✅ Prodotto eliminato!")
                        else: st.error("Errore nell'eliminazione.")
                        st.rerun()
                if cn.button("❌ Annulla"):
                    st.session_state.confirm_del_prod = None
                    st.rerun()
    
    st.divider()
    st.markdown("### 📊 Panoramica del Database")
    st.write("Consulta tutti i prodotti disponibili. Clicca sulle intestazioni per ordinare dal maggiore al minore e viceversa.")
    
    lista_view = []
    for n, macros in MACROS_DB.items():
        cal, p, c, f, fib, sat, var, pz_w, u_def = macros
        match_db = df_db[df_db['nome'].str.lower() == n.lower()] if not df_db.empty else pd.DataFrame()
        user_owner = match_db['user_id'].iloc[0] if not match_db.empty else ADMIN_ID
        proprietario = "🌍 Nutrilab" if user_owner == ADMIN_ID else "👤 Personale"
        
        lista_view.append({
            "Nome Prodotto": n, "Calorie": cal, "Carboidrati": c, "Proteine": p, 
            "Grassi": f, "Unità": u_def, "Peso 1pz": pz_w, "% Cottura": var, "Proprietario": proprietario
        })
        
    st.dataframe(pd.DataFrame(lista_view), use_container_width=True, hide_index=True)

elif azione_db == "➕ Aggiungi Nuovo (Web / Manuale)":
    
    if st.session_state.get("do_clear_add"):
        for k in ["add_n", "add_cal", "add_c", "add_p", "add_f", "add_sat", "add_fib", "add_var", "add_peso"]:
            st.session_state[k] = 0.0 if k != "add_n" else ""
        st.session_state.add_udef = "g"
        st.session_state.do_clear_add = False
        
    if st.session_state.get("msg_add_ok"):
        st.success(st.session_state.msg_add_ok)
        st.session_state.msg_add_ok = ""
        
    st.markdown("### 🌐 Cerca sul Web o Inserisci Manualmente")
    c_search, c_btn, c_clear = st.columns([2.5, 1, 1])
    search_term = c_search.text_input("Cerca alimento (es. Mela, Pollo):", key="search_term_db")
    
    if c_btn.button("🔍 Cerca (Locale + Web)", use_container_width=True):
        if search_term:
            with st.spinner("Ricerca in corso..."):
                trovato_loc, n_loc, cal, p, c, f, fib, sat, var_cott, peso_pz, unita_def = cerca_locale(search_term)
                if trovato_loc:
                    st.session_state.add_n = n_loc; st.session_state.add_cal = float(cal); st.session_state.add_p = float(p)
                    st.session_state.add_c = float(c); st.session_state.add_f = float(f); st.session_state.add_fib = float(fib)
                    st.session_state.add_sat = float(sat); st.session_state.add_var = float(var_cott)
                    st.session_state.add_peso = float(peso_pz); st.session_state.add_udef = unita_def
                    st.success(f"✅ Prodotto già trovato nel Database Locale come '{n_loc}'!")
                else:
                    trovato_web, cal, p, c, f, fib, sat, var_cott, peso_pz, unita_def = cerca_alimento_web(search_term)
                    if trovato_web:
                        st.session_state.add_n = search_term.title(); st.session_state.add_cal = float(cal); st.session_state.add_p = float(p)
                        st.session_state.add_c = float(c); st.session_state.add_f = float(f); st.session_state.add_fib = float(fib)
                        st.session_state.add_sat = float(sat); st.session_state.add_var = 0.0
                        st.session_state.add_peso = 0.0; st.session_state.add_udef = "g"
                        st.success(f"🌐 Prodotto trovato sul Web! Verifica i dati prima di salvare.")
                    else:
                        st.session_state.add_n = search_term.title(); st.session_state.add_cal = 0.0; st.session_state.add_p = 0.0
                        st.session_state.add_c = 0.0; st.session_state.add_f = 0.0; st.session_state.add_fib = 0.0
                        st.session_state.add_sat = 0.0; st.session_state.add_var = 0.0; st.session_state.add_peso = 0.0; st.session_state.add_udef = "g"
                        st.warning("⚠️ Nessun risultato trovato. Compila manualmente.")

    if c_clear.button("🧹 Svuota Campi", use_container_width=True):
        st.session_state.do_clear_add = True
        st.rerun()

    st.write("")
    st.markdown("**Verifica e salva i valori (su 100g/ml) del nuovo prodotto:**")
    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns([1.5, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1, 1, 1.2])
    
    db_n = c1.text_input("Nome", key="add_n")
    db_cal = c2.number_input("Cal", step=1.0, key="add_cal")
    db_c = c3.number_input("Carb", step=0.1, key="add_c")
    db_p = c4.number_input("Prot", step=0.1, key="add_p")
    db_f = c5.number_input("Gras", step=0.1, key="add_f")
    db_sat = c6.number_input("Sat", step=0.1, key="add_sat")
    db_fib = c7.number_input("Fib", step=0.1, key="add_fib")
    db_var = c8.number_input("% V.Cott", step=1.0, key="add_var")
    db_peso_pz = c9.number_input("Peso 1pz", step=1.0, key="add_peso")
    db_unita_def = c10.selectbox("Unità Default", options=["g", "ml", "pz"], key="add_udef")

    st.write("")
    if st.button("➕ Salva nel Database", type="primary"):
        if db_n:
            esiste_gia = db_n.strip().lower() in [k.lower() for k in MACROS_DB.keys()]
            if esiste_gia:
                st.session_state.show_dup_warning = db_n
            else:
                with st.spinner("Salvataggio in Cloud..."):
                    success = salva_su_cloud(db_n, db_cal, db_p, db_c, db_f, db_sat, db_fib, db_var, db_peso_pz, db_unita_def)
                    if success:
                        st.session_state.msg_add_ok = f"✅ '{db_n}' salvato nel tuo database personale!"
                        st.session_state.do_clear_add = True
                        st.rerun()
        else: 
            st.warning("Inserisci il nome del prodotto prima di salvare.")

    if st.session_state.get("show_dup_warning") == db_n:
        st.error(f"⚠️ Attenzione! Esiste già un prodotto chiamato **'{db_n}'** nel database.")
        cy, cn = st.columns(2)
        if cy.button("🚨 Sì, Sovrascrivi", type="primary"):
            with st.spinner("Sovrascrittura in Cloud..."):
                salva_su_cloud(db_n, db_cal, db_p, db_c, db_f, db_sat, db_fib, db_var, db_peso_pz, db_unita_def)
                st.session_state.show_dup_warning = None
                st.session_state.msg_add_ok = "✅ Prodotto aggiornato e salvato!"
                st.session_state.do_clear_add = True
                st.rerun()
        if cn.button("❌ No, annulla e cambia nome"):
            st.session_state.show_dup_warning = None
            st.rerun()

elif azione_db == "🗂️ Duplica Esistente":
    if st.session_state.get("do_clear_dup"):
        for k in ["dup_n", "dup_cal", "dup_c", "dup_p", "dup_f", "dup_sat", "dup_fib", "dup_var", "dup_peso"]:
            st.session_state[k] = 0.0 if k != "dup_n" else ""
        st.session_state.dup_udef = "g"
        st.session_state.do_clear_dup = False
        
    if st.session_state.get("msg_dup_ok"):
        st.success(st.session_state.msg_dup_ok)
        st.session_state.msg_dup_ok = ""
        
    st.markdown("### 🗂️ Usa un prodotto esistente come base")
    c_dup, c_btn_dup = st.columns([3, 1])
    prodotto_da_duplicare = c_dup.selectbox("Seleziona un prodotto dal database:", ["-- Seleziona --"] + sorted(list(MACROS_DB.keys())), key="dup_db_sel")
    
    with c_btn_dup:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Carica Valori Originali", use_container_width=True):
            if prodotto_da_duplicare != "-- Seleziona --":
                cal, p, c, f, fib, sat, var, peso_db, unita_db = MACROS_DB[prodotto_da_duplicare]
                
                st.session_state.dup_n = prodotto_da_duplicare + " (Personalizzato)"
                st.session_state.dup_cal = float(cal); st.session_state.dup_p = float(p)
                st.session_state.dup_c = float(c); st.session_state.dup_f = float(f)
                st.session_state.dup_sat = float(sat); st.session_state.dup_fib = float(fib)
                st.session_state.dup_var = float(var); st.session_state.dup_peso = float(peso_db); st.session_state.dup_udef = unita_db
                
                st.success(f"✅ Valori di '{prodotto_da_duplicare}' caricati. Modifica il nome e salva la tua variante!")
            else: 
                st.warning("Seleziona prima un prodotto dalla tendina.")

    st.write("")
    st.markdown("**Modifica i valori e salva come nuovo prodotto**")
    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns([1.5, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1, 1, 1.2])
    
    db_n = c1.text_input("Nome Variante", key="dup_n")
    db_cal = c2.number_input("Cal", step=1.0, key="dup_cal")
    db_c = c3.number_input("Carb", step=0.1, key="dup_c")
    db_p = c4.number_input("Prot", step=0.1, key="dup_p")
    db_f = c5.number_input("Gras", step=0.1, key="dup_f")
    db_sat = c6.number_input("Sat", step=0.1, key="dup_sat")
    db_fib = c7.number_input("Fib", step=0.1, key="dup_fib")
    db_var = c8.number_input("% V.Cott", step=1.0, key="dup_var")
    db_peso_pz = c9.number_input("Peso 1pz", step=1.0, key="dup_peso")
    db_unita_def = c10.selectbox("Unità Default", options=["g", "ml", "pz"], key="dup_udef")

    st.write("")
    if st.button("➕ Salva Nuova Variante", type="primary"):
        if db_n and " (Personalizzato)" not in db_n:
            with st.spinner("Salvataggio in Cloud..."):
                success = salva_su_cloud(db_n, db_cal, db_p, db_c, db_f, db_sat, db_fib, db_var, db_peso_pz, db_unita_def)
                if success: 
                    st.session_state.msg_dup_ok = f"✅ Variante '{db_n}' salvata correttamente!"
                    st.session_state.do_clear_dup = True
                    st.rerun()
        elif " (Personalizzato)" in db_n:
            st.error("⚠️ Rinomina il prodotto eliminando la scritta '(Personalizzato)' prima di salvare.")
        else: 
            st.warning("Inserisci il nome della variante.")