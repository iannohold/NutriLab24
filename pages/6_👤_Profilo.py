import streamlit as st
import pandas as pd
from services.db import get_profilo_utente, salva_profilo_utente
from components.nav import render_top_nav

# # 1. Controllo di sicurezza centralizzato
from components.auth import require_login
require_login()

# 🧭 VISUALIZZA LA NAVIGAZIONE SUPERIORE
render_top_nav("Profilo")

USER_ID = st.session_state.username

st.title("👤 Profilo e Obiettivi Nutrizionali")
st.markdown("#### *Calcola il tuo fabbisogno e genera i tuoi target in automatico.* 🎯")
st.write("")

# Lettura profilo tramite SQL
df_prof = get_profilo_utente(USER_ID)

def_peso = float(df_prof.iloc[0]['Peso']) if not df_prof.empty and pd.notna(df_prof.iloc[0]['Peso']) else 75.0
def_alt = int(df_prof.iloc[0]['Altezza']) if not df_prof.empty and pd.notna(df_prof.iloc[0]['Altezza']) else 175
def_eta = int(df_prof.iloc[0]['Eta']) if not df_prof.empty and pd.notna(df_prof.iloc[0]['Eta']) else 52
def_sesso = str(df_prof.iloc[0]['Sesso']) if not df_prof.empty and pd.notna(df_prof.iloc[0]['Sesso']) else "Uomo"
def_att = str(df_prof.iloc[0]['Attivita']) if not df_prof.empty and pd.notna(df_prof.iloc[0]['Attivita']) else "Moderatamente Attivo (1.55) - Sport moderato 3-5 volte a sett"

st.markdown("### 1️⃣ I tuoi Dati Personali")
c1, c2, c3, c4 = st.columns(4)
peso = c1.number_input("Peso attuale (kg)", min_value=30.0, max_value=200.0, value=def_peso, step=0.1)
alt = c2.number_input("Altezza (cm)", min_value=100, max_value=250, value=def_alt, step=1)
eta = c3.number_input("Età", min_value=10, max_value=100, value=def_eta, step=1)
sesso = c4.selectbox("Sesso", ["Uomo", "Donna"], index=0 if def_sesso=="Uomo" else 1)

attivita_list = {
    "Sedentario (1.2) - Lavoro da scrivania, no sport": 1.2,
    "Leggermente Attivo (1.375) - Sport leggero 1-3 volte a sett": 1.375,
    "Moderatamente Attivo (1.55) - Sport moderato 3-5 volte a sett": 1.55,
    "Molto Attivo (1.725) - Sport intenso 6-7 giorni": 1.725,
    "Extra Attivo (1.9) - Atleta agonista o lavoro fisico pesante": 1.9
}
idx_att = list(attivita_list.keys()).index(def_att) if def_att in attivita_list else 2
att = st.selectbox("Livello di Attività Media", list(attivita_list.keys()), index=idx_att)

s = 5 if sesso == "Uomo" else -161
bmr = (10 * peso) + (6.25 * alt) - (5 * eta) + s
tdee = bmr * attivita_list[att]

st.info(f"🧬 **Metabolismo Basale (BMR):** {bmr:.0f} kcal  |  🔥 **Dispendio Energetico Totale (TDEE):** {tdee:.0f} kcal")

st.divider()

st.markdown("### 2️⃣ Generazione Automatica dei Macros")
st.write("Scegli il tuo obiettivo e imposta i fattori nutrizionali. I Carboidrati verranno calcolati automaticamente per coprire le calorie rimanenti.")

col_ob1, col_ob2, col_ob3 = st.columns(3)

obiettivo = col_ob1.selectbox(
    "Qual è il tuo obiettivo?", 
    ["Mantenimento (TDEE esatto)", "Dimagrimento Lieve (-300 kcal)", "Dimagrimento Marcato (-500 kcal)", "Costruzione Muscolare (+300 kcal)"]
)

if "Mantenimento" in obiettivo: tgt_cal_auto = tdee
elif "Lieve" in obiettivo: tgt_cal_auto = tdee - 300
elif "Marcato" in obiettivo: tgt_cal_auto = tdee - 500
else: tgt_cal_auto = tdee + 300

molt_p = col_ob2.slider("Fattore Proteine (g per kg di peso)", min_value=1.0, max_value=3.0, value=2.0, step=0.1, help="Per sportivi che si allenano coi pesi si consiglia 1.6 - 2.2 g/kg.")
molt_f = col_ob3.slider("Fattore Grassi (g per kg di peso)", min_value=0.5, max_value=1.5, value=0.8, step=0.1, help="Per salute ormonale media consigliata 0.8 - 1.0 g/kg.")

calc_p = peso * molt_p
calc_f = peso * molt_f
cal_occupate = (calc_p * 4) + (calc_f * 9)
calc_c = (tgt_cal_auto - cal_occupate) / 4 if tgt_cal_auto > cal_occupate else 0.0

perc_p = ((calc_p * 4) / tgt_cal_auto) * 100 if tgt_cal_auto > 0 else 0
perc_f = ((calc_f * 9) / tgt_cal_auto) * 100 if tgt_cal_auto > 0 else 0
perc_c = ((calc_c * 4) / tgt_cal_auto) * 100 if tgt_cal_auto > 0 else 0

st.markdown("#### 📊 Ripartizione Macros")
st.success(f"🍞 **Carboidrati:** {perc_c:.0f}%  |  🥩 **Proteine:** {perc_p:.0f}%  |  🥑 **Grassi:** {perc_f:.0f}%")

st.markdown("#### 🎯 I tuoi Target Finali da Salvare")
st.write("Questi sono i valori generati. Se vuoi, puoi arrotondarli o ritoccarli a mano prima di salvare.")

tc1, tc2, tc3, tc4 = st.columns(4)
t_cal = tc1.number_input("Target Calorie", value=float(tgt_cal_auto), step=50.0)
t_c = tc2.number_input("Target Carboidrati (g)", value=float(calc_c), step=5.0)
t_p = tc3.number_input("Target Proteine (g)", value=float(calc_p), step=5.0)
t_f = tc4.number_input("Target Grassi (g)", value=float(calc_f), step=5.0)

cal_check = (t_c * 4) + (t_p * 4) + (t_f * 9)
if abs(cal_check - t_cal) > 50:
    st.warning(f"⚠️ Nota: I macro generano circa {cal_check:.0f} kcal, ma il target in alto è {t_cal:.0f}. Non combaciano perfettamente.")
    
st.write("")
if st.button("💾 Conferma e Salva Obiettivi", type="primary", use_container_width=True):
    with st.spinner("Salvataggio in Cloud..."):
        # Scrittura profilo tramite SQL
        success = salva_profilo_utente(USER_ID, peso, alt, eta, sesso, att, t_cal, t_c, t_p, t_f)
        if success:
            st.success("✅ Profilo e Obiettivi aggiornati! Vai nel Diario Alimentare per vedere le Barre di Progresso colorate in azione.")
        else:
            st.error("Errore di salvataggio in Cloud. Riprova più tardi.")