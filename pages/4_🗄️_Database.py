import streamlit as st
import pandas as pd
import requests
from components.nav import render_top_nav
from services.db import get_current_macros_db, elimina_da_cloud, salva_su_cloud, get_ean_mapping

# 1. Controllo di sicurezza centralizzato
from components.auth import require_login
require_login()

st.set_page_config(page_title="NutriLab24", layout="wide")

# 🧭 VISUALIZZA LA NAVIGAZIONE SUPERIORE
render_top_nav("Database Prodotti")

st.title("🗄️ Database Prodotti")
st.markdown("#### *Gestisci, cerca e cataloga i tuoi ingredienti.* ☁️")

# ==========================================
# ⚙️ FUNZIONI DI SUPPORTO E CALLBACKS
# ==========================================

TIPOLOGIE_PRODOTTO = [
    "Materia Prima", 
    "Prodotto Confezionato", 
    "Integratore", 
    "Prodotto HomeMade", 
    "Ricetta Personale"
]

def formatta_nome_prodotto(nome):
    """Formatta in Title Case mantenendo minuscole le preposizioni italiane."""
    if not nome: return ""
    prep_min = {'di', 'a', 'da', 'in', 'con', 'su', 'per', 'tra', 'fra', 
                'il', 'lo', 'la', 'i', 'gli', 'le', 'del', 'dello', 'della', 
                'dei', 'degli', 'delle', 'al', 'allo', 'alla', 'ai', 'agli', 
                'alle', 'dal', 'dallo', 'dalla', 'dai', 'dagli', 'dalle', 
                'nel', 'nello', 'nella', 'nei', 'negli', 'nelle', 'sul', 
                'sullo', 'sulla', 'sui', 'sugli', 'sulle', 'ed', 'e', 'o', 'd'}
    
    parole = str(nome).lower().split()
    risultato = []
    for i, p in enumerate(parole):
        if "'" in p:
            parts = p.split("'", 1)
            if parts[0] in prep_min:
                p = parts[0] + "'" + parts[1].capitalize()
            else:
                p = parts[0].capitalize() + "'" + parts[1].capitalize()
        else:
            if i == 0 or p not in prep_min:
                p = p.capitalize()
        risultato.append(p)
    return " ".join(risultato)

# Callback: Cerca dal web
def cerca_e_compila_off():
    query = st.session_state.get("input_ricerca_web", "").strip()
    if not query: return
    
    headers = {"User-Agent": "NutriLab24/1.0"}
    url = f"https://world.openfoodfacts.org/api/v0/product/{query}.json" if query.isdigit() else f"https://it.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=1"
    
    try:
        res = requests.get(url, headers=headers, timeout=5).json()
        prod = res.get("product", {}) if query.isdigit() else (res.get("products")[0] if res.get("products") else {})
        
        if prod:
            n = prod.get("nutriments", {})
            nome_off = prod.get("product_name_it") or prod.get("product_name") or (query if not query.isdigit() else "")
            marca_off = prod.get("brands", "").split(",")[0] if prod.get("brands") else ""
            
            # 🔒 Selettore del blocco nome
            if not st.session_state.get("lock_name", False):
                st.session_state.f_nome = formatta_nome_prodotto(nome_off)
                
            st.session_state.f_marca = formatta_nome_prodotto(marca_off)
            st.session_state.f_tipo = "Prodotto Confezionato"
            if query.isdigit(): st.session_state.f_ean = query
            
            st.session_state.f_cal = float(n.get("energy-kcal_100g", 0.0) or 0.0)
            st.session_state.f_p = float(n.get("proteins_100g", 0.0) or 0.0)
            st.session_state.f_c = float(n.get("carbohydrates_100g", 0.0) or 0.0)
            st.session_state.f_f = float(n.get("fat_100g", 0.0) or 0.0)
            st.session_state.f_sat = float(n.get("saturated-fat_100g", 0.0) or 0.0)
            st.session_state.f_fib = float(n.get("fiber_100g", 0.0) or 0.0)
            st.session_state.f_sale = float(n.get("salt_100g", 0.0) or 0.0)
            st.toast("✅ Prodotto trovato e modulo compilato!", icon="🎯")
        else:
            st.toast("❌ Nessun risultato trovato.", icon="🚫")
    except:
        st.toast("❌ Errore di connessione a OpenFoodFacts.", icon="🚫")

# Callback: Carica dal DB locale
def carica_prodotto_locale():
    sel = st.session_state.get("sel_locale_modifica")
    if sel and sel != "-- Seleziona --":
        macros = MACROS_DB[sel]
        cal, p, c, f, fib, sat, sale, var, pz_w, u_def, marca, tipologia = macros
        
        user_id = st.session_state.get("username", "vins")
        em = get_ean_mapping(user_id)
        ean_val = ""
        for e_key, n_val in em.items():
            if n_val.lower() == sel.lower(): ean_val = e_key; break
        
        st.session_state.f_nome = sel
        st.session_state.lock_name = True # 🔒 Auto-blocco attivato se carichi dal DB locale
        
        st.session_state.f_marca = marca
        st.session_state.f_tipo = tipologia if tipologia in TIPOLOGIE_PRODOTTO else "Materia Prima"
        st.session_state.f_ean = ean_val
        st.session_state.f_u = u_def
        st.session_state.f_pzw = pz_w
        st.session_state.f_var = var
        st.session_state.f_cal = cal
        st.session_state.f_c = c
        st.session_state.f_p = p
        st.session_state.f_f = f
        st.session_state.f_sat = sat
        st.session_state.f_fib = fib
        st.session_state.f_sale = sale
        st.toast("📥 Dati caricati! Ora puoi modificarli o integrarli dal web.", icon="📝")

# Inizializzazione Session State per il form
form_keys = {
    'f_nome': '', 'f_marca': '', 'f_tipo': 'Materia Prima', 'f_ean': '', 
    'f_u': 'g', 'f_pzw': 0.0, 'f_var': 0.0, 'f_cal': 0.0, 'f_c': 0.0, 
    'f_p': 0.0, 'f_f': 0.0, 'f_sat': 0.0, 'f_fib': 0.0, 'f_sale': 0.0, 'lock_name': False
}
for k, v in form_keys.items():
    if k not in st.session_state: st.session_state[k] = v

# Callback: Salvataggio prodotto
def salva_prodotto_callback():
    nome_formattato = formatta_nome_prodotto(st.session_state.f_nome)
    marca_formattata = formatta_nome_prodotto(st.session_state.f_marca)
    
    if not nome_formattato.strip():
        st.session_state.db_form_error = "⚠️ Il nome del prodotto è obbligatorio!"
    elif st.session_state.f_u == "pz" and st.session_state.f_pzw <= 0:
        st.session_state.db_form_error = "⚠️ Hai selezionato 'pz'. Devi inserire il peso di un singolo pezzo."
    else:
        success = salva_su_cloud(
            nome=nome_formattato, cal=st.session_state.f_cal, p=st.session_state.f_p, 
            c=st.session_state.f_c, f=st.session_state.f_f, sat=st.session_state.f_sat, 
            fib=st.session_state.f_fib, sale=st.session_state.f_sale, var_cott=st.session_state.f_var, 
            peso_pz=st.session_state.f_pzw, unita_def=st.session_state.f_u, 
            marca=marca_formattata, tipologia=st.session_state.f_tipo, ean=st.session_state.f_ean
        )
        if success:
            st.session_state.db_form_success = f"✅ Prodotto '{nome_formattato}' salvato con successo!"
            st.session_state.db_form_error = ""
            for k, v in form_keys.items(): 
                st.session_state[k] = v

# ==========================================
# 📊 ELABORAZIONE DATI E UI
# ==========================================

MACROS_DB = get_current_macros_db()
tot_prod = len(MACROS_DB)

with st.expander("📖 Legenda Tipologie Prodotti", expanded=False):
    st.markdown("""
    - 🌾 **Materia Prima**: Alimenti base non trasformati (es. Farina, uova, pollo crudo).
    - 🥫 **Prodotto Confezionato**: Alimenti acquistati con una marca specifica o EAN (es. Yogurt greco, barrette).
    - 💊 **Integratore**: Prodotti per l'integrazione (es. Proteine in polvere, creatina).
    - 🍪 **Prodotto HomeMade**: Singole porzioni salvate dalle tue preparazioni per un uso rapido nel diario.
    - 🍲 **Ricetta Personale**: Le preparazioni o impasti che hai creato tu nel Laboratorio (es. Mix pancake).
    """)

tab_lista, tab_nuovo, tab_gestione = st.tabs(["📋 Lista Completa", "➕ Nuovo / Modifica", "🗑️ Elimina"])

with tab_lista:
    st.markdown(f"### 📋 Tutti i tuoi Prodotti ({tot_prod})")
    if not MACROS_DB:
        st.warning("Il database è vuoto.")
    else:
        dati_tabella = []
        for nome, macros in MACROS_DB.items():
            cal, p, c, f, fib, sat, sale, var, pz_w, u_def, marca, tipologia = macros
            dati_tabella.append({
                "Nome": nome, "Marca": marca, "Tipologia": tipologia, "Unità": u_def,
                "Calorie": cal, "Carboidrati": c, "Proteine": p, "Grassi": f,
                "Fibre": fib, "Saturi": sat, "Sale": sale, "Peso 1pz": pz_w, "Var. Cottura %": var
            })
            
        df_vis = pd.DataFrame(dati_tabella)
        
        c_search, c_tipo, c_marca = st.columns([2, 1, 1])
        ricerca = c_search.text_input("🔍 Cerca per nome:")
        tipologie_disponibili = ["Tutte"] + sorted(df_vis['Tipologia'].unique().tolist())
        filtro_tipo = c_tipo.selectbox("Filtra Tipologia:", tipologie_disponibili)
        marche_disponibili = ["Tutte"] + sorted(df_vis[df_vis['Marca'] != '']['Marca'].unique().tolist())
        filtro_marca = c_marca.selectbox("Filtra Marca:", marche_disponibili)
        
        if ricerca: df_vis = df_vis[df_vis['Nome'].str.contains(ricerca, case=False)]
        if filtro_tipo != "Tutte": df_vis = df_vis[df_vis['Tipologia'] == filtro_tipo]
        if filtro_marca != "Tutte": df_vis = df_vis[df_vis['Marca'] == filtro_marca]
            
        st.dataframe(
            df_vis.style.format({
                "Calorie": "{:.0f}", "Carboidrati": "{:.1f}", "Proteine": "{:.1f}", 
                "Grassi": "{:.1f}", "Fibre": "{:.1f}", "Saturi": "{:.1f}", "Sale": "{:.2f}",
                "Peso 1pz": "{:.1f}", "Var. Cottura %": "{:.1f}"
            }),
            use_container_width=True, hide_index=True
        )

with tab_nuovo:
    st.markdown("### 🔍 Importazione e Modifica")
    
    col_web, col_loc = st.columns(2)
    with col_web:
        st.write("**Cerca nel database mondiale:**")
        cw1, cw2 = st.columns([3, 1])
        cw1.text_input("Inserisci EAN o Nome prodotto", key="input_ricerca_web", placeholder="es. 8480000511102")
        cw2.write("")
        cw2.button("🌐 Cerca Online", on_click=cerca_e_compila_off, use_container_width=True)
        st.checkbox("🔒 Blocca il Nome (evita sovrascrittura automatica)", key="lock_name")
        
    with col_loc:
        st.write("**Modifica un prodotto esistente:**")
        cl1, cl2 = st.columns([3, 1])
        cl1.selectbox("Seleziona prodotto locale", ["-- Seleziona --"] + sorted(list(MACROS_DB.keys())), key="sel_locale_modifica", label_visibility="collapsed")
        cl2.button("📥 Carica", on_click=carica_prodotto_locale, use_container_width=True)

    st.divider()
    
    c_n, c_m, c_t = st.columns([2, 1.5, 1.5])
    c_n.text_input("Nome Prodotto *", key="f_nome")
    c_m.text_input("Marca", key="f_marca")
    c_t.selectbox("Tipologia", TIPOLOGIE_PRODOTTO, key="f_tipo")
    
    c_ean, c_u, c_pw, c_var = st.columns([1.5, 1, 1, 1])
    c_ean.text_input("Codice EAN", key="f_ean")
    c_u.selectbox("Unità", ["g", "ml", "pz"], key="f_u")
    c_pw.number_input("Peso 1pz (se in 'pz')", min_value=0.0, step=1.0, key="f_pzw")
    c_var.number_input("Var. Cottura %", step=1.0, key="f_var")
    
    st.markdown("#### Valori Nutrizionali (per 100g/ml o 1 pz)")
    c_cal, c_c, c_p, c_f, c_s, c_fib, c_sal = st.columns(7)
    c_cal.number_input("Calorie", min_value=0.0, step=1.0, key="f_cal")
    c_c.number_input("Carboidrati", min_value=0.0, step=0.1, key="f_c")
    c_p.number_input("Proteine", min_value=0.0, step=0.1, key="f_p")
    c_f.number_input("Grassi", min_value=0.0, step=0.1, key="f_f")
    c_s.number_input("Saturi", min_value=0.0, step=0.1, key="f_sat")
    c_fib.number_input("Fibre", min_value=0.0, step=0.1, key="f_fib")
    c_sal.number_input("Sale", min_value=0.0, step=0.1, key="f_sale", format="%.2f")
    
    st.write("")
    
    if st.session_state.get("db_form_error"):
        st.error(st.session_state.db_form_error)
        st.session_state.db_form_error = "" 
        
    if st.session_state.get("db_form_success"):
        st.success(st.session_state.db_form_success)
        st.session_state.db_form_success = ""
        
    st.button("💾 Salva nel Database Cloud", type="primary", use_container_width=True, on_click=salva_prodotto_callback)

with tab_gestione:
    st.markdown("### 🗑️ Elimina Prodotti")
    st.write("L'eliminazione è irreversibile.")
    
    opzioni_del = ["-- Seleziona --"] + sorted(list(MACROS_DB.keys()))
    da_eliminare = st.selectbox("Seleziona il prodotto da eliminare:", opzioni_del)
    
    if da_eliminare != "-- Seleziona --":
        st.warning(f"⚠️ Sei sicuro di voler eliminare definitivamente **{da_eliminare}**?")
        c1_del, c2_del = st.columns(2)
        
        if c1_del.button("🚨 Conferma Eliminazione", type="primary", use_container_width=True):
            with st.spinner("Eliminazione in corso..."):
                success = elimina_da_cloud(da_eliminare)
                if success:
                    st.success(f"✅ {da_eliminare} eliminato con successo!")
                    st.rerun()
                else:
                    st.error("Errore durante l'eliminazione.")
        if c2_del.button("❌ Annulla", use_container_width=True):
            st.rerun()