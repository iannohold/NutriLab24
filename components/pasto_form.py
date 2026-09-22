import streamlit as st
import pandas as pd
import datetime
import uuid
import io
from sqlalchemy import text

from services.db import (
    get_conn, 
    ADMIN_ID, 
    get_current_macros_db, 
    get_macros_and_match, 
    salva_su_cloud, 
    get_ricette_utente_e_community
)

ORARI_FINE_PASTO = {
    "Colazione": datetime.time(11, 0),
    "Spuntino": datetime.time(12, 30),
    "Pranzo": datetime.time(15, 30),
    "Merenda": datetime.time(20, 0),
    "Cena": datetime.time(23, 59)
}

def mostra_interfaccia_inserimento_pasti(data_selezionata, is_planner=False):
    USER_ID = st.session_state.get("username", ADMIN_ID)
    conn = get_conn()
    MACROS_DB = get_current_macros_db()
    
    oggi_date = pd.to_datetime('today').date()
    ora_attuale = pd.Timestamp.now(tz='Europe/Rome').time()
    tutti_pasti = ["Colazione", "Spuntino", "Pranzo", "Merenda", "Cena"]

    if data_selezionata == oggi_date and is_planner:
        pasti_disponibili = [p for p in tutti_pasti if ora_attuale <= ORARI_FINE_PASTO.get(p, datetime.time(23, 59))]
        if not pasti_disponibili: pasti_disponibili = ["Merenda", "Cena"]
    else:
        pasti_disponibili = tutti_pasti

    t_colazione = datetime.time(9, 30); t_spuntino1 = datetime.time(12, 0)
    t_pranzo = datetime.time(15, 0); t_spuntino2 = datetime.time(19, 0)
    
    if ora_attuale <= t_colazione: pasto_suggerito = "Colazione"
    elif ora_attuale <= t_spuntino1: pasto_suggerito = "Spuntino"
    elif ora_attuale <= t_pranzo: pasto_suggerito = "Pranzo"
    elif ora_attuale <= t_spuntino2: pasto_suggerito = "Merenda"
    else: pasto_suggerito = "Cena"

    default_pasto_idx = pasti_disponibili.index(pasto_suggerito) if pasto_suggerito in pasti_disponibili else 0

    tgt_cal = tgt_c = tgt_p = tgt_f = 0.0
    try:
        query_prof = text("SELECT tgt_cal, tgt_c, tgt_p, tgt_f FROM profilo WHERE LOWER(user_id) = LOWER(:uid)")
        df_prof = conn.query(query_prof, params={"uid": USER_ID}, ttl=600)
        if not df_prof.empty:
            tgt_cal = float(df_prof.iloc[0].get('tgt_cal', 0) or 0)
            tgt_c = float(df_prof.iloc[0].get('tgt_c', 0) or 0)
            tgt_p = float(df_prof.iloc[0].get('tgt_p', 0) or 0)
            tgt_f = float(df_prof.iloc[0].get('tgt_f', 0) or 0)
    except: pass

    c1_ins, c2_ins = st.columns([1, 2])
    with c1_ins:
        pasto_sel = st.selectbox("Pasto della giornata", pasti_disponibili, index=default_pasto_idx, key=f"sel_pasto_{data_selezionata}")
    with c2_ins:
        tipo_inserimento_diario = st.radio(
            "Seleziona la tipologia di inserimento:", 
            ["📚 Dal tuo Ricettario", "🛒 Alimenti (Singoli o Multipli)", "⏱️ Ricetta Libera (Al volo)"], 
            horizontal=True, key=f"tipo_ins_{data_selezionata}"
        )

    st.divider()
    rows_to_add = [] 
    ready_to_add = False
    
    if "diario_multi_items" not in st.session_state: st.session_state.diario_multi_items = []
    if "temp_recipe_diario" not in st.session_state: st.session_state.temp_recipe_diario = []

    # =========================================================
    # LOGICA DI FILTRAGGIO GLOBALE
    # =========================================================
    tipologie_uniche = ["Tutte"] + sorted(list(set([v[11] for v in MACROS_DB.values() if len(v)>11 and v[11]])))
    marche_uniche = ["Tutte"] + sorted(list(set([v[10] for v in MACROS_DB.values() if len(v)>10 and v[10]])))

    def get_filtered_ingredients(tipo_sel, marca_sel):
        filtrati = []
        for k, v in MACROS_DB.items():
            t_match = (tipo_sel == "Tutte" or (len(v)>11 and v[11] == tipo_sel))
            m_match = (marca_sel == "Tutte" or (len(v)>10 and v[10] == marca_sel))
            if t_match and m_match: filtrati.append(k)
        return ["-- Seleziona --"] + sorted(filtrati)

    # =========================================================
    # 📚 FLUSSO 1: RICETTARIO PERSONALE
    # =========================================================
    if tipo_inserimento_diario == "📚 Dal tuo Ricettario":
        df_ricette_cloud = get_ricette_utente_e_community(USER_ID, ADMIN_ID)
        df_mie = df_ricette_cloud[df_ricette_cloud['User_ID'] == USER_ID]
        ricette_list = df_mie['Nome Ricetta'].dropna().tolist() if not df_mie.empty else []
            
        ric_scelta = st.selectbox("Cerca la ricetta nel tuo archivio:", ["-- Seleziona --"] + ricette_list, key=f"ric_scelta_{data_selezionata}")
        
        if ric_scelta != "-- Seleziona --":
            json_str = df_mie[df_mie['Nome Ricetta'] == ric_scelta]['Dati JSON'].iloc[0]
            df_r = pd.read_json(io.StringIO(json_str))
            
            st.markdown("### 1️⃣ La preparazione di oggi")
            with st.expander("🛠️ Modifica ingredienti crudi (solo per questo pasto)", expanded=False):
                mod_qty_raw = {}
                mod_peso_pz = {}
                for idx, row in df_r.iterrows():
                    c1_r, c2_r = st.columns([2, 1]) if row['Unita'] == 'pz' else st.columns([1, 0.01])
                    with c1_r:
                        mod_qty_raw[idx] = st.number_input(f"{row['Nome']} ({row['Unita']})", min_value=0.0, value=float(row['Quantita']), step=1.0 if row['Unita'] == 'pz' else 5.0, key=f"mod_raw_{idx}_{data_selezionata}")
                    if row['Unita'] == 'pz':
                        with c2_r: mod_peso_pz[idx] = st.number_input(f"Peso 1 pz (g)", min_value=0.1, value=float(row.get('Peso_pz', 100.0)), step=1.0, key=f"mod_pz_{idx}_{data_selezionata}")
                    else: mod_peso_pz[idx] = 0.0
            
            new_w_impasto_raw = new_w_altri_raw = new_m_cal_tot = new_m_p_tot = new_m_c_tot = new_m_f_tot = new_m_sat_tot = new_m_fib_tot = 0.0
            variante = False
            for idx, row in df_r.iterrows():
                actual_qta = mod_qty_raw[idx]
                if abs(actual_qta - float(row['Quantita'])) > 0.01: variante = True
                if actual_qta > 0:
                    u = str(row['Unita']).strip()
                    pz_w = mod_peso_pz[idx] if u == 'pz' else 0.0
                    w_ing_raw = actual_qta * pz_w if u == 'pz' else actual_qta
                    if str(row.get('Utilizzo', 'Impasto')) == 'Impasto': new_w_impasto_raw += w_ing_raw
                    else: new_w_altri_raw += w_ing_raw
                    
                    new_m_cal_tot += (float(row.get('Cal_100g', 0)) / 100) * w_ing_raw
                    new_m_p_tot += (float(row.get('Prot_100g', 0)) / 100) * w_ing_raw
                    new_m_c_tot += (float(row.get('Carb_100g', 0)) / 100) * w_ing_raw
                    new_m_f_tot += (float(row.get('Fat_100g', 0)) / 100) * w_ing_raw
                    new_m_sat_tot += (float(row.get('Sat_100g', 0)) / 100) * w_ing_raw
                    new_m_fib_tot += (float(row.get('Fib_100g', 0)) / 100) * w_ing_raw
            
            r_cottura = bool(df_r.iloc[0].get('Cottura_Richiesta', False))
            if r_cottura:
                if str(df_r.iloc[0].get('Cottura_TipoResa', '')) == "Usa % di stima":
                    var_cott_db = float(df_r.iloc[0]['Cottura_Variazione']) if 'Cottura_Variazione' in df_r.columns else -float(df_r.iloc[0].get('Cottura_Calo', 15.0))
                    p_cot_new = new_w_impasto_raw * (1 + var_cott_db / 100.0)
                else:
                    vecchio_impasto_raw = float(df_r.iloc[0].get('Cottura_QtaTeglia', 100.0))
                    vecchio_cotto_reale = float(df_r.iloc[0].get('Cottura_PesoReale', 85.0))
                    var_perc = ((vecchio_cotto_reale - vecchio_impasto_raw) / vecchio_impasto_raw) if vecchio_impasto_raw > 0 else -0.15
                    p_cot_new = new_w_impasto_raw * (1 + var_perc)
            else:
                p_cot_new = new_w_impasto_raw
                
            peso_finale_ricetta = p_cot_new + new_w_altri_raw
            peso_crudo_totale = new_w_impasto_raw + new_w_altri_raw
            porz_orig = float(df_r.iloc[0].get('Ricetta_Porzioni', 1.0))
            if porz_orig <= 0: porz_orig = 1.0
            peso_singola_porzione = peso_finale_ricetta / porz_orig
            
            st.info(f"⚖️ **Report Preparazione:** Peso: **{peso_crudo_totale:.1f} g** | Peso Cotto/Finito: **{peso_finale_ricetta:.1f} g**")
            
            st.markdown("### 2️⃣ Quanto ne hai mangiato?")
            c_mod1, c_mod2 = st.columns(2)
            tipo_inserimento = c_mod1.radio("Scegli come inserire la quantità consumata:", ["In Porzioni (Frazione)", "Grammi esatti"], key=f"tipo_qta_{data_selezionata}")
            
            if tipo_inserimento == "In Porzioni (Frazione)":
                qta_val = c_mod2.number_input("Numero di porzioni mangiate", min_value=0.1, step=0.5, value=1.0, key=f"n_porz_{data_selezionata}")
                rt_consumo = qta_val / porz_orig
                peso_consumato = peso_finale_ricetta * rt_consumo
                valore_salvataggio = qta_val; unita_salvataggio = "porzioni"
            else:
                peso_consumato = c_mod2.number_input("Grammi esatti mangiati (g)", min_value=1.0, step=10.0, value=float(peso_singola_porzione), key=f"g_esatti_{data_selezionata}")
                rt_consumo = peso_consumato / peso_finale_ricetta if peso_finale_ricetta > 0 else 0
                valore_salvataggio = peso_consumato; unita_salvataggio = "g"
                
            m_cal_disp = new_m_cal_tot * rt_consumo; m_p_disp = new_m_p_tot * rt_consumo; m_c_disp = new_m_c_tot * rt_consumo
            m_f_disp = new_m_f_tot * rt_consumo; m_sat_disp = new_m_sat_tot * rt_consumo; m_fib_disp = new_m_fib_tot * rt_consumo
            elemento_inserito = f"🍽️ {ric_scelta} (Variante)" if variante else f"🍽️ {ric_scelta}"
            
            st.write("")
            st.success(f"💡 Stai registrando **{peso_consumato:.1f} g** complessivi.\n\n🔥 Cal: **{m_cal_disp:.0f} kcal** | 🍞 C: **{m_c_disp:.1f}g** | 🥩 P: **{m_p_disp:.1f}g** | 🥑 G: **{m_f_disp:.1f}g**")

            rows_to_add.append({
                "id": uuid.uuid4().hex, "data": str(data_selezionata), "pasto": pasto_sel, "elemento": elemento_inserito,
                "quantita": valore_salvataggio, "unita": unita_salvataggio, "calorie": m_cal_disp, "carboidrati": m_c_disp, 
                "proteine": m_p_disp, "grassi": m_f_disp, "saturi": m_sat_disp, "fibre": m_fib_disp, "user_id": USER_ID,
                "tgt_cal": tgt_cal, "tgt_c": tgt_c, "tgt_p": tgt_p, "tgt_f": tgt_f
            })
            ready_to_add = True

    # =========================================================
    # 🛒 FLUSSO 2: ALIMENTI (SINGOLI O MULTIPLI NEL VASSOIO)
    # =========================================================
    elif tipo_inserimento_diario == "🛒 Alimenti (Singoli o Multipli)":
        st.markdown("### 1️⃣ Componi il pasto nel Vassoio")
        
        c_filt1, c_filt2 = st.columns(2)
        f_tipo = c_filt1.selectbox("Filtra per Tipologia", tipologie_uniche, key=f"f_tipo_{data_selezionata}")
        f_marca = c_filt2.selectbox("Filtra per Marca", marche_uniche, key=f"f_marca_{data_selezionata}")
        
        opzioni_vassoio = get_filtered_ingredients(f_tipo, f_marca)
        
        def update_vassoio_from_selection():
            ing = st.session_state.get(f"vassoio_ing_{data_selezionata}")
            if ing and ing != "-- Seleziona --":
                res = get_macros_and_match(ing)
                unita_def = res[11]
                peso_pz = res[10]
                st.session_state[f"vassoio_u_{data_selezionata}_sel"] = unita_def
                
                try:
                    peso_val = float(peso_pz)
                except (ValueError, TypeError):
                    peso_val = 0.0
                st.session_state[f"vassoio_pz_{data_selezionata}"] = peso_val if peso_val > 0 else 0.0

        c_ing, c_qta, c_unit, c_pz, c_btn = st.columns([3, 1, 1, 1, 1.5])
        ing_scelto = c_ing.selectbox("Cerca alimento:", opzioni_vassoio, key=f"vassoio_ing_{data_selezionata}", on_change=update_vassoio_from_selection)
        qta_val = c_qta.number_input("Quantità", min_value=0.0, step=10.0, key=f"vassoio_qta_{data_selezionata}", value=None)
        
        idx_u = ["g", "ml", "pz"].index(st.session_state.get(f"vassoio_u_{data_selezionata}_sel", "g")) if st.session_state.get(f"vassoio_u_{data_selezionata}_sel") in ["g", "ml", "pz"] else 0
        unit_val = c_unit.selectbox("Unità", options=["g", "ml", "pz"], index=idx_u, key=f"vassoio_u_{data_selezionata}_sel")
        
        if unit_val == "pz": 
            default_pz = MACROS_DB[ing_scelto][8] if ing_scelto != "-- Seleziona --" and ing_scelto in MACROS_DB else 0.0
            pz_w = c_pz.number_input("Peso 1pz (g)", min_value=0.0, step=1.0, value=float(default_pz), key=f"vassoio_pz_{data_selezionata}")
        else: 
            pz_w = 0.0

        if ing_scelto != "-- Seleziona --" and qta_val is not None and qta_val > 0:
            cal_p, p_p, c_p, f_p, _, _, sale_p, _, _, _, _, _ = MACROS_DB[ing_scelto]
            peso_p = qta_val * pz_w if unit_val == "pz" else qta_val
            st.markdown(f"<div style='color:gray; font-size:14px; margin-top:-10px; margin-bottom:10px;'>📊 <b>Valori ({peso_p:.1f}g):</b> {cal_p*peso_p/100:.0f} kcal | C: {c_p*peso_p/100:.1f}g | P: {p_p*peso_p/100:.1f}g | G: {f_p*peso_p/100:.1f}g | Sale: {sale_p*peso_p/100:.2f}g</div>", unsafe_allow_html=True)

        mostra_cottura = st.checkbox("🔥 Applica calo/aumento cottura all'ingrediente", key=f"chk_cotto_{data_selezionata}")
        var_cottura_da_salvare = 0.0
        
        if mostra_cottura and ing_scelto != "-- Seleziona --":
            db_var = MACROS_DB[ing_scelto][7]
            if qta_val is not None and qta_val > 0:
                peso_effettivo_crudo = qta_val * pz_w if unit_val == "pz" else qta_val
                tipo_resa_vassoio = st.radio("Come vuoi calcolare la resa in cottura?", ["Usa % di stima", "Inserisci peso reale cotto"], horizontal=True, key=f"resa_{data_selezionata}")
                
                if tipo_resa_vassoio == "Usa % di stima":
                    c_var1, c_var2 = st.columns([1, 2])
                    var_cottura_da_salvare = c_var1.number_input("% Variazione", value=float(db_var), step=1.0, key=f"var_cott_{data_selezionata}")
                    peso_stimato_cotto = peso_effettivo_crudo * (1 + var_cottura_da_salvare / 100)
                    c_var2.info(f"⚖️ Crudo: **{peso_effettivo_crudo:.1f} g** ➡️ Cotto stimato: **{peso_stimato_cotto:.1f} g**")
                else:
                    c_var1, c_var2 = st.columns([1, 2])
                    peso_cotto_reale = c_var1.number_input("Peso cotto reale (g)", min_value=1.0, value=float(peso_effettivo_crudo * (1 + db_var / 100)), step=10.0, key=f"real_cot_{data_selezionata}")
                    var_cottura_da_salvare = ((peso_cotto_reale - peso_effettivo_crudo) / peso_effettivo_crudo) * 100 if peso_effettivo_crudo > 0 else 0.0
                    c_var2.info(f"⚖️ Variazione calcolata: **{var_cottura_da_salvare:+.1f}%**")
                    
                    if abs(var_cottura_da_salvare - db_var) > 0.1:
                        if st.button("💾 Aggiorna % nel Database Prodotti", key=f"btn_upd_var_{data_selezionata}"):
                            with st.spinner("Aggiornamento in corso..."):
                                cal_db, p_db, c_db, f_db, fib_db, sat_db, sale_db, _, peso_db, unita_db, marca_db, tipo_db = MACROS_DB[ing_scelto]
                                salva_su_cloud(ing_scelto, cal_db, p_db, c_db, f_db, sat_db, fib_db, sale_db, var_cottura_da_salvare, peso_db, unita_db, marca_db, tipo_db)
                                st.success("✅ Variazione aggiornata!")
                                st.rerun()

        st.session_state[f"var_cottura_computed_{data_selezionata}"] = var_cottura_da_salvare

        def on_add_multi():
            ing = st.session_state.get(f"vassoio_ing_{data_selezionata}")
            q = st.session_state.get(f"vassoio_qta_{data_selezionata}")
            u = st.session_state.get(f"vassoio_u_{data_selezionata}_sel")
            pw = st.session_state.get(f"vassoio_pz_{data_selezionata}", 0.0)
            cotto = st.session_state.get(f"chk_cotto_{data_selezionata}", False)
            vc = float(st.session_state.get(f"var_cottura_computed_{data_selezionata}", 0.0))
            if ing and ing != "-- Seleziona --" and q is not None and q > 0:
                st.session_state.diario_multi_items.append({
                    "id": uuid.uuid4().hex, "nome": ing, "quantita": float(q), "unita": u,
                    "peso_pz": float(pw), "is_cotto": cotto, "var_cottura": vc
                })
                st.session_state[f"vassoio_ing_{data_selezionata}"] = "-- Seleziona --"
                st.session_state[f"vassoio_qta_{data_selezionata}"] = None
                st.session_state[f"vassoio_u_{data_selezionata}_sel"] = "g"
                st.session_state[f"chk_cotto_{data_selezionata}"] = False

        can_add = True
        if unit_val == "pz" and pz_w <= 0:
            st.warning("⚠️ Hai selezionato 'pz' ma il peso medio è 0.")
            can_add = False

        with c_btn:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            st.button("➕ Aggiungi al Vassoio", use_container_width=True, on_click=on_add_multi, disabled=(not can_add or qta_val is None or qta_val <= 0), key=f"btn_add_vass_fl2_{data_selezionata}")

        if st.session_state.diario_multi_items:
            st.markdown("### 🛒 Nel tuo Vassoio:")
            m_cal_tot = m_p_tot = m_c_tot = m_f_tot = m_sat_tot = m_fib_tot = m_peso_tot = m_sale_tot = 0.0 
            ingredienti_list = []
            
            for i, item in enumerate(st.session_state.diario_multi_items):
                c1, c2, c3 = st.columns([0.6, 0.3, 0.1])
                
                # --- LOGICA INVERSIONE COTTO/CRUDO NEL VASSOIO ---
                fattore_cottura = (1 + item.get("var_cottura", 0.0) / 100) if item.get("is_cotto") else 1.0
                peso_mostrato = float(item['quantita']) * fattore_cottura
                
                # Il box ora mostra il peso COTTO (se c'è la spunta) o il CRUDO (se non c'è)
                new_mostrato = c2.number_input("Q.tà nel Piatto", min_value=0.0, value=peso_mostrato, step=1.0 if item['unita'] == 'pz' else 5.0, key=f"edit_multi_{item['id']}", label_visibility="collapsed")
                
                # Se l'utente modifica il peso nel vassoio (es. da 120g a 90g cotto), ricalcoliamo il crudo dietro le quinte
                if abs(new_mostrato - peso_mostrato) > 0.01: 
                    st.session_state.diario_multi_items[i]['quantita'] = new_mostrato / fattore_cottura if fattore_cottura > 0 else 0
                    st.rerun()

                if c3.button("❌", key=f"del_multi_{item['id']}"):
                    st.session_state.diario_multi_items = [it for it in st.session_state.diario_multi_items if it['id'] != item['id']]
                    st.rerun()

                cal, p, c, f, fib, sat, sale, _, _, _, _, _ = MACROS_DB[item["nome"]]
                # item['quantita'] ora è sempre il crudo corretto e proporzionato
                peso_eff_crudo = item['quantita'] * item.get("peso_pz", 0.0) if item["unita"] == "pz" else item['quantita']
                
                cal_i = (cal / 100) * peso_eff_crudo; c_i = (c / 100) * peso_eff_crudo; p_i = (p / 100) * peso_eff_crudo
                f_i = (f / 100) * peso_eff_crudo; sat_i = (sat / 100) * peso_eff_crudo; fib_i = (fib / 100) * peso_eff_crudo
                sale_i = (sale / 100) * peso_eff_crudo
                
                m_cal_tot += cal_i; m_p_tot += p_i; m_c_tot += c_i; m_f_tot += f_i; m_sat_tot += sat_i; m_fib_tot += fib_i; m_sale_tot += sale_i
                
                if item.get("is_cotto"):
                    p_cotto = peso_eff_crudo * fattore_cottura
                    m_peso_tot += p_cotto
                    c1.write(f"🔹 **{item['nome']}** (Cotto) *(Equivale a {peso_eff_crudo:.1f}g crudi | Cal: {cal_i:.0f} | C: {c_i:.1f}g | P: {p_i:.1f}g | G: {f_i:.1f}g | Sale: {sale_i:.2f}g)*")
                else:
                    m_peso_tot += peso_eff_crudo
                    c1.write(f"🔹 **{item['nome']}** *(Peso: {peso_eff_crudo:.1f}g | Cal: {cal_i:.0f} | C: {c_i:.1f}g | P: {p_i:.1f}g | G: {f_i:.1f}g | Sale: {sale_i:.2f}g)*")
                    
                ingredienti_list.append(f"{new_mostrato:.1f}{item['unita']} {item['nome']}")
                
            st.info(f"⚖️ **Report Vassoio:** Peso: **{m_peso_tot:.1f} g** | 🔥 **{m_cal_tot:.0f} kcal** | 🍞 C: **{m_c_tot:.1f}g** | 🥩 P: **{m_p_tot:.1f}g** | 🥑 G: **{m_f_tot:.1f}g** | Sat: **{m_sat_tot:.1f}g** | Fib: **{m_fib_tot:.1f}g** | Sale: **{m_sale_tot:.2f}g**")
            
            dividi_porzioni = st.checkbox("🔪 Dividi in porzioni", key=f"dividi_vass_{data_selezionata}")
            
            if dividi_porzioni:
                st.markdown("#### 🥧 Resa e Porzioni del Vassoio")
                num_porzioni = st.number_input("In quante porzioni totali dividi questo vassoio? (max 5)", min_value=1, max_value=5, step=1, value=2, key=f"n_porz_vass_{data_selezionata}")
                
                porzioni_perc = []
                perc_rimanente = 100.0
                porzioni_selezionate = []

                cols_perc = st.columns(num_porzioni)
                somma_parziale = 0.0
                for i in range(num_porzioni - 1):
                    with cols_perc[i]:
                        p_val = st.number_input(f"% Porz. {i+1}", min_value=0.0, max_value=100.0, value=100.0/num_porzioni, step=1.0, key=f"perc_p_{i}_{data_selezionata}")
                        porzioni_perc.append(p_val)
                        somma_parziale += p_val
                perc_rimanente = 100.0 - somma_parziale
                porzioni_perc.append(perc_rimanente)
                with cols_perc[-1]:
                    st.text_input(f"% Porz. {num_porzioni} (Resto)", value=f"{perc_rimanente:.1f}%", disabled=True, key=f"resto_txt_{data_selezionata}")
                if perc_rimanente < 0: st.error("⚠️ La somma delle percentuali supera il 100%.")

                st.markdown("### 2️⃣ Quali porzioni stai mangiando?")
                cols_chk = st.columns(num_porzioni)
                for i in range(num_porzioni):
                    perc = porzioni_perc[i]
                    with cols_chk[i]:
                        if perc >= 0:
                            if st.checkbox(f"🍽️ Mangio Porz. {i+1} ({perc:.1f}%)", value=(i==0), key=f"mangio_chk_{i}_{data_selezionata}"):
                                porzioni_selezionate.append(i)
                            p_peso = m_peso_tot * (perc / 100.0); p_cal = m_cal_tot * (perc / 100.0)
                            p_c = m_c_tot * (perc / 100.0); p_p = m_p_tot * (perc / 100.0); p_f = m_f_tot * (perc / 100.0)
                            st.caption(f"⚖️ {p_peso:.1f}g | 🔥 {p_cal:.0f} kcal \n🍞 C: {p_c:.1f}g | 🥩 P: {p_p:.1f}g | 🥑 G: {p_f:.1f}g")

                tot_perc_consumata = sum([porzioni_perc[i] for i in porzioni_selezionate])
                rt_consumo_vassoio = tot_perc_consumata / 100.0
            else:
                num_porzioni = 1
                porzioni_perc = [100.0]
                perc_rimanente = 0.0
                porzioni_selezionate = [0]
                tot_perc_consumata = 100.0
                rt_consumo_vassoio = 1.0

            if rt_consumo_vassoio > 0 and perc_rimanente >= 0:
                p_peso = m_peso_tot * rt_consumo_vassoio
                p_cal = m_cal_tot * rt_consumo_vassoio
                p_c = m_c_tot * rt_consumo_vassoio
                p_p = m_p_tot * rt_consumo_vassoio
                p_f = m_f_tot * rt_consumo_vassoio
                
                if dividi_porzioni:
                    st.success(f"💡 Stai registrando il **{tot_perc_consumata:.1f}%** del vassoio.\n\n⚖️ Peso consumato: **{p_peso:.1f} g** | 🔥 Cal: **{p_cal:.0f} kcal** | 🍞 C: **{p_c:.1f}g** | 🥩 P: **{p_p:.1f}g** | 🥑 G: **{p_f:.1f}g**")
            
            st.markdown("### 3️⃣ Salvataggio")
            nome_gruppo = st.text_input("Vuoi raggruppare questi elementi in un'unica voce? Inserisci un nome (es. 'Mix Proteico') o lascia vuoto per salvarli separati:", key=f"nome_gr_{data_selezionata}")
            
            if rt_consumo_vassoio > 0 and perc_rimanente >= 0:
                if nome_gruppo.strip():
                    dettaglio = ", ".join(ingredienti_list)
                    rows_to_add.append({
                        "id": uuid.uuid4().hex, "data": str(data_selezionata), "pasto": pasto_sel,
                        "elemento": f"📦 {nome_gruppo.strip()} [{dettaglio}]", "quantita": tot_perc_consumata, "unita": "%",
                        "calorie": m_cal_tot * rt_consumo_vassoio, "carboidrati": m_c_tot * rt_consumo_vassoio, "proteine": m_p_tot * rt_consumo_vassoio,
                        "grassi": m_f_tot * rt_consumo_vassoio, "saturi": m_sat_tot * rt_consumo_vassoio, "fibre": m_fib_tot * rt_consumo_vassoio, "user_id": USER_ID,
                        "tgt_cal": tgt_cal, "tgt_c": tgt_c, "tgt_p": tgt_p, "tgt_f": tgt_f
                    })
                else:
                    for item in st.session_state.diario_multi_items:
                        cal, p, c, f, fib, sat, _, _, _, _, _, _ = MACROS_DB[item["nome"]]
                        peso_eff_crudo = item['quantita'] * item.get("peso_pz", 0.0) if item["unita"] == "pz" else item['quantita']
                        
                        # --- MODIFICA SMART: Ricalcolo su Peso Cotto ---
                        if item.get("is_cotto"):
                            # Calcoliamo il peso finale cotto
                            peso_finale_cotto = peso_eff_crudo * (1 + item.get("var_cottura", 0.0) / 100)
                            
                            # Registriamo come "Quantita" da mostrare nel diario il peso COTTO
                            qta_da_salvare = peso_finale_cotto * rt_consumo_vassoio
                            unita_da_salvare = "g" # Forza grammi per il cotto
                            
                            # Integriamo nel nome l'origine a crudo per chiarezza nel diario
                            elemento_salvato = f"🛒 {item['nome']} (Da crudo: {peso_eff_crudo * rt_consumo_vassoio:.1f}g)"
                        else:
                            # Comportamento standard per cibi non cotti
                            qta_da_salvare = item['quantita'] * rt_consumo_vassoio
                            unita_da_salvare = item['unita']
                            elemento_salvato = f"🛒 {item['nome']}"
                        # -----------------------------------------------

                        rows_to_add.append({
                            "id": uuid.uuid4().hex, "data": str(data_selezionata), "pasto": pasto_sel,
                            "elemento": elemento_salvato, "quantita": qta_da_salvare, "unita": unita_da_salvare,
                            "calorie": (cal/100) * peso_eff_crudo * rt_consumo_vassoio, "carboidrati": (c/100) * peso_eff_crudo * rt_consumo_vassoio, 
                            "proteine": (p/100) * peso_eff_crudo * rt_consumo_vassoio, "grassi": (f/100) * peso_eff_crudo * rt_consumo_vassoio, 
                            "saturi": (sat/100) * peso_eff_crudo * rt_consumo_vassoio, "fibre": (fib/100) * peso_eff_crudo * rt_consumo_vassoio, 
                            "user_id": USER_ID, "tgt_cal": tgt_cal, "tgt_c": tgt_c, "tgt_p": tgt_p, "tgt_f": tgt_f
                        })
                ready_to_add = True

    # =========================================================
    # ⏱️ FLUSSO 3: RICETTA LIBERA (AL VOLO)
    # =========================================================
    elif tipo_inserimento_diario == "⏱️ Ricetta Libera (Al volo)":
        st.write("Aggiungi gli ingredienti per calcolare una preparazione veloce.")
        
        c_filt1, c_filt2 = st.columns(2)
        f_tipo_lib = c_filt1.selectbox("Filtra per Tipologia", tipologie_uniche, key=f"f_tipo_lib_{data_selezionata}")
        f_marca_lib = c_filt2.selectbox("Filtra per Marca", marche_uniche, key=f"f_marca_lib_{data_selezionata}")
        
        opzioni_libera = get_filtered_ingredients(f_tipo_lib, f_marca_lib)

        def update_lib_from_selection():
            ing = st.session_state.get(f"ing_lib_sel_{data_selezionata}")
            if ing and ing != "-- Seleziona --":
                res = get_macros_and_match(ing)
                unita_def = res[11]
                peso_pz = res[10]
                st.session_state[f"unit_lib_val_{data_selezionata}_sel"] = unita_def
                st.session_state[f"lib_pz_w_{data_selezionata}"] = peso_pz if peso_pz > 0 else 0.0

        c_ing, c_qta, c_unit, c_pz, c_btn = st.columns([3, 1, 1, 1, 1.5])
        ing_libero = c_ing.selectbox("Ingrediente", opzioni_libera, key=f"ing_lib_sel_{data_selezionata}", on_change=update_lib_from_selection)
        qta_libera = c_qta.number_input("Quantità", min_value=0.0, step=10.0, key=f"qta_lib_val_{data_selezionata}", value=None)
        
        idx_u_lib = ["g", "ml", "pz"].index(st.session_state.get(f"unit_lib_val_{data_selezionata}_sel", "g")) if st.session_state.get(f"unit_lib_val_{data_selezionata}_sel") in ["g", "ml", "pz"] else 0
        unit_libera = c_unit.selectbox("Unità", options=["g", "ml", "pz"], key=f"unit_lib_val_{data_selezionata}_sel", index=idx_u_lib)
        
        if unit_libera == "pz": 
            default_pz_lib = MACROS_DB[ing_libero][8] if ing_libero != "-- Seleziona --" and ing_libero in MACROS_DB else 0.0
            pz_w_lib = c_pz.number_input("Peso 1pz (g)", min_value=0.0, step=1.0, value=float(default_pz_lib), key=f"lib_pz_w_{data_selezionata}")
        else: pz_w_lib = 0.0

        if ing_libero != "-- Seleziona --" and qta_libera is not None and qta_libera > 0:
            cal_l, p_l, c_l, f_l, _, _, sale_l, _, _, _, _, _ = MACROS_DB[ing_libero]
            peso_l = qta_libera * pz_w_lib if unit_libera == "pz" else qta_libera
            st.markdown(f"<div style='color:gray; font-size:14px; margin-top:-10px; margin-bottom:10px;'>📊 <b>Valori ({peso_l:.1f}g):</b> {cal_l*peso_l/100:.0f} kcal | C: {c_l*peso_l/100:.1f}g | P: {p_l*peso_l/100:.1f}g | G: {f_l*peso_l/100:.1f}g | Sale: {sale_l*peso_l/100:.2f}g</div>", unsafe_allow_html=True)
            
        def on_add_libero():
            ing = st.session_state.get(f"ing_lib_sel_{data_selezionata}", "-- Seleziona --")
            qta = st.session_state.get(f"qta_lib_val_{data_selezionata}")
            unit = st.session_state.get(f"unit_lib_val_{data_selezionata}_sel")
            pw = st.session_state.get(f"lib_pz_w_{data_selezionata}", 0.0)
            if ing != "-- Seleziona --" and qta is not None and qta > 0:
                st.session_state.temp_recipe_diario.append({
                    "id": uuid.uuid4().hex, "nome": ing, "quantita": float(qta), "unita": unit, "peso_pz": float(pw)
                })
                st.session_state[f"ing_lib_sel_{data_selezionata}"] = "-- Seleziona --"
                st.session_state[f"qta_lib_val_{data_selezionata}"] = None
                st.session_state[f"unit_lib_val_{data_selezionata}_sel"] = "g"

        can_add_lib = True
        if unit_libera == "pz" and pz_w_lib <= 0: can_add_lib = False

        with c_btn:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            st.button("➕ Aggiungi", use_container_width=True, on_click=on_add_libero, disabled=(not can_add_lib or qta_libera is None or qta_libera <= 0), key=f"btn_add_lib_{data_selezionata}")
                
        if st.session_state.temp_recipe_diario:
            st.markdown("---")
            w_raw_tot = m_cal_tot = m_p_tot = m_c_tot = m_f_tot = m_sat_tot = m_fib_tot = m_sale_tot = 0.0
            
            for i, ing in enumerate(st.session_state.temp_recipe_diario):
                c1, c2, c3 = st.columns([0.6, 0.3, 0.1])
                new_qty = c2.number_input("Q.tà", min_value=0.0, value=float(ing['quantita']), step=1.0 if ing['unita'] == 'pz' else 5.0, key=f"edit_lib_{ing['id']}", label_visibility="collapsed")
                if new_qty != ing['quantita']: st.session_state.temp_recipe_diario[i]['quantita'] = new_qty
                if c3.button("❌", key=f"del_lib_{ing['id']}"):
                    st.session_state.temp_recipe_diario = [item for item in st.session_state.temp_recipe_diario if item['id'] != ing['id']]
                    st.rerun()
                
                cal, p, c, f, fib, sat, sale, _, _, _, _, _ = MACROS_DB[ing['nome']]
                peso_eff = new_qty * ing.get("peso_pz", 0.0) if ing['unita'] == 'pz' else new_qty
                
                w_raw_tot += peso_eff
                cal_i = (cal / 100) * peso_eff; p_i = (p / 100) * peso_eff; c_i = (c / 100) * peso_eff; f_i = (f / 100) * peso_eff
                sale_i = (sale / 100) * peso_eff
                
                m_cal_tot += cal_i; m_p_tot += p_i; m_c_tot += c_i; m_f_tot += f_i
                m_sat_tot += (sat / 100) * peso_eff; m_fib_tot += (fib / 100) * peso_eff; m_sale_tot += sale_i
                
                c1.write(f"🔹 **{ing['nome']}** *(Peso: {peso_eff:.1f}g | Cal: {cal_i:.0f} | C: {c_i:.1f}g | P: {p_i:.1f}g | G: {f_i:.1f}g | Sale: {sale_i:.2f}g)*")
                
            nome_libera = st.text_input("Dai un nome per ricordarla nel diario:", "Pasto al volo", key=f"n_lib_{data_selezionata}")
            peso_cotto_libero = st.number_input("Peso cotto finale (g)", min_value=1.0, value=float(w_raw_tot), key=f"peso_cot_lib_{data_selezionata}")
            
            st.info(f"⚖️ **Report:** Peso a crudo: **{w_raw_tot:.1f} g** | Cotto/Finito: **{peso_cotto_libero:.1f} g** | 🔥 **{m_cal_tot:.0f} kcal** | 🍞 C: **{m_c_tot:.1f}g** | 🥩 P: **{m_p_tot:.1f}g** | 🥑 G: **{m_f_tot:.1f}g** | Sale: **{m_sale_tot:.2f}g**")
            
            dividi_libera = st.checkbox("🔪 Dividi in porzioni", key=f"dividi_lib_{data_selezionata}")
            
            if dividi_libera:
                st.markdown("#### 🥧 Resa e Porzioni")
                num_porzioni_lib = st.number_input("In quante porzioni dividi? (max 5)", min_value=1, max_value=5, step=1, value=2, key=f"num_porz_lib_{data_selezionata}")
                
                porzioni_perc_lib = []
                perc_rimanente_lib = 100.0
                porzioni_selezionate_lib = []
                
                cols_perc_lib = st.columns(num_porzioni_lib)
                somma_parziale_lib = 0.0
                for i in range(num_porzioni_lib - 1):
                    with cols_perc_lib[i]:
                        p_val_lib = st.number_input(f"% Porz. {i+1}", min_value=0.0, max_value=100.0, value=100.0/num_porzioni_lib, step=1.0, key=f"perc_p_lib_{i}_{data_selezionata}")
                        porzioni_perc_lib.append(p_val_lib)
                        somma_parziale_lib += p_val_lib
                perc_rimanente_lib = 100.0 - somma_parziale_lib
                porzioni_perc_lib.append(perc_rimanente_lib)
                with cols_perc_lib[-1]:
                    st.text_input(f"% Porz. {num_porzioni_lib} (Resto)", value=f"{perc_rimanente_lib:.1f}%", disabled=True, key=f"resto_lib_txt_{data_selezionata}")
                if perc_rimanente_lib < 0: st.error("⚠️ La somma supera il 100%. Riduci i valori.")

                st.markdown("### 2️⃣ Quali porzioni mangi?")
                cols_chk_lib = st.columns(num_porzioni_lib)
                for i in range(num_porzioni_lib):
                    perc = porzioni_perc_lib[i]
                    with cols_chk_lib[i]:
                        if perc >= 0:
                            if st.checkbox(f"🍽️ Mangio Porz. {i+1} ({perc:.1f}%)", value=(i==0), key=f"mangio_chk_lib_{i}_{data_selezionata}"):
                                porzioni_selezionate_lib.append(i)
                            p_peso = peso_cotto_libero * (perc / 100.0)
                            p_cal = m_cal_tot * (perc / 100.0)
                            p_c = m_c_tot * (perc / 100.0)
                            p_p = m_p_tot * (perc / 100.0)
                            p_f = m_f_tot * (perc / 100.0)
                            st.caption(f"⚖️ {p_peso:.1f}g | 🔥 {p_cal:.0f} kcal \n🍞 C: {p_c:.1f}g | 🥩 P: {p_p:.1f}g | 🥑 G: {p_f:.1f}g")

                rt_consumo_lib = sum([porzioni_perc_lib[i] for i in porzioni_selezionate_lib]) / 100.0
            else:
                num_porzioni_lib = 1
                porzioni_perc_lib = [100.0]
                porzioni_selezionate_lib = [0]
                perc_rimanente_lib = 0.0
                rt_consumo_lib = 1.0

            if rt_consumo_lib > 0 and perc_rimanente_lib >= 0:
                p_peso = peso_cotto_libero * rt_consumo_lib
                p_cal = m_cal_tot * rt_consumo_lib
                p_c = m_c_tot * rt_consumo_lib
                p_p = m_p_tot * rt_consumo_lib
                p_f = m_f_tot * rt_consumo_lib
                
                if dividi_libera:
                    st.success(f"💡 Stai registrando il **{rt_consumo_lib*100:.1f}%** dell'intera preparazione.\n\n⚖️ Peso consumato: **{p_peso:.1f} g** | 🔥 Cal: **{p_cal:.0f} kcal** | 🍞 C: **{p_c:.1f}g** | 🥩 P: **{p_p:.1f}g** | 🥑 G: **{p_f:.1f}g**")
                
                dettaglio_lib = ", ".join([f"{ing['quantita']:g}{ing['unita']} {ing['nome']}" for ing in st.session_state.temp_recipe_diario])
                elemento_inserito = f"⏱️ {nome_libera} [{dettaglio_lib}]"

                rows_to_add.append({
                    "id": uuid.uuid4().hex, "data": str(data_selezionata), "pasto": pasto_sel,
                    "elemento": elemento_inserito, "quantita": rt_consumo_lib*100, "unita": "%",
                    "calorie": m_cal_tot * rt_consumo_lib, "carboidrati": m_c_tot * rt_consumo_lib, "proteine": m_p_tot * rt_consumo_lib,
                    "grassi": m_f_tot * rt_consumo_lib, "saturi": m_sat_tot * rt_consumo_lib, "fibre": m_fib_tot * rt_consumo_lib, "user_id": USER_ID,
                    "tgt_cal": tgt_cal, "tgt_c": tgt_c, "tgt_p": tgt_p, "tgt_f": tgt_f
                })
                ready_to_add = True

    # =========================================================
    # SALVATAGGIO UNIFICATO VIA SQL
    # =========================================================
    st.write("")
    if ready_to_add:
        if st.button("➕ Registra Pasto", type="primary", use_container_width=True, key=f"btn_save_{data_selezionata}"):
            with st.spinner("Salvataggio in corso..."):
                try:
                    if data_selezionata > oggi_date: stato_ins = "Pianificato"
                    elif data_selezionata == oggi_date and is_planner: stato_ins = "Pianificato"
                    else: stato_ins = "Consumato"

                    with conn.engine.begin() as e:
                        query_sql = ("INSERT INTO diario (id, data, pasto, elemento, quantita, unita, calorie, "
                                     "carboidrati, proteine, grassi, saturi, fibre, user_id, tgt_cal, tgt_c, tgt_p, tgt_f, stato) "
                                     "VALUES (:id, :data, :pasto, :elemento, :quantita, :unita, :calorie, "
                                     ":carboidrati, :proteine, :grassi, :saturi, :fibre, :user_id, :tgt_cal, :tgt_c, :tgt_p, :tgt_f, :stato)")
                        
                        for row_dict in rows_to_add:
                            row_dict["stato"] = stato_ins
                            e.execute(text(query_sql), row_dict)
                    
                    st.session_state.diario_multi_items = []
                    st.session_state.temp_recipe_diario = [] 
                    st.cache_data.clear()
                    st.success("✅ Pasto registrato con successo!")
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Errore di salvataggio SQL: {e}")
