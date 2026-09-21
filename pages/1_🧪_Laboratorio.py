import streamlit as st
import pandas as pd
import uuid
import io
import re
from fpdf import FPDF
from components.nav import render_top_nav

st.set_page_config(page_title="NutriLab24", layout="wide")

# 1. Controllo di sicurezza centralizzato
from components.auth import require_login
require_login()

# 🧭 VISUALIZZA LA NAVIGAZIONE SUPERIORE
render_top_nav("Laboratorio Ricette")

# Importiamo dal nostro backend
from services.db import (
    get_conn, ADMIN_ID, RUOLI_LIST, CATEGORIE_LIST,
    get_current_macros_db, salva_su_cloud, get_macros_and_match,
    salva_bozza_locale, carica_bozza_locale, svuota_laboratorio,
    process_ingredient_list, ricalcola_ingrediente, ripristina_ricetta,
    get_ricette_utente_e_community, salva_ricetta_cloud, elimina_ricetta_cloud
)

# ==========================================
# ⚙️ 2. INIZIALIZZAZIONE VARIABILI DI PAGINA
# ==========================================
USER_ID = st.session_state.username
IS_ADMIN = st.session_state.get("is_admin", False)
MACROS_DB = get_current_macros_db()
conn = get_conn()

stati_iniziali = [
    ('nome_ricetta', "Nuova Ricetta"), ('tipo_ricetta', []), ('procedimento', ""), ('ingredients', []), 
    ('ing_scelto', "-- Seleziona --"), ('input_qty', None), ('input_unit', "g"), ('input_pz_w', 0.0), 
    ('input_ruolo', "Impasto"), ('input_cal', None), ('input_p', None), ('input_c', None), ('input_f', None), 
    ('input_fib', None), ('input_sat', None), ('input_sale', None), ('new_name_free', ""), ('new_name_manual', ""),
    ('riposo', ""), ('porzioni', 1), ('richiede_cottura', False), ('m_cot', "Forno"), ('t_cot', ""),
    ('temp_cot', 180), ('qta_teglia', 100.0), ('tipo_resa', "Usa % di stima"), ('var_cottura', -15.0), ('peso_cotto_reale', 85.0),
    ('confirm_del', "")
]

for key, default in stati_iniziali:
    if key not in st.session_state: st.session_state[key] = default

if "bozza_recuperata" not in st.session_state:
    carica_bozza_locale()
    st.session_state.bozza_recuperata = True

# ==========================================
# 🧪 3. INTERFACCIA LABORATORIO
# ==========================================
st.title("🧪 Laboratorio Ricette")
st.markdown("#### *Progetta, bilancia e cucina le tue idee.* 💡 ⚖️ 🍳")
st.write("")

nome_ric_display = st.session_state.get('nome_ricetta', '').strip()
if nome_ric_display and nome_ric_display != "Nuova Ricetta":
    st.markdown(f"<h2 style='color: #FF4B4B;'>{nome_ric_display}</h2>", unsafe_allow_html=True)
    st.write("")

col_titolo, col_svuota, col_ricarica = st.columns([3, 1, 1])
with col_titolo:
    st.markdown("### :green[1. Aggiungi Ingredienti]")
with col_svuota:
    st.button("🧹 Svuota Laboratorio", on_click=svuota_laboratorio, use_container_width=True)
with col_ricarica:
    if st.button("🔄 Ricarica Database", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- TABS INSERIMENTO ---
tab_manuale, tab_cloud, tab_excel, tab_web, tab_testo = st.tabs(["✍️ Singolo", "☁️ Da Cloud", "📁 Da Excel/CSV", "🌐 Link Web", "📝 Testo"])

with tab_manuale:
    st.write("Inserisci manualmente o cerca nel database web.")
    opzioni = ["-- Seleziona --", "Altro (Ricerca Libera su Web)", "Altro (Inserimento Manuale)"] + sorted(list(MACROS_DB.keys()))
    
    def update_macros_from_selection():
        scelta = st.session_state.get("ing_scelto", "-- Seleziona --")
        if scelta in ["-- Seleziona --", "Altro (Inserimento Manuale)", "Altro (Ricerca Libera su Web)"]:
            st.session_state.input_cal = None; st.session_state.input_p = None; st.session_state.input_c = None
            st.session_state.input_f = None; st.session_state.input_sat = None; st.session_state.input_fib = None
            st.session_state.input_sale = None; st.session_state.input_unit = 'g'; st.session_state.input_pz_w = 0.0
        else:
            m_name, cal, p, c, f, fib, sat, sale, var_cott, peso_pz, unita_def, m_marca, m_tipo = get_macros_and_match(scelta)
            st.session_state.input_cal = float(cal); st.session_state.input_p = float(p); st.session_state.input_c = float(c)
            st.session_state.input_f = float(f); st.session_state.input_sat = float(sat); st.session_state.input_fib = float(fib)
            st.session_state.input_sale = float(sale); st.session_state.input_unit = unita_def; st.session_state.input_pz_w = peso_pz

    def fetch_macros_from_web_btn():
        from services.db import cerca_alimento_web
        new_name = st.session_state.get("new_name_free", "")
        if new_name:
            risultato = cerca_alimento_web(new_name)
            if risultato[0]:
                st.session_state.input_cal = float(risultato[1]); st.session_state.input_p = float(risultato[2])
                st.session_state.input_c = float(risultato[3]); st.session_state.input_f = float(risultato[4])
                st.session_state.input_sat = float(risultato[6]); st.session_state.input_fib = float(risultato[5])
                st.session_state.input_sale = float(risultato[7]); st.session_state.input_marca = risultato[11]
                if new_name.isdigit(): st.session_state.input_ean = new_name
                st.toast("✅ Prodotto trovato! Parametri compilati in basso.", icon="🎯")
            else:
                st.toast("❌ Nessun risultato trovato nel database mondiale.", icon="🚫")

    st.selectbox("Cerca ingrediente", options=opzioni, key="ing_scelto", on_change=update_macros_from_selection)
    if st.session_state.get("ing_scelto") == "Altro (Ricerca Libera su Web)":
        c_t, c_b = st.columns([3, 1])
        c_t.text_input("Nome o EAN da cercare online:", key="new_name_free")
        c_b.write(""); c_b.button("🔍 Cerca Online", on_click=fetch_macros_from_web_btn)
    elif st.session_state.get("ing_scelto") == "Altro (Inserimento Manuale)":
        st.text_input("Nome nuovo ingrediente:", key="new_name_manual")

    c_mrc, c_tip, c_ean = st.columns([1.5, 1.5, 1])
    val_marca = c_mrc.text_input("Marca (opzionale)", key="input_marca", value=st.session_state.get("input_marca", ""))
    val_tipologia = c_tip.selectbox("Tipologia", ["Materia Prima", "Prodotto Confezionato", "Integratore", "Ricetta Personale"], key="input_tipologia")
    val_ean = c_ean.text_input("Codice EAN", key="input_ean", value=st.session_state.get("input_ean", ""))

    c_q, c_u, c_r, c_pw = st.columns([1, 1, 1, 1.5])
    qty = c_q.number_input("Quantità", min_value=0.0, step=1.0, key="input_qty", value=None)
    unit = c_u.selectbox("Unità", options=["g", "ml", "pz"], key="input_unit")
    ruolo = c_r.selectbox("Utilizzo", options=RUOLI_LIST, key="input_ruolo")
    
    if unit == "pz":
        default_pz_lab = 0.0
        scelta = st.session_state.get("ing_scelto", "-- Seleziona --")
        if scelta not in ["-- Seleziona --", "Altro (Inserimento Manuale)", "Altro (Ricerca Libera su Web)"] and scelta in MACROS_DB:
            default_pz_lab = MACROS_DB[scelta][8]
        pz_w = c_pw.number_input(f"Peso 1 pz (g) [da DB]", min_value=0.0, step=1.0, value=float(default_pz_lab), key="input_pz_w")
    else: pz_w = 0.0

    c_cal, c_c, c_p, c_f, c_s, c_fib, c_sal = st.columns(7)
    val_cal = c_cal.number_input("Calorie", key="input_cal", step=1.0, value=st.session_state.get("input_cal", None))
    val_c = c_c.number_input("Carb.", key="input_c", step=0.1, value=st.session_state.get("input_c", None))
    val_p = c_p.number_input("Prot.", key="input_p", step=0.1, value=st.session_state.get("input_p", None))
    val_f = c_f.number_input("Grassi", key="input_f", step=0.1, value=st.session_state.get("input_f", None))
    val_sat = c_s.number_input("Saturi", key="input_sat", step=0.1, value=st.session_state.get("input_sat", None))
    val_fib = c_fib.number_input("Fibre", key="input_fib", step=0.1, value=st.session_state.get("input_fib", None))
    val_sale = c_sal.number_input("Sale", key="input_sale", step=0.1, value=st.session_state.get("input_sale", None))

    def aggiungi_singolo():
        scelta = st.session_state.get("ing_scelto", "-- Seleziona --")
        act = st.session_state.get("new_name_free", "") if scelta == "Altro (Ricerca Libera su Web)" else (st.session_state.get("new_name_manual", "") if scelta == "Altro (Inserimento Manuale)" else scelta)
        if qty is not None and qty > 0 and act and act != "-- Seleziona --":
            m_name, m_cal, m_p, m_c, m_f, m_fib, m_sat, m_sale, m_var, m_pesopz, m_unita, m_marca, m_tipo = get_macros_and_match(act)
            st.session_state.ingredients.append({
                "id": uuid.uuid4().hex, "nome": act.title(), "matched_name": m_name, "quantita": float(qty), "unita": unit, 
                "peso_pz": float(pz_w), "peso": float(qty) * pz_w if unit == 'pz' else float(qty), 
                "ruolo": st.session_state.get("input_ruolo", "Impasto"),
                "cal_100": float(st.session_state.get("input_cal") or 0.0),
                "prot_100": float(st.session_state.get("input_p") or 0.0), 
                "carb_100": float(st.session_state.get("input_c") or 0.0), 
                "fat_100": float(st.session_state.get("input_f") or 0.0), 
                "sat_100": float(st.session_state.get("input_sat") or 0.0),
                "fib_100": float(st.session_state.get("input_fib") or 0.0),
                "sale_100": float(st.session_state.get("input_sale") or 0.0),
                "marca": st.session_state.get("input_marca", "").strip(),
                "tipologia": st.session_state.get("input_tipologia", "Materia Prima"),
                "ean": st.session_state.get("input_ean", "").strip()
            })
            st.session_state.input_qty = None; st.session_state.ing_scelto = "-- Seleziona --"; st.session_state.input_ruolo = "Impasto"
            st.session_state.input_marca = ""; st.session_state.input_ean = ""
        salva_bozza_locale()

    can_add = True
    if unit == "pz" and pz_w <= 0:
        st.warning("⚠️ Hai selezionato 'pz' ma il peso medio è 0. Inserisci il peso per pezzo.")
        can_add = False

    st.button("➕ Aggiungi", type="primary", on_click=aggiungi_singolo, disabled=(qty is None or qty <= 0 or not can_add))

with tab_cloud:
    st.write("Gestisci le tue ricette o esplora quelle della community.")
    try:
        df_ricette = get_ricette_utente_e_community(USER_ID, ADMIN_ID)
        sub_personale, sub_community = st.tabs(["📕 Il mio Ricettario", "🌍 Ricette Community"])
        
        with sub_personale:
            df_mie = df_ricette[df_ricette['User_ID'] == USER_ID]
            if not df_mie.empty:
                ricette_list = [f"{row['Nome Ricetta']} [{row['Categoria']}]" for _, row in df_mie.iterrows()]
                ric_scelta = st.selectbox("Le tue ricette:", ["-- Seleziona --"] + ricette_list, key="sel_mie")
                
                c_btn_imp, c_btn_del = st.columns(2)
                
                if c_btn_imp.button("📥 Importa nel Laboratorio", use_container_width=True) and ric_scelta != "-- Seleziona --":
                    st.session_state.confirm_del = "" 
                    with st.spinner("Caricamento..."):
                        nome_sel = ric_scelta.rsplit(" [", 1)[0]
                        json_dati = df_mie[df_mie['Nome Ricetta'] == nome_sel]['Dati JSON'].iloc[0]
                        df_rec = pd.read_json(io.StringIO(json_dati))
                        ripristina_ricetta(df_rec)
                        st.success("✅ Ricetta caricata nel laboratorio!")
                        st.rerun()
                        
                if c_btn_del.button("🗑️ Elimina", type="secondary", use_container_width=True) and ric_scelta != "-- Seleziona --":
                    st.session_state.confirm_del = ric_scelta 

                if st.session_state.get("confirm_del") == ric_scelta and ric_scelta != "-- Seleziona --":
                    st.warning("⚠️ Sei sicuro di voler eliminare questa ricetta?")
                    c_yes, c_no = st.columns(2)
                    if c_yes.button("🚨 Conferma", type="primary"):
                        nome_sel = ric_scelta.rsplit(" [", 1)[0]
                        success = elimina_ricetta_cloud(USER_ID, nome_sel)
                        if success:
                            st.session_state.confirm_del = ""
                            st.success("Ricetta eliminata.")
                            st.rerun()
                    if c_no.button("❌ Annulla"):
                        st.session_state.confirm_del = ""
                        st.rerun()
            else: st.info("Non hai ancora salvato nessuna ricetta nel tuo ricettario personale.")

        with sub_community:
            df_comm = df_ricette[(df_ricette['Condivisa'] == True) & (df_ricette['User_ID'] != USER_ID)]
            if not df_comm.empty:
                comm_list = [f"{row['Nome Ricetta']} (di {row['User_ID']}) [{row['Categoria']}]" for _, row in df_comm.iterrows()]
                ric_comm_scelta = st.selectbox("Esplora le ricette:", ["-- Seleziona --"] + comm_list, key="sel_comm")
                
                if ric_comm_scelta != "-- Seleziona --":
                    nome_comm_sel = ric_comm_scelta.rsplit(" (di ", 1)[0]
                    autore = ric_comm_scelta.split("(di ")[1].split(")")[0]
                    st.write(f"Vuoi aggiungere **{nome_comm_sel}** creata da *{autore}* al tuo ricettario?")
                    if st.button("⬇️ Salva nel mio Ricettario", type="primary", use_container_width=True):
                        with st.spinner("Importazione in corso..."):
                            riga_orig = df_comm[(df_comm['Nome Ricetta'] == nome_comm_sel) & (df_comm['User_ID'] == autore)].iloc[0]
                            new_name = nome_comm_sel
                            if not df_ricette[(df_ricette['Nome Ricetta'] == nome_comm_sel) & (df_ricette['User_ID'] == USER_ID)].empty:
                                new_name = nome_comm_sel + " (Importata)"
                            success = salva_ricetta_cloud(USER_ID, new_name, riga_orig['Categoria'], riga_orig['Dati JSON'], False)
                            if success:
                                st.success("✅ Ricetta importata!")
                                st.rerun()
            else: st.info("Nessuna ricetta condivisa dalla community al momento.")

    except Exception as e: st.error(f"Errore cloud: {e}")

with tab_excel:
    st.info("Carica un file CSV o Excel esportato da NutriLab")
    file_caricato = st.file_uploader("Scegli file", type=['xls', 'xlsx', 'csv'])
    if file_caricato and st.button("📥 Importa da File Esterno"):
        try:
            if file_caricato.name.endswith('.csv'): df = pd.read_csv(file_caricato)
            else: df = pd.read_excel(file_caricato)
            if 'Ricetta_Nome' in df.columns:
                ripristina_ricetta(df)
                st.success("✅ Ricetta ripristinata dal file con successo!")
                st.rerun()
            else:
                st.session_state.nome_ricetta = file_caricato.name.rsplit('.', 1)[0].replace('_', ' ').title()
                if file_caricato.name.endswith('.csv'): df = pd.read_csv(file_caricato, header=None)
                else: df = pd.read_excel(file_caricato, header=None)
                lines = [f"{str(r.iloc[0]).strip()},{float(r.iloc[1])},{str(r.iloc[2]).strip().lower() if len(r)>2 else ''}" for _, r in df.iterrows()]
                with st.spinner("Importazione in corso..."): aggiunti = process_ingredient_list(lines)
                st.success(f"{aggiunti} ingredienti generici importati!")
                st.rerun()
        except Exception as e: st.error(f"Errore nella lettura. {e}")

with tab_web:
    st.info("Incolla il link di un blog (es. GialloZafferano).")
    url_input = st.text_input("Link della ricetta (URL):")
    if st.button("🌐 Importa da Link Web") and url_input:
        try:
            from recipe_scrapers import scrape_me
            scraper = scrape_me(url_input)
            st.session_state.nome_ricetta, st.session_state.procedimento = scraper.title(), scraper.instructions()
            with st.spinner("Scraping in corso..."): aggiunti = process_ingredient_list(scraper.ingredients())
            st.success(f"Estrazione completata! {aggiunti} ingredienti trovati."); st.rerun()
        except Exception as e: st.error("Link non supportato o errore di connessione.")

with tab_testo:
    st.info("Formato testuale richiesto: **Nome Ingrediente, Quantità, Unità(opzionale)**.")
    testo_input = st.text_area("Incolla qui gli ingredienti (uno per riga):", height=150, placeholder="Es:\ndatteri, 100, g\nuova, 2")
    if st.button("📝 Analizza e Importa") and testo_input:
        with st.spinner("Ricerca ed estrazione..."): aggiunti = process_ingredient_list(testo_input.split('\n'))
        st.success(f"{aggiunti} ingredienti interpretati!"); st.rerun()

st.divider()

# ==========================================
# 📋 4. RIEPILOGO INGREDIENTI
# ==========================================
if st.session_state.ingredients:
    st.markdown("### :orange[2. Riepilogo Ingredienti]")
    
    col_h1, col_sel, col_desel, col_del = st.columns([2.5, 1.2, 1.2, 1.5])
    col_h1.write("Modifica i valori o salva i nuovi ingredienti nel Database in Cloud.")
    
    col_sel.button("☑️ Seleziona Tutti", on_click=lambda: [st.session_state.update({f"chk_del_{i['id']}": True}) for i in st.session_state.ingredients], use_container_width=True)
    col_desel.button("🔲 Deseleziona", on_click=lambda: [st.session_state.update({f"chk_del_{i['id']}": False}) for i in st.session_state.ingredients], use_container_width=True)
    if col_del.button("🗑️ Elimina Selezionati", type="primary", use_container_width=True):
        st.session_state.ingredients = [i for i in st.session_state.ingredients if not st.session_state.get(f"chk_del_{i['id']}", False)]
        salva_bozza_locale()
        st.rerun()
    
    for ing in st.session_state.ingredients:
        non_riconosciuto = (ing['cal_100'] == 0 and ing['prot_100'] == 0 and ing['carb_100'] == 0 and ing['fat_100'] == 0)
        fuzzy_matched = bool(not non_riconosciuto and ing.get('matched_name') and ing['nome'].strip().lower() != ing['matched_name'].lower())
        icona = "⚠️ [DA VERIFICARE]" if non_riconosciuto else "💡 [ASSOCIAZIONE]" if fuzzy_matched else "📌"
        
        ruolo_corr = ing.get('ruolo', 'Impasto')
        
        fattore = ing['peso'] / 100.0 if ing['unita'] != 'pz' else (ing['quantita'] * ing.get('peso_pz', 0.0)) / 100.0
        ing_cal = ing['cal_100'] * fattore
        ing_c = ing['carb_100'] * fattore
        ing_p = ing['prot_100'] * fattore
        ing_f = ing['fat_100'] * fattore
        
        # Titolo dell'expander pulito (senza peso e senza icone ai macro)
        titolo_expander = f"{icona} {ing['quantita']} {ing['unita']} di {ing['nome'].title()} • [{ruolo_corr}]"
        
        col_chk, col_exp = st.columns([0.05, 0.95])
        
        with col_chk:
            st.checkbox(" ", key=f"chk_del_{ing['id']}", label_visibility="collapsed")
            
        with col_exp:
            with st.expander(titolo_expander, expanded=bool(non_riconosciuto or fuzzy_matched)):
                # Seconda riga descrittiva visibile dentro l'espansore con peso e macro senza icone
                st.markdown(f"<small style='color: gray;'>⚖️ {ing['peso']:.1f}g &nbsp;|&nbsp; Kcal: {ing_cal:.0f} &nbsp;|&nbsp; C: {ing_c:.1f}g &nbsp;|&nbsp; P: {ing_p:.1f}g &nbsp;|&nbsp; G: {ing_f:.1f}g</small>", unsafe_allow_html=True)
                st.write("")

                if non_riconosciuto:
                    st.error("Prodotto non riconosciuto.")
                    c_fix, c_btn = st.columns([3, 1])
                    c_fix.selectbox("Sostituisci con prodotto salvato:", ["-- Scegli dal Database --"] + sorted(list(MACROS_DB.keys())), key=f"fix_sel_{ing['id']}")
                    def applica_fix(i_id, k):
                        sc = st.session_state.get(k)
                        if sc and sc != "-- Scegli dal Database --":
                            cal, p, c, f, fib, sat, sal, v, peso_db, unita_db, marca_db, tipo_db = MACROS_DB[sc]
                            for item in st.session_state.ingredients:
                                if item['id'] == i_id:
                                    item.update({'nome': sc, 'matched_name': sc, 'cal_100': cal, 'prot_100': p, 'carb_100': c, 'fat_100': f, 'sat_100': sat, 'fib_100': fib, 'sale_100': sal})
                                    st.session_state.update({f"n_{i_id}": sc, f"cal2_{i_id}": cal, f"p2_{i_id}": p, f"c2_{i_id}": c, f"f2_{i_id}": f, f"sat2_{i_id}": sat, f"fib2_{i_id}": fib, f"sale2_{i_id}": sal})
                                    item.update({'unita': unita_db, 'peso_pz': peso_db})
                                    st.session_state[f"u_{i_id}"] = unita_db
                                    item['peso'] = item['quantita'] * item.get('peso_pz',0.0) if item['unita']=='pz' else item['quantita']
                                    break
                    c_btn.write(""); c_btn.button("🔄 Applica", key=f"btn_fix_{ing['id']}", on_click=applica_fix, args=(ing['id'], f"fix_sel_{ing['id']}"))
                
                elif fuzzy_matched:
                    st.info(f"Ho associato **{ing['nome']}** a **{ing['matched_name']}**.")
                    c_f1, c_f2 = st.columns([3, 1]); c_f1.write(f"Vuoi aggiornare il nome e usare quello del database?")
                    def applica_rn(i_id, nm):
                        for it in st.session_state.ingredients:
                            if it['id'] == i_id: it['nome'] = nm; it['matched_name'] = nm; st.session_state[f"n_{i_id}"] = nm; break
                    c_f2.button("✅ Aggiorna Nome", key=f"btn_rn_{ing['id']}", on_click=applica_rn, args=(ing['id'], ing['matched_name']))

                st.text_input("Nome", value=ing['nome'], key=f"n_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                
                r1_1, r1_2, r1_r, r1_3 = st.columns([1, 1, 1, 1.5])
                r1_1.number_input("Quantità", value=float(ing['quantita']), key=f"q_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                r1_2.selectbox("Unità", options=["g", "ml", "pz"], index=["g", "ml", "pz"].index(ing['unita']), key=f"u_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                idx_ruolo = RUOLI_LIST.index(ruolo_corr) if ruolo_corr in RUOLI_LIST else 0
                r1_r.selectbox("Utilizzo", options=RUOLI_LIST, index=idx_ruolo, key=f"ruolo_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))

                if ing['unita'] == 'pz': 
                    r1_3.number_input("Peso 1 pz (g)", value=float(ing.get('peso_pz', 0.0)), key=f"pw_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                else: r1_3.write("")
                
                # Flag a comparsa per sbloccare la modifica dei macro su 100g
                modifica_macro_attiva = st.checkbox("✏️ Modifica i macronutrienti per questo prodotto (su 100g)", key=f"flag_mod_macro_{ing['id']}")
                
                if modifica_macro_attiva:
                    r2_cal, r2_c, r2_p, r2_3, r2_4, r2_5, r2_6 = st.columns(7)
                    r2_cal.number_input("Calorie", value=float(ing['cal_100']), step=1.0, key=f"cal2_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                    r2_c.number_input("Carb.", value=float(ing['carb_100']), step=0.1, key=f"c2_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                    r2_p.number_input("Prot.", value=float(ing['prot_100']), step=0.1, key=f"p2_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                    r2_3.number_input("Grass.", value=float(ing['fat_100']), step=0.1, key=f"f2_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                    r2_4.number_input("Saturi", value=float(ing['sat_100']), step=0.1, key=f"sat2_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                    r2_5.number_input("Fibre", value=float(ing['fib_100']), step=0.1, key=f"fib2_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                    r2_6.number_input("Sale", value=float(ing.get('sale_100', 0.0)), step=0.1, key=f"sale2_{ing['id']}", on_change=ricalcola_ingrediente, args=(ing['id'],))
                
                if ing['nome'].title() not in MACROS_DB:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("☁️ Salva nuovo prodotto nel Database", key=f"db_save_{ing['id']}", type="secondary"):
                        with st.spinner("Sincronizzazione..."):
                            success = salva_su_cloud(ing['nome'], ing['cal_100'], ing['prot_100'], ing['carb_100'], ing['fat_100'], ing['sat_100'], ing['fib_100'], ing.get('sale_100', 0.0), 0.0, float(ing.get('peso_pz', 0.0)), ing['unita'], ing.get('marca', ''), ing.get('tipologia', 'Materia Prima'), ing.get('ean', ''))
                        if success:
                            st.success(f"✅ {ing['nome'].title()} salvato!")
                            st.rerun()

                if st.button("🗑️ Rimuovi ingrediente", key=f"del_sn_{ing['id']}", type="secondary"):
                    st.session_state.ingredients = [it for it in st.session_state.ingredients if it['id'] != ing['id']]
                    salva_bozza_locale()
                    st.rerun()

    st.divider()

    # ==========================================
    # 🔥 5. COTTURA E RESA
    # ==========================================
    st.markdown("### :red[3. Cottura e Resa]")
    
    ruoli_stats = {r: {'w':0.0, 'cal':0.0, 'p':0.0, 'c':0.0, 'f':0.0, 's':0.0, 'fib':0.0, 'sale':0.0} for r in RUOLI_LIST}

    for i in st.session_state.ingredients:
        r = i.get('ruolo', 'Impasto')
        if r not in ruoli_stats: r = 'Impasto'
        ruoli_stats[r]['w'] += i['peso']
        ruoli_stats[r]['cal'] += (i['cal_100'] / 100) * i['peso']
        ruoli_stats[r]['p'] += (i['prot_100'] / 100) * i['peso']
        ruoli_stats[r]['c'] += (i['carb_100'] / 100) * i['peso']
        ruoli_stats[r]['f'] += (i['fat_100'] / 100) * i['peso']
        ruoli_stats[r]['s'] += (i['sat_100'] / 100) * i['peso']
        ruoli_stats[r]['fib'] += (i['fib_100'] / 100) * i['peso']
        ruoli_stats[r]['sale'] += (i.get('sale_100', 0.0) / 100) * i['peso']

    tot_w = sum(rs['w'] for rs in ruoli_stats.values())
    w_impasto = ruoli_stats['Impasto']['w']
    w_altri = tot_w - w_impasto

    t_cal = sum(rs['cal'] for rs in ruoli_stats.values())
    t_p = sum(rs['p'] for rs in ruoli_stats.values())
    t_c = sum(rs['c'] for rs in ruoli_stats.values())
    t_f = sum(rs['f'] for rs in ruoli_stats.values())
    t_s = sum(rs['s'] for rs in ruoli_stats.values())
    t_fib = sum(rs['fib'] for rs in ruoli_stats.values())
    t_sale = sum(rs['sale'] for rs in ruoli_stats.values())

    st.markdown(f"**Peso Totale (a crudo):** {tot_w:.1f} g *(di cui Impasto: {w_impasto:.1f} g, Componenti extra: {w_altri:.1f} g)*")

    with st.expander("🔍 Dettagli Nutrizionali a Crudo", expanded=False):
        c1_r, c2_r = st.columns(2)
        c1_r.markdown(f"**Valori Totali ({tot_w:.1f}g):**\n- Calorie: {t_cal:.0f} kcal\n- Carboidrati: {t_c:.1f}g\n- Proteine: {t_p:.1f}g\n- Grassi: {t_f:.1f}g\n  di cui saturi: {t_s:.1f}g\n- Fibre: {t_fib:.1f}g\n- Sale: {t_sale:.2f}g")
        if tot_w > 0: c2_r.markdown(f"**Valori su 100g:**\n- Calorie: {(t_cal/tot_w*100):.0f} kcal\n- Carboidrati: {(t_c/tot_w*100):.1f}g\n- Proteine: {(t_p/tot_w*100):.1f}g\n- Grassi: {(t_f/tot_w*100):.1f}g\n  di cui saturi: {(t_s/tot_w*100):.1f}g\n- Fibre: {(t_fib/tot_w*100):.1f}g\n- Sale: {(t_sale/tot_w*100):.2f}g")

    richiede_cottura = st.checkbox("🔥 La ricetta prevede una cottura dell'Impasto?", key="richiede_cottura")
    rt = 1.0
    var_cott_finale_per_json = 0.0

    if richiede_cottura:
        st.markdown("#### Impostazioni e Variazione Peso")
        cc1, cc2, cc3 = st.columns(3)
        m_cot = cc1.selectbox("Modalità di cottura", ["Forno", "Padella", "Friggitrice ad aria", "Altro"], key="m_cot")
        t_cot = cc2.text_input("Tempo di cottura (es. 15 min)", key="t_cot")
        temp = cc3.number_input("Temperatura (°C)", min_value=0, step=5, key="temp_cot")
        
        ct1, ct2 = st.columns(2)
        
        if 'qta_teglia' not in st.session_state or st.session_state.qta_teglia == 100.0:
            st.session_state.qta_teglia = float(w_impasto) if w_impasto > 0 else 100.0
            
        p_teg_impasto = ct1.number_input("Quantità IMPASTO a crudo in teglia (g/ml)", min_value=1.0, key="qta_teglia")
        rt = p_teg_impasto / w_impasto if w_impasto > 0 else 1.0

        tipo_resa = ct2.radio("Come vuoi calcolare la resa?", ["Usa % di stima", "Inserisci peso reale"], key="tipo_resa")
        
        if tipo_resa == "Usa % di stima":
            var_cott = st.number_input("% Variazione peso (es. -15 per calo)", step=1.0, key="var_cottura")
            p_cot_impasto = p_teg_impasto * (1 + var_cott / 100.0)
            st.info(f"💡 Il peso cotto dell'IMPASTO sarà di circa: **{p_cot_impasto:.1f} g**")
            var_cott_finale_per_json = var_cott
        else:
            p_cot_impasto = st.number_input("Peso cotto reale dell'IMPASTO (g)", min_value=1.0, key="peso_cotto_reale")
            var_cott = ((p_cot_impasto - p_teg_impasto) / p_teg_impasto) * 100.0 if p_teg_impasto > 0 else 0.0
            st.info(f"💡 La variazione di peso effettiva è stata del: **{var_cott:+.1f}%**")
            var_cott_finale_per_json = var_cott
    else:
        p_tot_uso = st.number_input("Quantità totale a crudo da preparare (g/ml)", min_value=1.0, value=float(tot_w) if tot_w > 0 else 100.0)
        rt = p_tot_uso / tot_w if tot_w > 0 else 1.0
        p_cot_impasto = w_impasto * rt

    w_altri_scalati = w_altri * rt
    peso_finale = p_cot_impasto + w_altri_scalati

    cal_f, p_f, c_f, f_f, s_f, fib_f, sale_f = t_cal*rt, t_p*rt, t_c*rt, t_f*rt, t_s*rt, t_fib*rt, t_sale*rt

    if richiede_cottura:
        with st.expander("🔍 Dettagli Nutrizionali a Cotto (Totale Prodotto Finito)", expanded=False):
            c1_c, c2_c = st.columns(2)
            c1_c.markdown(f"**Valori Totali (su {peso_finale:.1f}g):**\n- Calorie: {cal_f:.0f} kcal\n- Carboidrati: {c_f:.1f}g\n- Proteine: {p_f:.1f}g\n- Grassi: {f_f:.1f}g\n  di cui saturi: {s_f:.1f}g\n- Fibre: {fib_f:.1f}g\n- Sale: {sale_f:.2f}g")
            if peso_finale > 0: c2_c.markdown(f"**Valori su 100g:**\n- Calorie: {(cal_f/peso_finale*100):.0f} kcal\n- Carboidrati: {(c_f/peso_finale*100):.1f}g\n- Proteine: {(p_f/peso_finale*100):.1f}g\n- Grassi: {(f_f/peso_finale*100):.1f}g\n  di cui saturi: {(s_f/peso_finale*100):.1f}g\n- Fibre: {(fib_f/peso_finale*100):.1f}g\n- Sale: {(sale_f/peso_finale*100):.2f}g")

    st.divider()

    # ==========================================
    # ⚖️ 6. PORZIONI E BILANCIAMENTO
    # ==========================================
    st.markdown("### :violet[4. Porzioni e Composizione]")
    
    n_porz = st.number_input("In quante porzioni finali dividerai la ricetta?", min_value=1, step=1, key="porzioni")
    w_porz = peso_finale / n_porz
    
    tab_res, tab_comp, tab_tgt = st.tabs(["📊 Totale per Porzione", "🧩 Analisi per Componente", "🎯 Bilanciamento Dinamico"])
    
    with tab_res:
        st.markdown("**Valori per SINGOLA PORZIONE (Prodotto Finito)**")
        st.write(f"*(Ogni porzione pesa complessivamente **{w_porz:.1f} g**)*")
        
        cm_cal, cm2, cm1, cm3, cm4, cm5, cm6 = st.columns(7)
        cm_cal.markdown(f"**Calorie**\n\n{(cal_f / n_porz):.0f} kcal")
        cm2.markdown(f"**Carb.**\n\n{(c_f / n_porz):.1f} g")
        cm1.markdown(f"**Prot.**\n\n{(p_f / n_porz):.1f} g")
        cm3.markdown(f"**Grassi**\n\n{(f_f / n_porz):.1f} g")
        cm4.markdown(f"**Saturi**\n\n{(s_f / n_porz):.1f} g")
        cm5.markdown(f"**Fibre**\n\n{(fib_f / n_porz):.1f} g")
        cm6.markdown(f"**Sale**\n\n{(sale_f / n_porz):.2f} g")

        st.divider()
        st.markdown("#### 💾 Salva Porzione nel Database")
        st.write("Puoi salvare questa singola porzione come prodotto a sé stante (es. 'Barretta Vins') per poterla inserire al volo nel Diario.")
        
        c_np, c_bp = st.columns([2, 1])
        nome_base = st.session_state.get('nome_ricetta', '').strip()
        val_default = f"Porzione di {nome_base}" if nome_base and nome_base != "Nuova Ricetta" else ""
        nome_porz_db = c_np.text_input("Nome del prodotto da salvare:", value=val_default)
        
        with c_bp:
            st.write("")
            if st.button("➕ Salva come Prodotto (pz)", use_container_width=True, key="btn_save_porz_db"):
                if nome_porz_db:
                    esiste_gia = nome_porz_db.strip().lower() in [k.lower() for k in MACROS_DB.keys()]
                    if esiste_gia:
                        st.session_state.show_dup_warning_ricetta = nome_porz_db
                    else:
                        with st.spinner("Salvataggio nel Database..."):
                            cal_100 = (cal_f / peso_finale * 100) if peso_finale > 0 else 0
                            p_100 = (p_f / peso_finale * 100) if peso_finale > 0 else 0
                            c_100 = (c_f / peso_finale * 100) if peso_finale > 0 else 0
                            f_100 = (f_f / peso_finale * 100) if peso_finale > 0 else 0
                            sat_100 = (s_f / peso_finale * 100) if peso_finale > 0 else 0
                            fib_100 = (fib_f / peso_finale * 100) if peso_finale > 0 else 0
                            sale_100 = (sale_f / peso_finale * 100) if peso_finale > 0 else 0
                            
                            success = salva_su_cloud(nome_porz_db, cal_100, p_100, c_100, f_100, sat_100, fib_100, sale_100, 0.0, w_porz, "pz", marca="NutriLab", tipologia="Ricetta Personale")
                            if success:
                                st.success(f"✅ '{nome_porz_db}' salvato nel Database Prodotti!")
                                st.rerun()
                else:
                    st.warning("Inserisci un nome valido.")

        if st.session_state.get("show_dup_warning_ricetta") == nome_porz_db:
            st.error(f"⚠️ Esiste già un prodotto chiamato '{nome_porz_db}' nel database.")
            cy, cn = st.columns(2)
            if cy.button("🚨 Sovrascrivi Esistente", key="btn_over_porz", type="primary"):
                with st.spinner("Sovrascrittura in corso..."):
                    cal_100 = (cal_f / peso_finale * 100) if peso_finale > 0 else 0
                    p_100 = (p_f / peso_finale * 100) if peso_finale > 0 else 0
                    c_100 = (c_f / peso_finale * 100) if peso_finale > 0 else 0
                    f_100 = (f_f / peso_finale * 100) if peso_finale > 0 else 0
                    sat_100 = (s_f / peso_finale * 100) if peso_finale > 0 else 0
                    fib_100 = (fib_f / peso_finale * 100) if peso_finale > 0 else 0
                    sale_100 = (sale_f / peso_finale * 100) if peso_finale > 0 else 0
                    
                    salva_su_cloud(nome_porz_db, cal_100, p_100, c_100, f_100, sat_100, fib_100, sale_100, 0.0, w_porz, "pz")
                    st.session_state.show_dup_warning_ricetta = None
                    st.success("✅ Prodotto aggiornato!")
                    st.rerun()
            if cn.button("❌ Annulla e cambia nome", key="btn_canc_porz"):
                st.session_state.show_dup_warning_ricetta = None
                st.rerun()

    with tab_comp:
        st.write("Analisi dell'apporto nutrizionale suddiviso in base al ruolo dell'ingrediente.")
        for r in RUOLI_LIST:
            if ruoli_stats[r]['w'] > 0:
                if r == 'Impasto': r_w_final = p_cot_impasto / n_porz
                else: r_w_final = (ruoli_stats[r]['w'] * rt) / n_porz
                
                r_cal = (ruoli_stats[r]['cal'] * rt) / n_porz
                r_p = (ruoli_stats[r]['p'] * rt) / n_porz
                r_c = (ruoli_stats[r]['c'] * rt) / n_porz
                r_f = (ruoli_stats[r]['f'] * rt) / n_porz
                
                st.markdown(f"**🔹 {r}** (Peso nella porzione: {r_w_final:.1f} g)  \n  Calorie: {r_cal:.0f} kcal | Carboidrati: {r_c:.1f}g | Proteine: {r_p:.1f}g | Grassi: {r_f:.1f}g")

    with tab_tgt:
        st.write("Scegli un target e calcola le quantità esatte necessarie a raggiungerlo.")
        ct1, ct2 = st.columns(2)
        t_mode = ct1.radio("Calcola il target su:", ["Per porzione", "Su 100g di prodotto finito"])
        t_p_req = ct2.number_input("Target g di proteine", min_value=0.0, value=25.0, step=1.0)
        t_tot = t_p_req * n_porz if t_mode == "Per porzione" else (t_p_req * peso_finale) / 100.0
        
        opz_bil = {}
        for k, v in MACROS_DB.items():
            if len(v) > 1 and v[1] > 0: opz_bil[k] = v[1]
        
        for i in st.session_state.ingredients:
            if i['prot_100'] > 0: opz_bil[i['nome']] = i['prot_100']
            
        sel_bil = st.multiselect("Con quali ingredienti vuoi raggiungere il target?", options=list(opz_bil.keys()))
        if sel_bil:
            base_p = sum((i['prot_100'] / 100) * i['peso'] for i in st.session_state.ingredients if i['nome'] not in sel_bil)
            if t_tot > base_p:
                manca = t_tot - base_p
                st.write(f"Mancano **{manca:.1f}g** di proteine all'intero preparato.")
                prop = {}
                if len(sel_bil) > 1:
                    cs = st.columns(len(sel_bil))
                    t_sl = sum(cs[idx].slider(f"% da {s}", 0, 100, int(100/len(sel_bil)), key=f"sl_{idx}") for idx, s in enumerate(sel_bil))
                    if t_sl > 0: prop = {s: st.session_state[f"sl_{idx}"]/t_sl for idx, s in enumerate(sel_bil)}
                else: prop = {sel_bil[0]: 1.0}
                
                if sum(prop.values()) > 0:
                    st.success("📝 Quantità **TOTALI** da inserire a crudo:")
                    for s in sel_bil:
                        if prop.get(s, 0) > 0:
                            st.markdown(f"- **{(((manca * prop[s]) / opz_bil[s]) * 100):.1f} g** di {s}")
            else: st.warning(f"Gli ingredienti coprono già il target!")

    st.divider()

    # ==========================================
    # 📑 7. ESPORTAZIONE E SALVATAGGIO CLOUD
    # ==========================================
    st.markdown("### :blue[5. Dettagli, Stampa e Salvataggio]")
    
    rip = st.text_input("Tempo di riposo (es. 30 min, in frigo ecc.)", key="riposo")
    proc = st.text_area("Procedimento", height=150, key="procedimento")
    
    c_n, c_t = st.columns([2, 1])
    n_ric = c_n.text_input("**Nome ricetta:**", key="nome_ricetta")
    t_ric = c_t.multiselect("**Categoria:**", CATEGORIE_LIST, key="tipo_ricetta")
    
    txt_exp = f"RICETTA: {n_ric}\nCATEGORIA: {', '.join(t_ric)}\n\nINGREDIENTI:\n"
    ruoli_presenti = set(i.get('ruolo', 'Impasto') for i in st.session_state.ingredients)
    for r_ord in RUOLI_LIST:
        if r_ord in ruoli_presenti:
            txt_exp += f"\n  [{r_ord.upper()}]\n"
            for i in st.session_state.ingredients:
                if i.get('ruolo', 'Impasto') == r_ord:
                    peso_extra = f" ({i['peso']:.0f}g)" if i['unita'] == 'pz' else ""
                    txt_exp += f"  - {i['quantita']} {i['unita']} {i['nome']}{peso_extra}\n"
    
    txt_exp += f"\nPREPARAZIONE:\n"
    if rip: txt_exp += f"- Riposo: {rip}\n"
    if richiede_cottura: 
        txt_exp += f"- Cottura (solo Impasto): {st.session_state.m_cot} a {st.session_state.temp_cot}°C per {st.session_state.t_cot}\n"
        var_c_txt = st.session_state.var_cottura if st.session_state.tipo_resa == "Usa % di stima" else var_cott
        txt_exp += f"- Variazione peso Impasto: {var_c_txt:+.1f}%\n- Peso Prodotto Finito: {peso_finale:.1f} g\n"
    else: 
        txt_exp += f"- Resa totale: {peso_finale:.1f} g\n"
        
    txt_exp += f"- Porzioni: {n_porz} da {w_porz:.1f} g\n\nVALORI NUTRIZIONALI (Per Porzione Pronta):\n"
    txt_exp += f"- Calorie: {(cal_f/n_porz):.0f} kcal | Carboidrati: {(c_f/n_porz):.1f}g | Proteine: {(p_f/n_porz):.1f}g | Grassi: {(f_f/n_porz):.1f}g (Saturi: {(s_f/n_porz):.1f}g) | Fibre: {(fib_f/n_porz):.1f}g | Sale: {(sale_f/n_porz):.2f}g"
    
    def clean(t): return str(t).encode('latin-1', 'replace').decode('latin-1')
    def mk_pdf():
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.multi_cell(0, 10, txt=clean(txt_exp)); return bytes(pdf.output())

    df_export = pd.DataFrame([{
        "Nome": i['nome'], "Quantita": i['quantita'], "Unita": i['unita'], "Utilizzo": i.get('ruolo', 'Impasto'),
        "Cal_100g": i['cal_100'], "Prot_100g": i['prot_100'], "Carb_100g": i['carb_100'],
        "Fat_100g": i['fat_100'], "Sat_100g": i['sat_100'], "Fib_100g": i['fib_100'], "Sale_100g": i.get('sale_100', 0.0), "Peso_pz": i.get('peso_pz', 0.0),
        "Ricetta_Nome": st.session_state.nome_ricetta,
        "Ricetta_Procedimento": st.session_state.procedimento,
        "Ricetta_Riposo": st.session_state.riposo,
        "Ricetta_Categorie": ",".join(st.session_state.tipo_ricetta),
        "Ricetta_Porzioni": st.session_state.porzioni,
        "Cottura_Richiesta": st.session_state.richiede_cottura,
        "Cottura_Modalita": st.session_state.m_cot,
        "Cottura_Tempo": st.session_state.t_cot,
        "Cottura_Temperatura": st.session_state.temp_cot,
        "Cottura_TipoResa": st.session_state.tipo_resa,
        "Cottura_Variazione": var_cott_finale_per_json if st.session_state.richiede_cottura else 0.0,
        "Cottura_PesoReale": st.session_state.peso_cotto_reale,
        "Cottura_QtaTeglia": st.session_state.qta_teglia
    } for i in st.session_state.ingredients])
    
    csv_data = df_export.to_csv(index=False).encode('utf-8')
    
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Ricetta')
    excel_data = excel_buffer.getvalue()

    with st.expander("👀 Anteprima Testo Generato"): st.text(txt_exp)
    
    st.write("**Salvataggio in Cloud**")
    
    if IS_ADMIN:
        condividi_ricetta = True
        st.info("👑 Sei l'amministratore: le tue ricette sono pubbliche di default per tutta la community.")
    else:
        condividi_ricetta = st.checkbox("🌍 Rendi pubblica questa ricetta (condividila con la community)")
        
    if st.button("☁️ Salva Ricetta nel Database Cloud", use_container_width=True):
        if n_ric and st.session_state.ingredients:
            with st.spinner("Salvataggio in corso..."):
                try:
                    json_dati = df_export.to_json(orient='records')
                    categoria_str = ", ".join(t_ric)
                    success = salva_ricetta_cloud(USER_ID, n_ric, categoria_str, json_dati, condividi_ricetta)
                    if success: st.success("✅ Ricetta salvata nel Database!")
                    else: st.error("Errore tecnico durante il salvataggio.")
                except Exception as e:
                    st.error(f"Errore tecnico: {e}")
        else:
            st.warning("⚠️ Inserisci un Nome per la ricetta prima di salvare.")

    st.write("**Esportazione File Locali**")
    c_dl1, c_dl2, c_dl3, c_dl4 = st.columns(4)
    nm_f = n_ric.replace(" ", "_").lower() if n_ric else "ricetta"
    c_dl1.download_button("📄 .TXT", data=txt_exp, file_name=f"{nm_f}.txt", use_container_width=True)
    try: c_dl2.download_button("📕 .PDF", data=mk_pdf(), file_name=f"{nm_f}.pdf", mime="application/pdf", use_container_width=True)
    except: c_dl2.error("Errore PDF")
    c_dl3.download_button("📊 .CSV (Dati)", data=csv_data, file_name=f"{nm_f}.csv", mime="text/csv", use_container_width=True)
    c_dl4.download_button("📗 .XLSX (Dati)", data=excel_data, file_name=f"{nm_f}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)