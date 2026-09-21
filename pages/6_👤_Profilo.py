import streamlit as st
import pandas as pd
import plotly.express as px
from components.nav import render_top_nav
from services.db import get_profilo_utente, salva_profilo_utente, get_storico_profilo

# 1. Controllo di sicurezza centralizzato
from components.auth import require_login
require_login()

st.set_page_config(page_title="NutriLab24 - Profilo", layout="wide")
render_top_nav("Profilo e Obiettivi")

USER_ID = st.session_state.username

st.title("👤 Profilo, Misure e Obiettivi")
st.markdown("#### *Calcola il tuo fabbisogno, gestisci i target con logica avanzata e monitora i progressi.* 📈")
st.write("")

# Recupero profilo attuale dal DB
df_prof = get_profilo_utente(USER_ID)
curr_peso = 70.0; curr_alt = 170; curr_eta = 30; curr_sesso = "Uomo"; curr_att = "Sedentario"
curr_ob = "Mantenimento"
curr_cal = 2000.0; curr_c = 200.0; curr_p = 150.0; curr_f = 60.0
curr_collo = curr_petto = curr_vita = curr_fianchi = curr_braccio = curr_coscia = curr_polpaccio = 0.0
curr_mgrassa = curr_mmusc = curr_mossea = curr_acqua = 0.0

if not df_prof.empty:
    r = df_prof.iloc[0]
    curr_peso = float(r.get('peso', 70.0))
    curr_alt = int(r.get('altezza', 170))
    curr_eta = int(r.get('eta', 30))
    curr_sesso = str(r.get('sesso', 'Uomo'))
    curr_att = str(r.get('attivita', 'Sedentario'))
    curr_ob = str(r.get('obiettivo', 'Mantenimento'))
    
    curr_cal = float(r.get('tgt_cal', 2000.0))
    curr_c = float(r.get('tgt_c', 200.0))
    curr_p = float(r.get('tgt_p', 150.0))
    curr_f = float(r.get('tgt_f', 60.0))
    
    curr_collo = float(r.get('circ_collo', 0.0))
    curr_petto = float(r.get('circ_petto', 0.0))
    curr_vita = float(r.get('circ_vita', 0.0))
    curr_fianchi = float(r.get('circ_fianchi', 0.0))
    curr_braccio = float(r.get('circ_braccio', 0.0))
    curr_coscia = float(r.get('circ_coscia', 0.0))
    curr_polpaccio = float(r.get('circ_polpaccio', 0.0))
    
    curr_mgrassa = float(r.get('massa_grassa', 0.0))
    curr_mmusc = float(r.get('massa_muscolare', 0.0))
    curr_mossea = float(r.get('massa_ossea', 0.0))
    curr_acqua = float(r.get('acqua_corporea', 0.0))

# Inizializzazione Session State per i target
if "t_cal" not in st.session_state: st.session_state.t_cal = curr_cal
if "t_c" not in st.session_state: st.session_state.t_c = curr_c
if "t_p" not in st.session_state: st.session_state.t_p = curr_p
if "t_f" not in st.session_state: st.session_state.t_f = curr_f

tab_dati, tab_storico = st.tabs(["📝 Dati e Calcolatore Macros", "📊 Andamento e Storico"])

with tab_dati:
    # ---------------------------------------------------------------------------------
    # SEZIONE 1: Dati Fissi
    # ---------------------------------------------------------------------------------
    st.markdown("### 1️⃣ Dati Biometrici Base")
    c_eta, c_alt, c_ses = st.columns(3)
    new_eta = c_eta.number_input("Età", min_value=10, max_value=120, value=curr_eta, step=1)
    new_alt = c_alt.number_input("Altezza (cm)", min_value=100, max_value=250, value=curr_alt, step=1)
    new_sesso = c_ses.selectbox("Sesso", ["Uomo", "Donna"], index=0 if curr_sesso=="Uomo" else 1)

    st.divider()

    # ---------------------------------------------------------------------------------
    # SEZIONE 2: Composizione Corporea
    # ---------------------------------------------------------------------------------
    st.markdown("### 2️⃣ Peso e Composizione Corporea")
    
    c_data, c_peso, c_bmi = st.columns([1, 1, 1.5])
    
    with c_data:
        data_pesata = st.date_input("Data", pd.to_datetime('today').date())
        
    with c_peso:
        new_peso = st.number_input("Peso (kg)", min_value=30.0, max_value=250.0, value=curr_peso, step=0.5)
        
    with c_bmi:
        # Questo <br> abbassa l'IMC per allinearlo ai box di input a fianco
        st.markdown("<br>", unsafe_allow_html=True)
        bmi = new_peso / ((new_alt / 100) ** 2) if new_alt > 0 else 0
        st.markdown(f"⚖️ **IMC: {bmi:.1f}**", help="Indice di Massa Corporea: Rapporto tra il peso e il quadrato dell'altezza")
    
    st.write("")
    cc1, cc2, cc3, cc4 = st.columns(4)
    new_mgrassa = cc1.number_input("% Massa Grassa", min_value=0.0, value=curr_mgrassa, step=0.5, help="La stima del grasso totale rispetto alla massa complessiva.")
    new_mmusc = cc2.number_input("Massa Muscolare (kg)", min_value=0.0, value=curr_mmusc, step=0.5, help="La quantità totale di muscolo espressa in unità di peso.")
    new_mossea = cc3.number_input("Massa Ossea (kg)", min_value=0.0, value=curr_mossea, step=0.1, help="Il peso specifico dello scheletro e dei minerali ossei.")
    new_acqua = cc4.number_input("% Acqua Corporea", min_value=0.0, value=curr_acqua, step=0.5, help="Indica il livello di idratazione.")

    with st.expander("📏 Circonferenze Corporee (Opzionali)"):
        m1, m2, m3, m4 = st.columns(4)
        new_collo = m1.number_input("Collo (cm)", min_value=0.0, value=curr_collo, step=0.5)
        new_petto = m2.number_input("Petto/Dorso (cm)", min_value=0.0, value=curr_petto, step=0.5)
        new_vita = m3.number_input("Vita/Addome (cm)", min_value=0.0, value=curr_vita, step=0.5)
        new_fianchi = m4.number_input("Fianchi (cm)", min_value=0.0, value=curr_fianchi, step=0.5)
        
        m5, m6, m7, _ = st.columns(4)
        new_braccio = m5.number_input("Braccio (cm)", min_value=0.0, value=curr_braccio, step=0.5)
        new_coscia = m6.number_input("Coscia (cm)", min_value=0.0, value=curr_coscia, step=0.5)
        new_polpaccio = m7.number_input("Polpaccio (cm)", min_value=0.0, value=curr_polpaccio, step=0.5)

    st.divider()

    # ---------------------------------------------------------------------------------
    # SEZIONE 3: Livello di Attività e Obiettivo
    # ---------------------------------------------------------------------------------
    st.markdown("### 3️⃣ Livello di Attività e Obiettivo")
    
    c_att, c_ob = st.columns(2)
    att_options = [
        "Sedentario (Lavoro da scrivania, zero o poco sport)",
        "Leggero (Passeggiate, sport 1-3 volte a settimana)",
        "Moderato (Sport 3-5 volte a settimana)",
        "Intenso (Sport 6-7 volte, allenamenti duri)",
        "Atleta (Doppio allenamento o lavoro fisico pesante)"
    ]
    idx_att = 0
    for i, opt in enumerate(att_options):
        if curr_att.split(" ")[0].lower() in opt.lower():
            idx_att = i; break
            
    new_att = c_att.selectbox("Livello di Attività Fisica", att_options, index=idx_att)

    ob_options = ["Dimagrimento", "Definizione", "Mantenimento", "Ricomposizione Corporea", "Crescita Muscolare", "Aumento Peso"]
    idx_ob = ob_options.index(curr_ob) if curr_ob in ob_options else 2
    new_ob = c_ob.selectbox("Cosa vuoi ottenere?", ob_options, index=idx_ob)

    # Calcolo Teorico Mifflin-St Jeor
    if new_sesso == "Uomo": bmr = (10 * new_peso) + (6.25 * new_alt) - (5 * new_eta) + 5
    else: bmr = (10 * new_peso) + (6.25 * new_alt) - (5 * new_eta) - 161
    
    moltiplicatori = {"Sedentario": 1.2, "Leggero": 1.375, "Moderato": 1.55, "Intenso": 1.725, "Atleta": 1.9}
    tdee = bmr * moltiplicatori.get(new_att.split(" ")[0], 1.2)
    adj = {"Dimagrimento": -500, "Definizione": -300, "Mantenimento": 0, "Ricomposizione Corporea": 0, "Crescita Muscolare": 300, "Aumento Peso": 500}
    sugg_cal = tdee + adj.get(new_ob, 0)
    sugg_p = new_peso * (2.2 if new_ob in ["Definizione", "Ricomposizione Corporea", "Dimagrimento"] else 2.0)
    sugg_f = (sugg_cal * 0.25) / 9.0
    sugg_c = max(0.0, (sugg_cal - (sugg_p * 4) - (sugg_f * 9)) / 4.0)

    st.info(f"💡 **Fabbisogno Suggerito (Mifflin-St Jeor):** 🔥 **{sugg_cal:.0f} kcal** | 🍞 C: **{sugg_c:.0f}g** | 🥩 P: **{sugg_p:.0f}g** | 🥑 G: **{sugg_f:.0f}g**")
    
    def applica_suggeriti():
        st.session_state.t_cal = float(round(sugg_cal))
        st.session_state.t_c = float(round(sugg_c))
        st.session_state.t_p = float(round(sugg_p))
        st.session_state.t_f = float(round(sugg_f))
        
    st.button("🪄 Applica Valori Suggeriti", on_click=applica_suggeriti, use_container_width=True)

    st.markdown("### 🎯 I Tuoi Target Attuali e Gestione Macros")
    
    def update_macros(modificato):
        preserva = st.session_state.get("preserva_cal", True)
        lock_p = st.session_state.get("lock_p", False)
        lock_f = st.session_state.get("lock_f", False)
        lock_c = st.session_state.get("lock_c", False)

        c = st.session_state.get("t_c", 0.0)
        p = st.session_state.get("t_p", 0.0)
        f = st.session_state.get("t_f", 0.0)
        cal = st.session_state.get("t_cal", 0.0)

        if not preserva:
            if modificato in ['c', 'p', 'f']:
                st.session_state.t_cal = float(round((c * 4) + (p * 4) + (f * 9)))
            return

        cal_actual = (c * 4) + (p * 4) + (f * 9)
        diff = cal - cal_actual
        
        if abs(diff) > 2:
            can_edit_c = not lock_c and modificato != 'c'
            can_edit_p = not lock_p and modificato != 'p'
            can_edit_f = not lock_f and modificato != 'f'
            
            editable_count = sum([can_edit_c, can_edit_p, can_edit_f])
            
            if editable_count == 0:
                st.session_state.t_cal = float(round(cal_actual))
            else:
                if can_edit_c: st.session_state.t_c = max(0.0, c + (diff / editable_count / 4.0))
                if can_edit_p: st.session_state.t_p = max(0.0, p + (diff / editable_count / 4.0))
                if can_edit_f: st.session_state.t_f = max(0.0, f + (diff / editable_count / 9.0))

    # Creazione delle colonne con flag e input raggruppati per perfetto allineamento verticale
    tc1, tc2, tc3, tc4 = st.columns(4)
    
    with tc1:
        preserva_cal = st.checkbox("🔒 Preserva Calorie", value=True, key="preserva_cal", on_change=update_macros, args=('cal',))
        final_cal = st.number_input("Target Calorie (kcal)", key="t_cal", step=50.0, on_change=update_macros, args=('cal',))
        
    with tc2:
        lock_c = st.checkbox("🔒 Blocca Carboidrati", value=False, key="lock_c")
        final_c = st.number_input("Carboidrati (g)", key="t_c", step=5.0, on_change=update_macros, args=('c',))
        
    with tc3:
        lock_p = st.checkbox("🔒 Blocca Proteine", value=False, key="lock_p")
        final_p = st.number_input("Proteine (g)", key="t_p", step=5.0, on_change=update_macros, args=('p',))
        
    with tc4:
        lock_f = st.checkbox("🔒 Blocca Grassi", value=False, key="lock_f")
        final_f = st.number_input("Grassi (g)", key="t_f", step=5.0, on_change=update_macros, args=('f',))

    # Calcolo Percentuali e Rapporti su kg di peso corporeo
    tot_cal_macro = (final_c * 4) + (final_p * 4) + (final_f * 9)
    p_carb = (final_c * 4 / tot_cal_macro * 100) if tot_cal_macro > 0 else 0
    p_prot = (final_p * 4 / tot_cal_macro * 100) if tot_cal_macro > 0 else 0
    p_gras = (final_f * 9 / tot_cal_macro * 100) if tot_cal_macro > 0 else 0

    r_carb = final_c / new_peso if new_peso > 0 else 0
    r_prot = final_p / new_peso if new_peso > 0 else 0
    r_gras = final_f / new_peso if new_peso > 0 else 0

    # Riquadro compatto, pulito e nativo
    st.info(f"📊 **Ripartizione Energetica:** 🍞 C: **{p_carb:.1f}%** ({r_carb:.2f} g/kg)  &nbsp;|&nbsp;  🥩 P: **{p_prot:.1f}%** ({r_prot:.2f} g/kg)  &nbsp;|&nbsp;  🥑 G: **{p_gras:.1f}%** ({r_gras:.2f} g/kg)")

    st.write("")
    if st.button(f"💾 Salva Profilo e Registra Misurazione al {data_pesata.strftime('%d/%m/%Y')}", type="primary", use_container_width=True):
        with st.spinner("Salvataggio in corso..."):
            salvataggio_att = new_att.split(" (")[0]
            salva_profilo_utente(
                USER_ID, data_pesata, new_peso, new_alt, new_eta, new_sesso, salvataggio_att, 
                final_cal, final_c, final_p, final_f, new_ob, 
                new_collo, new_petto, new_vita, new_fianchi, new_braccio, new_coscia, new_polpaccio,
                new_mgrassa, new_mmusc, new_mossea, new_acqua
            )
            st.success("✅ Dati aggiornati! La misurazione è stata registrata nello storico.")

with tab_storico:
    df_storico = get_storico_profilo(USER_ID)
    if not df_storico.empty:
        df_storico['data'] = pd.to_datetime(df_storico['data'])
        
        c_peso, c_mis = st.columns([1, 1])
        with c_peso:
            st.markdown("### 📉 Andamento Peso (kg)")
            fig_peso = px.line(df_storico, x='data', y='peso', markers=True, hover_data=['obiettivo'], color_discrete_sequence=['#FF4B4B'])
            fig_peso.update_layout(xaxis_title="", yaxis_title="Peso (kg)", hovermode="x unified", height=350, showlegend=False)
            st.plotly_chart(fig_peso, use_container_width=True)

        with c_mis:
            st.markdown("### 📊 Composizione Corporea (%)")
            comp_cols = ['massa_grassa', 'acqua_corporea']
            comp_labels = {'massa_grassa': 'Massa Grassa %', 'acqua_corporea': 'Acqua Corporea %'}
            comp_valide = [col for col in comp_cols if df_storico[col].sum() > 0]
            
            if comp_valide:
                fig_comp = px.line(df_storico, x='data', y=comp_valide, markers=True, color_discrete_sequence=['#FFA500', '#00BFFF'])
                fig_comp.for_each_trace(lambda t: t.update(name=comp_labels.get(t.name, t.name)))
                fig_comp.update_layout(xaxis_title="", yaxis_title="Percentuale (%)", hovermode="x unified", height=350, legend_title="")
                st.plotly_chart(fig_comp, use_container_width=True)
            else:
                st.info("Nessun dato percentuale sulla composizione registrato.")

        st.divider()
        st.markdown("### 📏 Andamento Circonferenze (cm)")
        misure_cols = ['circ_collo', 'circ_petto', 'circ_vita', 'circ_fianchi', 'circ_braccio', 'circ_coscia', 'circ_polpaccio']
        misure_labels = {'circ_collo': 'Collo', 'circ_petto': 'Petto', 'circ_vita': 'Vita', 'circ_fianchi': 'Fianchi', 'circ_braccio': 'Braccio', 'circ_coscia': 'Coscia', 'circ_polpaccio': 'Polpaccio'}
        
        misure_valide = [col for col in misure_cols if df_storico[col].sum() > 0]
        
        if misure_valide:
            fig_mis = px.line(df_storico, x='data', y=misure_valide, markers=True)
            fig_mis.for_each_trace(lambda t: t.update(name=misure_labels.get(t.name, t.name)))
            fig_mis.update_layout(xaxis_title="", yaxis_title="Centimetri (cm)", hovermode="x unified", height=350, legend_title="")
            st.plotly_chart(fig_mis, use_container_width=True)
        else:
            st.info("Nessuna misurazione centimetrica registrata finora.")

        with st.expander("📅 Vedi Tabella Dati Storici Completa"):
            df_storico_view = df_storico.sort_values('data', ascending=False)
            rename_dict = {
                'data': 'Data', 'obiettivo': 'Obiettivo', 'peso': 'Peso',
                'massa_grassa': 'Massa Grassa %', 'massa_muscolare': 'Massa Musc (kg)', 'massa_ossea': 'Ossea (kg)', 'acqua_corporea': 'Acqua %',
                'tgt_cal': 'Target Kcal', 'tgt_c': 'Carb (g)', 'tgt_p': 'Prot (g)', 'tgt_f': 'Gras (g)',
                'circ_collo': 'Collo', 'circ_petto': 'Petto', 'circ_vita': 'Vita', 
                'circ_fianchi': 'Fianchi', 'circ_braccio': 'Braccio', 'circ_coscia': 'Coscia', 'circ_polpaccio': 'Polpaccio'
            }
            df_storico_view = df_storico_view.rename(columns=rename_dict)
            
            st.dataframe(
                df_storico_view.style.format({
                    "Peso": "{:.1f} kg", "Target Kcal": "{:.0f}", "Carb (g)": "{:.0f}", "Prot (g)": "{:.0f}", "Gras (g)": "{:.0f}",
                    "Massa Grassa %": "{:.1f}%", "Massa Musc (kg)": "{:.1f} kg", "Ossea (kg)": "{:.1f} kg", "Acqua %": "{:.1f}%",
                    "Collo": "{:.1f}", "Petto": "{:.1f}", "Vita": "{:.1f}", "Fianchi": "{:.1f}", "Braccio": "{:.1f}", "Coscia": "{:.1f}", "Polpaccio": "{:.1f}"
                }), 
                hide_index=True, use_container_width=True
            )
    else:
        st.info("ℹ️ Nessuno storico disponibile. Clicca su '💾 Salva Dati' nella prima scheda per creare il tuo record iniziale!")