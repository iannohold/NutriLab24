import streamlit as st
import pandas as pd
import uuid
import datetime
from components.pasto_form import mostra_interfaccia_inserimento_pasti
from components.nav import render_top_nav
from services.db import (
    get_conn, ADMIN_ID, get_diario_utente,
    get_pasti_futuri_utente, elimina_giornata_planner, clona_giornata_db,
    get_dispensa_utente, get_profilo_utente
)

# # 1. Controllo di sicurezza centralizzato
from components.auth import require_login
require_login()

# 🧭 VISUALIZZA LA NAVIGAZIONE SUPERIORE
render_top_nav("Meal Planner & Lista Spesa")

USER_ID = st.session_state.username
conn = get_conn()
oggi_date = pd.to_datetime('today').date()

st.title("📆 Meal Planner & Lista Spesa")
st.markdown("#### *Pianifica i tuoi pasti futuri e gestisci la spesa.* 🛒")
st.write("")

def render_prog(col, label, curr, tgt, unit):
    with col:
        if tgt > 0:
            perc = curr / tgt
            diff = tgt - curr
            st.progress(min(max(perc, 0.0), 1.0))
            if diff >= 0:
                st.markdown(f"{label}: **{curr:.0f}** / {tgt:.0f} {unit}")
                st.caption(f"📉 Mancano: **{diff:.0f}** {unit} ({(diff/tgt)*100:.1f}%)")
            else:
                st.markdown(f"<span style='color:#FF4B4B;'>{label}: <b>{curr:.0f}</b> / {tgt:.0f} {unit}</span>", unsafe_allow_html=True)
                st.markdown(f"<span style='color:#FF4B4B; font-size:14px;'>🚨 Superato di: <b>{abs(diff):.0f}</b> {unit} (+{(perc*100)-100:.1f}%)</span>", unsafe_allow_html=True)
        else:
            st.write(f"{label}: {curr:.0f}")

# Recupero intero diario per clonazione giorni passati
df_diario = get_diario_utente(USER_ID)
if not df_diario.empty and 'Data' in df_diario.columns:
    df_diario['Data_DT'] = pd.to_datetime(df_diario['Data'], format='%Y-%m-%d', errors='coerce').dt.date
else:
    df_diario = pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato", "Data_DT"])

# Recupero profilo tramite SQL
tgt_cal = tgt_c = tgt_p = tgt_f = 0.0
df_prof = get_profilo_utente(USER_ID)
if not df_prof.empty:
    tgt_cal = float(df_prof.iloc[0].get('TGT_Cal', 0) or 0)
    tgt_c = float(df_prof.iloc[0].get('TGT_C', 0) or 0)
    tgt_p = float(df_prof.iloc[0].get('TGT_P', 0) or 0)
    tgt_f = float(df_prof.iloc[0].get('TGT_F', 0) or 0)

# Recupero solo i pasti futuri o odierni pianificati
df_futuro = get_pasti_futuri_utente(USER_ID, str(oggi_date))

tab_nuovo, tab_clona, tab_spesa = st.tabs(["📝 Pianifica Nuovo", "👯 Clona Giornata", "🛒 Lista della Spesa"])

with tab_nuovo:
    c1, c2 = st.columns(2)
    with c1:
        data_sel_planner = st.date_input("Data da pianificare", oggi_date, min_value=oggi_date, key="date_planner")
    
    mostra_interfaccia_inserimento_pasti(data_sel_planner, is_planner=True)
    
    st.divider()
    st.markdown("### 🔍 Riepilogo Giornate Future o Pianificate")
    if not df_futuro.empty:
        giorni_futuri = sorted(df_futuro['Data'].unique())
        for d in giorni_futuri:
            df_giorno = df_futuro[df_futuro['Data'] == d]
            t_cal_storico = df_giorno['Calorie'].sum()
            d_obj = pd.to_datetime(d)
            nome_giorno = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][d_obj.weekday()]
            
            with st.expander(f"📌 {nome_giorno} {d_obj.strftime('%d/%m/%Y')} - Pianificato: {t_cal_storico:.0f} kcal", expanded=False):
                if tgt_cal > 0:
                    cp1, cp2, cp3, cp4 = st.columns(4)
                    render_prog(cp1, "🔥 Cal", t_cal_storico, tgt_cal, "kcal")
                    render_prog(cp2, "🍞 Carb", df_giorno['Carboidrati'].sum(), tgt_c, "g")
                    render_prog(cp3, "🥩 Prot", df_giorno['Proteine'].sum(), tgt_p, "g")
                    render_prog(cp4, "🥑 Gras", df_giorno['Grassi'].sum(), tgt_f, "g")
                else:
                    st.markdown(f"**Macros Previsti:** Carboidrati: {df_giorno['Carboidrati'].sum():.1f}g | Proteine: {df_giorno['Proteine'].sum():.1f}g | Grassi: {df_giorno['Grassi'].sum():.1f}g")
                
                st.write("")
                for pasto in ["Colazione", "Spuntino", "Pranzo", "Merenda", "Cena"]:
                    df_pasto_s = df_giorno[df_giorno['Pasto'] == pasto]
                    if not df_pasto_s.empty:
                        st.markdown(f"**🍽️ {pasto.upper()}** (Tot: {df_pasto_s['Calorie'].sum():.0f} kcal)")
                        for _, row in df_pasto_s.iterrows():
                            st.write(f"- **{row['Quantita']:.1f} {row['Unita']}** di {row['Elemento']} *(Cal: {row['Calorie']:.0f} | C: {row['Carboidrati']:.1f} | P: {row['Proteine']:.1f} | G: {row['Grassi']:.1f})*")
                st.write("")
                
                col_go, col_del_day = st.columns([1, 1])
                if col_go.button(f"✏️ Vai al Diario per modificare", key=f"btn_go_{d}"):
                    st.info("💡 Vai nella sezione 'Diario Alimentare' per modificare o confermare i singoli elementi di questa data!")
                
                if col_del_day.button(f"🗑️ Svuota intera giornata", key=f"btn_del_day_{d}"):
                    with st.spinner("Cancellazione..."):
                        elimina_giornata_planner(USER_ID, str(d))
                        st.rerun()
    else:
        st.success("Non hai ancora pianificato nessun pasto per i prossimi giorni.")

with tab_clona:
    st.markdown("#### 👯 Clona un giorno perfetto")
    c_copia1, c_copia2, c_copia_btn = st.columns([1.5, 1.5, 1])
    data_origine = c_copia1.date_input("Da quale data COPIARE?", oggi_date, key="date_orig")
    data_destinazione = c_copia2.date_input("In quale data INCOLLARE?", oggi_date + pd.Timedelta(days=1), min_value=oggi_date, key="date_dest")
    
    with c_copia_btn:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        if st.button("🪄 Clona Giornata", use_container_width=True, type="primary"):
            if str(data_origine) == str(data_destinazione):
                st.warning("Scegli una data diversa.")
            else:
                df_orig = df_diario[df_diario['Data'] == str(data_origine)]
                if df_orig.empty:
                    st.error("Nessun pasto trovato nella data di origine.")
                else:
                    with st.spinner("Clonazione in corso..."):
                        nuovi_pasti = []
                        for _, row in df_orig.iterrows():
                            nuovi_pasti.append({
                                "id": uuid.uuid4().hex,
                                "data": str(data_destinazione),
                                "pasto": str(row['Pasto']),
                                "elemento": str(row['Elemento']),
                                "quantita": float(row['Quantita']),
                                "unita": str(row['Unita']),
                                "calorie": float(row['Calorie']),
                                "carboidrati": float(row['Carboidrati']),
                                "proteine": float(row['Proteine']),
                                "grassi": float(row['Grassi']),
                                "saturi": float(row.get('Saturi', 0) or 0),
                                "fibre": float(row.get('Fibre', 0) or 0),
                                "user_id": USER_ID,
                                "tgt_cal": tgt_cal,
                                "tgt_c": tgt_c,
                                "tgt_p": tgt_p,
                                "tgt_f": tgt_f,
                                "stato": "Pianificato"
                            })
                        clona_giornata_db(nuovi_pasti)
                        st.success("Giornata clonata con successo!")
                        st.rerun()

with tab_spesa:
    st.markdown("#### 🛒 Lista della Spesa Intelligente")
    if not df_futuro.empty:
        df_spesa = df_futuro.groupby(['Elemento', 'Unita'])['Quantita'].sum().reset_index()
        df_spesa['Ingrediente'] = df_spesa['Elemento'].apply(lambda x: str(x).replace("🛒 ", "").replace("🍽️ ", "").replace("⏱️ ", "").replace("📦 ", ""))
        df_spesa = df_spesa.groupby(['Ingrediente', 'Unita'])['Quantita'].sum().reset_index()
        
        df_disp_user = get_dispensa_utente(USER_ID)
        dispensa_dict = dict(zip(df_disp_user['Nome'].str.lower(), df_disp_user['Quantita'])) if not df_disp_user.empty else {}
        
        df_editor = df_spesa[['Ingrediente', 'Quantita', 'Unita']].rename(columns={'Quantita': 'Fabbisogno'})
        df_editor['In Dispensa'] = df_editor['Ingrediente'].apply(lambda x: dispensa_dict.get(x.lower().strip(), 0.0))
        
        edited_df = st.data_editor(
            df_editor,
            column_config={
                "Ingrediente": st.column_config.TextColumn("Ingrediente", disabled=True),
                "Fabbisogno": st.column_config.NumberColumn("Richiesto", disabled=True, format="%.1f"),
                "Unita": st.column_config.TextColumn("Unità", disabled=True),
                "In Dispensa": st.column_config.NumberColumn("In Dispensa ✏️", min_value=0.0, format="%.1f", step=10.0)
            },
            hide_index=True, use_container_width=True, key="editor_spesa_planner"
        )
        
        spesa_testo = ""
        for _, r in edited_df.sort_values(by='Ingrediente').iterrows():
            da_comprare = max(float(r['Fabbisogno']) - float(r['In Dispensa']), 0.0)
            if da_comprare > 0:
                spesa_testo += f"- [ ] **{r['Ingrediente']}**: {da_comprare:.1f} {r['Unita']}\n"
        
        if spesa_testo: st.markdown(spesa_testo)
        else: st.success("🎉 Hai già tutto in dispensa!")
    else:
        st.warning("Pianifica almeno un pasto futuro o odierno per generare la spesa.")