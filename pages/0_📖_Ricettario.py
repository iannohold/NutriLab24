import streamlit as st
import pandas as pd
import json
import io
from components.nav import render_top_nav
from components.auth import require_login
from services.db import get_conn, ADMIN_ID, get_ricette_utente_e_community

st.set_page_config(page_title="NutriLab24 - Ricettario", layout="wide")
require_login()
render_top_nav("Ricettario Pubblico e Privato")

USER_ID = st.session_state.username

# Inizializza la navigazione interna della pagina
if "ricettario_view" not in st.session_state:
    st.session_state.ricettario_view = "index"
if "ricettario_selected" not in st.session_state:
    st.session_state.ricettario_selected = None

# ==========================================
# 📥 RECUPERO DATI
# ==========================================
@st.cache_data(ttl=300)
def load_ricettario():
    return get_ricette_utente_e_community(USER_ID, ADMIN_ID)

df_ricette = load_ricettario()

# ==========================================
# 📱 VISTA 1: INDICE (Stile GialloZafferano)
# ==========================================
if st.session_state.ricettario_view == "index":
    st.title("📖 Il Ricettario")
    st.markdown("#### *Esplora, filtra e ricalcola le ricette.* 🍲")
    
    if df_ricette.empty:
        st.info("Nessuna ricetta disponibile al momento. Creane una dal Laboratorio!")
        st.stop()

    # --- BARRA DEI FILTRI ---
    with st.expander("🔍 Filtra Ricette", expanded=True):
        c_search, c_cat, c_autore = st.columns([2, 1, 1])
        ricerca_txt = c_search.text_input("Cerca per nome:", placeholder="Es. Pancake...")
        
        categorie_uniche = ["Tutte"] + sorted(list(set([c.strip() for sublist in df_ricette['Categoria'].dropna().str.split(',') for c in sublist if c.strip()])))
        filtro_cat = c_cat.selectbox("Categoria:", categorie_uniche)
        
        autori_unici = ["Tutti", "Mie Ricette", "Community"]
        filtro_autore = c_autore.selectbox("Autore:", autori_unici)

    # Applica i filtri
    df_filtrato = df_ricette.copy()
    if ricerca_txt:
        df_filtrato = df_filtrato[df_filtrato['Nome Ricetta'].str.contains(ricerca_txt, case=False, na=False)]
    if filtro_cat != "Tutte":
        df_filtrato = df_filtrato[df_filtrato['Categoria'].str.contains(filtro_cat, case=False, na=False)]
    if filtro_autore == "Mie Ricette":
        df_filtrato = df_filtrato[df_filtrato['User_ID'] == USER_ID]
    elif filtro_autore == "Community":
        df_filtrato = df_filtrato[df_filtrato['User_ID'] != USER_ID]

    st.write("")
    st.markdown(f"**{len(df_filtrato)} Ricette Trovate**")

    # --- GRIGLIA RICETTE ---
    cols = st.columns(3) 
    
    for idx, row in df_filtrato.iterrows():
        col_idx = idx % 3
        
        # Estrazione rapida dell'immagine dal JSON (se presente)
        url_foto_index = ""
        try:
            dati_json = json.loads(row['Dati JSON'])
            if isinstance(dati_json, list) and len(dati_json) > 0:
                url_foto_index = dati_json[0].get('Ricetta_URLFoto', "")
        except: pass
        
        if url_foto_index:
            box_immagine = f'<img src="{url_foto_index}" style="width:100%; height:140px; object-fit:cover; border-radius:8px; margin-bottom:10px;">'
        else:
            box_immagine = '<div style="height:140px; background-color:#f4f4f4; border-radius:8px; display:flex; align-items:center; justify-content:center; margin-bottom:10px;"><span style="font-size:40px;">🍲</span></div>'
        
        with cols[col_idx]:
            st.markdown(
                f"""
                <div style="border:1px solid #e0e0e0; border-radius:10px; padding:15px; margin-bottom:15px; background-color:#ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                    {box_immagine}
                    <h4 style="margin:0; padding:0; color:#333; font-size:18px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{row['Nome Ricetta']}</h4>
                    <p style="color:gray; font-size:12px; margin:5px 0 15px 0;">Di: <b>{row['User_ID']}</b> • {row['Categoria']}</p>
                </div>
                """, unsafe_allow_html=True
            )
            if st.button("Leggi e Cucina 👨‍🍳", key=f"btn_open_{idx}", use_container_width=True):
                st.session_state.ricettario_selected = row.to_dict()
                st.session_state.ricettario_view = "detail"
                st.rerun()

# ==========================================
# 📱 VISTA 2: DETTAGLIO RICETTA INTERATTIVO
# ==========================================
elif st.session_state.ricettario_view == "detail":
    if st.button("⬅️ Torna all'Indice", type="secondary"):
        st.session_state.ricettario_view = "index"
        st.session_state.ricettario_selected = None
        st.rerun()
        
    ricetta = st.session_state.ricettario_selected
    
    try:
        df_dati = pd.read_json(io.StringIO(ricetta['Dati JSON']))
    except:
        st.error("Errore nella lettura dei dati della ricetta.")
        st.stop()
        
    r_meta = df_dati.iloc[0]
    n_porz_orig = float(r_meta.get('Ricetta_Porzioni', 1.0))
    if n_porz_orig <= 0: n_porz_orig = 1.0
    
    procedimento = r_meta.get('Ricetta_Procedimento', "Nessun procedimento inserito.")
    riposo = r_meta.get('Ricetta_Riposo', "")
    cott_req = r_meta.get('Cottura_Richiesta', False)
    mod_cott = r_meta.get('Cottura_Modalita', "")
    tempo_cott = r_meta.get('Cottura_Tempo', "")
    temp_cott = r_meta.get('Cottura_Temperatura', "")
    
    # Recupero Immagine e Video
    url_foto_det = r_meta.get('Ricetta_URLFoto', "")
    link_vid_det = r_meta.get('Ricetta_LinkVideo', "")

    # Calcolo Macros Totali Originari
    tot_cal = tot_p = tot_c = tot_f = tot_w = 0.0
    for _, item in df_dati.iterrows():
        u = str(item['Unita']).strip()
        pz_w = float(item.get('Peso_pz', 0.0))
        qty = float(item['Quantita'])
        w_ing = qty * pz_w if u == 'pz' else qty
        
        tot_w += w_ing
        tot_cal += (float(item.get('Cal_100g', 0)) / 100) * w_ing
        tot_p += (float(item.get('Prot_100g', 0)) / 100) * w_ing
        tot_c += (float(item.get('Carb_100g', 0)) / 100) * w_ing
        tot_f += (float(item.get('Fat_100g', 0)) / 100) * w_ing

    porz_p_orig = tot_p / n_porz_orig
    porz_c_orig = tot_c / n_porz_orig

    # --- HEADER RICETTA ---
    if url_foto_det:
        st.markdown(f'<img src="{url_foto_det}" style="width:100%; max-height:400px; object-fit:cover; border-radius:10px; margin-bottom:20px;">', unsafe_allow_html=True)
        
    st.markdown(f"<h1 style='color: #FF4B4B; margin-bottom: 0px;'>{ricetta['Nome Ricetta']}</h1>", unsafe_allow_html=True)
    
    if link_vid_det:
        st.markdown(f"**[📺 Guarda la videoricetta o apri il blog originale]({link_vid_det})**")
        
    st.markdown(f"**Categoria:** {ricetta['Categoria']} | **Autore:** {ricetta['User_ID']}")
    st.divider()

    # --- SCALATORE DINAMICO E MACROS COMPATTI ---
    c_calc1, c_calc2 = st.columns(2)
    with c_calc1:
        st.markdown("### ⚖️ Ricalcolo Ricetta")
        modalita_scala = st.radio("Metodo di calcolo:", [
            "📝 Libero (Cambia Porzioni)", 
            "🥩 Blocca Proteine a Porzione", 
            "🍞 Blocca Carboidrati a Porzione"
        ])
    
    with c_calc2:
        user_porzioni = st.number_input("Porzioni totali da preparare:", min_value=0.1, value=float(n_porz_orig), step=1.0)
        
        if modalita_scala == "📝 Libero (Cambia Porzioni)":
            moltiplicatore = user_porzioni / n_porz_orig if n_porz_orig > 0 else 1.0
        elif modalita_scala == "🥩 Blocca Proteine a Porzione":
            target_p_porz = st.number_input("Proteine target per 1 porzione (g):", min_value=1.0, value=float(porz_p_orig), step=1.0)
            tot_p_desiderate = target_p_porz * user_porzioni
            moltiplicatore = tot_p_desiderate / tot_p if tot_p > 0 else 1.0
        elif modalita_scala == "🍞 Blocca Carboidrati a Porzione":
            target_c_porz = st.number_input("Carboidrati target per 1 porzione (g):", min_value=1.0, value=float(porz_c_orig), step=1.0)
            tot_c_desiderate = target_c_porz * user_porzioni
            moltiplicatore = tot_c_desiderate / tot_c if tot_c > 0 else 1.0

    # Ricalcolo totali PREPARAZIONE
    new_tot_w = tot_w * moltiplicatore
    new_tot_cal = tot_cal * moltiplicatore
    new_tot_c = tot_c * moltiplicatore
    new_tot_p = tot_p * moltiplicatore
    new_tot_f = tot_f * moltiplicatore

    # Ricalcolo SINGOLA PORZIONE
    new_porz_w = new_tot_w / user_porzioni
    new_porz_cal = new_tot_cal / user_porzioni
    new_porz_c = new_tot_c / user_porzioni
    new_porz_p = new_tot_p / user_porzioni
    new_porz_f = new_tot_f / user_porzioni

    # --- COMPACT MACROS BOX ---
    st.markdown(f"""
    <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border: 1px solid #d0d0d0; margin-top: 5px; margin-bottom: 20px;">
        <div style="margin-bottom: 12px;">
            <b style="color:#FF4B4B; font-size: 15px;">🍲 INTERA PREPARAZIONE ({user_porzioni:g} porzioni)</b><br>
            <span style="font-size: 15px; color: #333;">⚖️ {new_tot_w:.0f}g &nbsp;|&nbsp; 🔥 {new_tot_cal:.0f} kcal &nbsp;|&nbsp; 🍞 C: {new_tot_c:.1f}g &nbsp;|&nbsp; 🥩 P: {new_tot_p:.1f}g &nbsp;|&nbsp; 🥑 G: {new_tot_f:.1f}g</span>
        </div>
        <div>
            <b style="color:#0068c9; font-size: 15px;">🍽️ 1 SINGOLA PORZIONE</b><br>
            <span style="font-size: 15px; color: #333;">⚖️ {new_porz_w:.0f}g &nbsp;|&nbsp; 🔥 {new_porz_cal:.0f} kcal &nbsp;|&nbsp; 🍞 C: {new_porz_c:.1f}g &nbsp;|&nbsp; 🥩 P: {new_porz_p:.1f}g &nbsp;|&nbsp; 🥑 G: {new_porz_f:.1f}g</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- INGREDIENTI RAGGRUPPATI E PROCEDIMENTO ---
    c_ing, c_proc = st.columns([1, 1.2])
    
    with c_ing:
        st.markdown("### 🛒 Ingredienti")
        st.write(f"Dosi ricalcolate per **{user_porzioni:g}** porzioni:")
        
        gruppi = df_dati['Utilizzo'].unique()
        for g in gruppi:
            df_g = df_dati[df_dati['Utilizzo'] == g]
            st.markdown(f"<div style='background-color: #f9f9f9; padding: 8px 12px; border-left: 4px solid #FF4B4B; margin-top: 10px; margin-bottom: 5px; border-radius: 0 5px 5px 0;'><b>{g.upper()}</b></div>", unsafe_allow_html=True)
            
            html_list = "<ul style='list-style-type: none; padding-left: 5px; margin-top: 5px; font-size: 15px;'>"
            for _, item in df_g.iterrows():
                qta_ricalcolata = float(item['Quantita']) * moltiplicatore
                html_list += f"<li style='margin-bottom: 8px; border-bottom: 1px dotted #ccc; padding-bottom: 4px;'><b>{qta_ricalcolata:.1f} {item['Unita']}</b> &nbsp; {item['Nome']}</li>"
            html_list += "</ul>"
            st.markdown(html_list, unsafe_allow_html=True)

    with c_proc:
        st.markdown("### 👨‍🍳 Procedimento")
        
        if cott_req:
            st.info(f"**Cottura prevista:** {mod_cott} a {temp_cott}°C per {tempo_cott}")
        if riposo:
            st.warning(f"**Tempo di riposo:** {riposo}")
            
        st.write("")
        step_lines = [s for s in procedimento.split('\n') if s.strip()]
        if step_lines:
            for i, step in enumerate(step_lines):
                st.markdown(f"**Step {i+1}**<br>{step}", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.write("Nessun passaggio dettagliato fornito dall'autore.")
            
        st.markdown("---")
        if st.button("📓 Apri nel Diario per consumarla oggi", type="primary", use_container_width=True):
            st.switch_page("pages/2_📅_Diario.py")