import streamlit as st
import pandas as pd
import datetime
import plotly.express as px

from components.pasto_form import mostra_interfaccia_inserimento_pasti
from components.nav import render_top_nav
from services.db import (
    get_diario_utente, elimina_voce_diario, aggiorna_voce_diario, 
    get_profilo_utente, ADMIN_ID
)

st.set_page_config(page_title="NutriLab24", layout="wide")

# ==========================================
# 🔐 CONTROLLO SICUREZZA E NAVIGAZIONE
# ==========================================
from components.auth import require_login
require_login()

render_top_nav("Diario Alimentare")

USER_ID = st.session_state.username
oggi_date = pd.to_datetime('today').date()

st.title("📅 Diario Alimentare")
st.markdown("#### *Registrazione e gestione flessibile dei pasti.* 🍽️")

# ==========================================
# 📊 UI HELPERS
# ==========================================
def render_stacked_prog(col, label, consumato, pianificato, tgt, unit):
    totale = consumato + pianificato
    with col:
        if tgt > 0:
            perc_cons = min((consumato / tgt) * 100, 100.0)
            perc_pian = min((pianificato / tgt) * 100, 100.0 - perc_cons)
            diff_cons = tgt - consumato
            diff_tot = tgt - totale
            
            if pianificato > 0:
                st.markdown(f"{label}: **{consumato:.0f}** <span style='color:gray;'>({totale:.0f})</span> / {tgt:.0f} {unit}", unsafe_allow_html=True)
            else:
                st.markdown(f"{label}: **{consumato:.0f}** / {tgt:.0f} {unit}", unsafe_allow_html=True)
            
            st.markdown(f"""
            <div style="width: 100%; background-color: #f0f2f6; border-radius: 5px; height: 10px; display: flex; overflow: hidden; margin-top: 5px; margin-bottom: 5px;">
                <div style="width: {perc_cons}%; background-color: #0068c9;"></div>
                <div style="width: {perc_pian}%; background-color: #a8a8a8;"></div>
            </div>
            """, unsafe_allow_html=True)
            
            if diff_cons >= 0:
                if pianificato > 0:
                    if diff_tot >= 0:
                        st.markdown(f"<div style='font-size:14px; color:#555;'>📉 Mancano: <b>{diff_cons:.0f}</b> <span style='color:#a8a8a8;'>({diff_tot:.0f})</span> {unit}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='font-size:14px; color:#555;'>📉 Mancano: <b>{diff_cons:.0f}</b> <span style='color:#FF4B4B;'>(🚨 supererai di {abs(diff_tot):.0f})</span> {unit}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='font-size:14px; color:#555;'>📉 Mancano: <b>{diff_cons:.0f}</b> {unit}</div>", unsafe_allow_html=True)
            else:
                if pianificato > 0:
                    st.markdown(f"<div style='font-size:14px; color:#FF4B4B;'>🚨 Superato di: <b>{abs(diff_cons):.0f}</b> <span style='color:#a8a8a8;'>({abs(diff_tot):.0f} col piano)</span> {unit}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='font-size:14px; color:#FF4B4B;'>🚨 Superato di: <b>{abs(diff_cons):.0f}</b> {unit}</div>", unsafe_allow_html=True)
        else:
            if pianificato > 0:
                st.markdown(f"{label}: **{consumato:.0f}** <span style='color:gray;'>({totale:.0f})</span> {unit}", unsafe_allow_html=True)
            else:
                st.markdown(f"{label}: **{consumato:.0f}** {unit}", unsafe_allow_html=True)

def get_status_emoji(val, tgt):
    if pd.isna(tgt) or tgt <= 0: return ""
    if val < tgt * 0.90: return "🟨"
    elif val > tgt * 1.05: return "🚨"
    else: return "✅"

# ==========================================
# 📥 RECUPERO DATI E OBIETTIVI TRAMITE SQL
# ==========================================
df_diario = get_diario_utente(USER_ID)
if not df_diario.empty and 'Data' in df_diario.columns:
    df_diario['Data'] = pd.to_datetime(df_diario['Data'], errors='coerce').dt.strftime('%Y-%m-%d')
    df_diario['Data_DT'] = pd.to_datetime(df_diario['Data'], format='%Y-%m-%d', errors='coerce').dt.date
else:
    df_diario['Data_DT'] = pd.Series(dtype='object')

tgt_cal = tgt_c = tgt_p = tgt_f = 0.0
df_prof = get_profilo_utente(USER_ID)
if not df_prof.empty:
    tgt_cal = float(df_prof.iloc[0].get('tgt_cal', 0) or 0)
    tgt_c = float(df_prof.iloc[0].get('tgt_c', 0) or 0)
    tgt_p = float(df_prof.iloc[0].get('tgt_p', 0) or 0)
    tgt_f = float(df_prof.iloc[0].get('tgt_f', 0) or 0)

# ==========================================
# 🗂️ TABS DI NAVIGAZIONE
# ==========================================
tab_inserisci, tab_storico, tab_report = st.tabs(["📝 Inserisci / Gestisci Oggi", "🗓️ Storico Giornaliero", "📈 Statistiche e Report"])

with tab_inserisci:
    data_sel_diario = st.date_input("Data del pasto", oggi_date, max_value=oggi_date)
    mostra_interfaccia_inserimento_pasti(data_sel_diario, is_planner=False)
    
    st.divider()
    st.markdown(f"#### 🔵 Riepilogo del {data_sel_diario.strftime('%d/%m/%Y')}")
    df_giorno_sel = df_diario[df_diario['Data'] == str(data_sel_diario)]
    
    if not df_giorno_sel.empty:
        df_consumati = df_giorno_sel[df_giorno_sel['Stato'] == 'Consumato']
        df_pianificati = df_giorno_sel[df_giorno_sel['Stato'] == 'Pianificato']
        
        t_cal = df_consumati['Calorie'].sum(); t_c = df_consumati['Carboidrati'].sum()
        t_p = df_consumati['Proteine'].sum(); t_f = df_consumati['Grassi'].sum()
        t_sale = df_consumati['Sale'].sum() if 'Sale' in df_consumati.columns else 0.0

        p_cal = df_pianificati['Calorie'].sum(); p_c = df_pianificati['Carboidrati'].sum()
        p_p = df_pianificati['Proteine'].sum(); p_f = df_pianificati['Grassi'].sum()
        p_sale = df_pianificati['Sale'].sum() if 'Sale' in df_pianificati.columns else 0.0

        if tgt_cal > 0:
            cp1, cp2, cp3, cp4, cp5 = st.columns(5)
            render_stacked_prog(cp1, "🔥 Cal", t_cal, p_cal, tgt_cal, "kcal")
            render_stacked_prog(cp2, "🍞 Carb", t_c, p_c, tgt_c, "g")
            render_stacked_prog(cp3, "🥩 Prot", t_p, p_p, tgt_p, "g")
            render_stacked_prog(cp4, "🥑 Gras", t_f, p_f, tgt_f, "g")
            cp5.metric("🧂 Sale", f"{t_sale:.2f} ({t_sale+p_sale:.2f}) g")
            st.write("")
        else:
            cm1, cm2, cm3, cm4, cm5 = st.columns(5)
            cm1.metric("🔥 Cal", f"{t_cal:.0f} ({t_cal+p_cal:.0f}) kcal")
            cm2.metric("🍞 Carb", f"{t_c:.1f} ({t_c+p_c:.1f}) g")
            cm3.metric("🥩 Prot", f"{t_p:.1f} ({t_p+p_p:.1f}) g")
            cm4.metric("🥑 Gras", f"{t_f:.1f} ({t_f+p_f:.1f}) g")
            cm5.metric("🧂 Sale", f"{t_sale:.2f} ({t_sale+p_sale:.2f}) g")
        
        st.write("")
        for pasto in ["Colazione", "Spuntino", "Pranzo", "Merenda", "Cena"]:
            df_pasto = df_giorno_sel[df_giorno_sel['Pasto'] == pasto]
            if not df_pasto.empty:
                t_cal_p = df_pasto['Calorie'].sum()
                t_c_p = df_pasto['Carboidrati'].sum()
                t_p_p = df_pasto['Proteine'].sum()
                t_f_p = df_pasto['Grassi'].sum()
                t_sale_p = df_pasto['Sale'].sum() if 'Sale' in df_pasto.columns else 0.0
                
                has_pianificati = any(str(row.get('Stato', 'Consumato')) == 'Pianificato' for _, row in df_pasto.iterrows())
                alert_icon = "⏳ " if has_pianificati else ""
                
                with st.expander(f"{alert_icon}🍽️ {pasto.upper()} (Cal: {t_cal_p:.0f} kcal | C: {t_c_p:.1f}g | P: {t_p_p:.1f}g | G: {t_f_p:.1f}g | Sale: {t_sale_p:.2f}g)", expanded=has_pianificati):
                    for _, row in df_pasto.iterrows():
                        c_txt, c_mod, c_del = st.columns([0.70, 0.15, 0.15])
                        is_pianificato = str(row.get('Stato', 'Consumato')) == 'Pianificato'
                        
                        if is_pianificato:
                            c_txt.markdown(f"<span style='color: gray;'>⏳ <b>[DA CONFERMARE]</b> {row['Quantita']:.1f} {row['Unita']} di {row['Elemento']} <i>(Cal: {row['Calorie']:.0f} | P: {row['Proteine']:.1f}g)</i></span>", unsafe_allow_html=True)
                            with st.container():
                                cc_spazio, cc_qta, cc_btn = st.columns([0.05, 0.45, 0.50])
                                # Etichetta chiara e inequivocabile per la conferma
                                nuova_qta = cc_qta.number_input(f"Q.tà nel piatto ({row['Unita']})", value=float(row['Quantita']), step=1.0, key=f"qta_conf_{row['ID']}")
                                cc_btn.write("")
                                if cc_btn.button("✅ Conferma Pasto", key=f"btn_conf_{row['ID']}", type="primary"):
                                    with st.spinner("Salvataggio..."):
                                        ratio = nuova_qta / float(row['Quantita']) if float(row['Quantita']) > 0 else 0
                                        new_cal = float(row['Calorie']) * ratio
                                        new_c = float(row['Carboidrati']) * ratio
                                        new_p = float(row['Proteine']) * ratio
                                        new_f = float(row['Grassi']) * ratio
                                        new_sal = float(row.get('Sale', 0.0)) * ratio
                                        
                                        aggiorna_voce_diario(row['ID'], nuova_qta, new_cal, new_c, new_p, new_f, new_sal, 'Consumato', row['Elemento'])
                                        st.rerun()
                        else:
                            c_txt.write(f"- **{row['Quantita']:.1f} {row['Unita']}** (nel piatto) di {row['Elemento']} *(Cal: {row['Calorie']:.0f} | C: {row['Carboidrati']:.1f} | P: {row['Proteine']:.1f} | G: {row['Grassi']:.1f} | Sale: {row.get('Sale', 0.0):.2f}g)*")

                        if c_mod.button("✏️ Modifica", key=f"mod_{row['ID']}"):
                            st.session_state[f"editing_{row['ID']}"] = True

                        if c_del.button("❌ Elimina", key=f"del_{row['ID']}"):
                            elimina_voce_diario(row['ID'])
                            st.rerun()

                        if st.session_state.get(f"editing_{row['ID']}", False):
                            with st.form(key=f"form_edit_{row['ID']}"):
                                st.write(f"Modifica la quantità nel piatto per: **{row['Elemento']}**")
                                old_qty = float(row['Quantita'])
                                
                                new_qty = st.number_input(f"Nuova Q.tà ({row['Unita']})", value=old_qty, min_value=0.0, step=1.0 if row['Unita']=='pz' else 5.0)
                                
                                if st.form_submit_button("💾 Salva Nuova Quantità"):
                                    ratio = new_qty / old_qty if old_qty > 0 else 1.0
                                    new_cal = float(row['Calorie']) * ratio
                                    new_c = float(row['Carboidrati']) * ratio
                                    new_p = float(row['Proteine']) * ratio
                                    new_f = float(row['Grassi']) * ratio
                                    new_sal = float(row.get('Sale', 0.0)) * ratio
                                    
                                    aggiorna_voce_diario(
                                        id_voce=row['ID'], 
                                        nuova_qta=new_qty, 
                                        cal=new_cal, 
                                        c=new_c, 
                                        p=new_p, 
                                        f=new_f,
                                        sal=new_sal, 
                                        stato=row['Stato'], 
                                        elemento=row['Elemento']
                                    )
                                    st.session_state[f"editing_{row['ID']}"] = False
                                    st.rerun()
    else:
        st.info("Nessun pasto registrato per oggi.")

with tab_storico:
    st.markdown("### Storico Giornate Passate")
    altri_giorni = sorted(df_diario['Data'].dropna().unique(), reverse=True)
    for d in altri_giorni:
        if d != str(oggi_date):
            df_g = df_diario[df_diario['Data'] == d]
            with st.expander(f"📅 {d} - {df_g['Calorie'].sum():.0f} kcal"):
                for _, row in df_g.iterrows():
                    col1, col2 = st.columns([0.85, 0.15])
                    col1.write(f"- **{row['Quantita']:.1f} {row['Unita']}** (nel piatto) di {row['Elemento']} *(Cal: {row['Calorie']:.0f} kcal)*")
                    if col2.button("✏️ Mod", key=f"mod_stor_{row['ID']}"):
                        st.session_state[f"editing_{row['ID']}"] = True
                    
                    if st.session_state.get(f"editing_{row['ID']}", False):
                        with st.form(key=f"form_edit_stor_{row['ID']}"):
                            st.write(f"Modifica: {row['Elemento']}")
                            old_qty = float(row['Quantita'])
                            new_qty = st.number_input(f"Q.tà nel piatto ({row['Unita']})", value=old_qty, min_value=0.0)
                            
                            if st.form_submit_button("Salva"):
                                ratio = new_qty / old_qty if old_qty > 0 else 1.0
                                aggiorna_voce_diario(
                                    id_voce=row['ID'],
                                    nuova_qta=new_qty,
                                    cal=float(row['Calorie']) * ratio,
                                    c=float(row['Carboidrati']) * ratio,
                                    p=float(row['Proteine']) * ratio,
                                    f=float(row['Grassi']) * ratio,
                                    sal=float(row.get('Sale', 0.0)) * ratio,
                                    stato=str(row.get('Stato', 'Consumato')),
                                    elemento=row['Elemento']
                                )
                                st.session_state[f"editing_{row['ID']}"] = False
                                st.rerun()

with tab_report:
    st.markdown("### 📈 Statistiche e Report")
    c_date1, c_date2 = st.columns([1, 2])
    rep_mode = c_date1.radio("Periodo di analisi:", ["Oggi", "Ieri", "Ultimi 7 gg", "Ultimi 30 gg", "Personalizzato"], index=0, horizontal=True)
    
    if rep_mode == "Oggi": start_date = end_date = oggi_date
    elif rep_mode == "Ieri": start_date = end_date = oggi_date - datetime.timedelta(days=1)
    elif rep_mode == "Ultimi 7 gg": start_date = oggi_date - datetime.timedelta(days=7); end_date = oggi_date
    elif rep_mode == "Ultimi 30 gg": start_date = oggi_date - datetime.timedelta(days=30); end_date = oggi_date
    else:
        sel_dates = c_date2.date_input("Seleziona intervallo:", [oggi_date, oggi_date])
        if len(sel_dates) == 2: start_date, end_date = sel_dates
        else: start_date, end_date = oggi_date, oggi_date

    mask_date = (df_diario['Data_DT'] >= start_date) & (df_diario['Data_DT'] <= end_date)
    df_rep_base = df_diario[mask_date].copy()
    
    if not df_rep_base.empty:
        st.divider()
        st.markdown("#### 🍽️ Analisi Dinamica per Pasti")
        pasti_disponibili = ["Colazione", "Spuntino", "Pranzo", "Merenda", "Cena", "Spuntino Mattina"]
        pasti_presenti = [p for p in pasti_disponibili if p in df_rep_base['Pasto'].unique() or (p=="Spuntino" and "Spuntino Mattina" in df_rep_base['Pasto'].unique())]
        if not pasti_presenti: pasti_presenti = df_rep_base['Pasto'].unique().tolist()
        
        pasti_selezionati = st.multiselect("Quali pasti vuoi analizzare?", options=pasti_presenti, default=pasti_presenti)
        pasti_filter = list(pasti_selezionati)
        if "Spuntino" in pasti_filter and "Spuntino Mattina" not in pasti_filter: pasti_filter.append("Spuntino Mattina")
            
        df_rep = df_rep_base[df_rep_base['Pasto'].isin(pasti_filter)]
        
        if not df_rep.empty:
            giorni_totali = df_rep['Data'].nunique()
            st.write(f"📊 **Medie calcolate dal {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')} su {giorni_totali} giorni attivi:**")
            
            df_rep_cons = df_rep[df_rep['Stato'] == 'Consumato']
            df_rep_pian = df_rep[df_rep['Stato'] == 'Pianificato']
            
            m_cal_c = df_rep_cons['Calorie'].sum() / giorni_totali if giorni_totali > 0 else 0
            m_c_c = df_rep_cons['Carboidrati'].sum() / giorni_totali if giorni_totali > 0 else 0
            m_p_c = df_rep_cons['Proteine'].sum() / giorni_totali if giorni_totali > 0 else 0
            m_f_c = df_rep_cons['Grassi'].sum() / giorni_totali if giorni_totali > 0 else 0
            m_sale_c = df_rep_cons['Sale'].sum() / giorni_totali if ('Sale' in df_rep_cons.columns and giorni_totali > 0) else 0
            
            m_cal_p = df_rep_pian['Calorie'].sum() / giorni_totali if giorni_totali > 0 else 0
            m_c_p = df_rep_pian['Carboidrati'].sum() / giorni_totali if giorni_totali > 0 else 0
            m_p_p = df_rep_pian['Proteine'].sum() / giorni_totali if giorni_totali > 0 else 0
            m_f_p = df_rep_pian['Grassi'].sum() / giorni_totali if giorni_totali > 0 else 0
            m_sale_p = df_rep_pian['Sale'].sum() / giorni_totali if ('Sale' in df_rep_pian.columns and giorni_totali > 0) else 0
            
            if tgt_cal > 0:
                st.markdown("##### 🎯 Media Giornaliera rispetto ai tuoi Obiettivi:")
                c_r1, c_r2, c_r3, c_r4, c_r5 = st.columns(5)
                render_stacked_prog(c_r1, "🔥 Cal Medie", m_cal_c, m_cal_p, tgt_cal, "kcal")
                render_stacked_prog(c_r2, "🍞 Carb Medi", m_c_c, m_c_p, tgt_c, "g")
                render_stacked_prog(c_r3, "🥩 Prot Medie", m_p_c, m_p_p, tgt_p, "g")
                render_stacked_prog(c_r4, "🥑 Gras Medi", m_f_c, m_f_p, tgt_f, "g")
                c_r5.metric("🧂 Sale Medio", f"{m_sale_c:.2f} g")
                st.write("")
            else:
                c_r1, c_r2, c_r3, c_r4, c_r5 = st.columns(5)
                c_r1.metric("🔥 Calorie Medie", f"{m_cal_c:.0f} kcal", f"Pianificate: +{m_cal_p:.0f}")
                c_r2.metric("🍞 Carboidrati Medi", f"{m_c_c:.1f} g", f"Pianificati: +{m_c_p:.1f}")
                c_r3.metric("🥩 Proteine Medie", f"{m_p_c:.1f} g", f"Pianificate: +{m_p_p:.1f}")
                c_r4.metric("🥑 Grassi Medi", f"{m_f_c:.1f} g", f"Pianificati: +{m_f_p:.1f}")
                c_r5.metric("🧂 Sale", f"{m_sale_c:.2f} g")
            
            st.write("")
            c_chart1, c_chart2 = st.columns([1, 1.8])
            with c_chart1:
                st.markdown("**Ripartizione Macros (Consumati)**")
                tot_c_real = df_rep_cons['Carboidrati'].sum()
                tot_p_real = df_rep_cons['Proteine'].sum()
                tot_f_real = df_rep_cons['Grassi'].sum()
                if tot_c_real + tot_p_real + tot_f_real > 0:
                    fig_pie = px.pie(names=['Carboidrati', 'Proteine', 'Grassi'], values=[tot_c_real, tot_p_real, tot_f_real], color_discrete_sequence=['#0068c9', '#87CEFA', '#98FB98'], hole=0.4)
                    fig_pie.update_layout(margin=dict(t=20, b=20, l=0, r=0), height=300, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
                else: st.info("Dati consumati insufficienti per il grafico a torta.")
                    
            with c_chart2:
                st.markdown("**Andamento Giornaliero (Totale)**")
                df_trend = df_rep.groupby('Data')[['Carboidrati', 'Proteine', 'Grassi']].sum().reset_index()
                df_trend['Data'] = pd.to_datetime(df_trend['Data'])
                df_trend = df_trend.sort_values('Data')
                
                fig_line = px.line(df_trend, x='Data', y=['Carboidrati', 'Proteine', 'Grassi'], color_discrete_map={'Carboidrati':'#FFA07A', 'Proteine':'#87CEFA', 'Grassi':'#98FB98'}, markers=True)
                fig_line.update_layout(xaxis_title="", yaxis_title="Grammi (g)", legend_title="", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(t=20, b=20, l=0, r=0), height=300, hovermode="x unified")
                st.plotly_chart(fig_line, use_container_width=True)
                
            with st.expander("📅 Vedi Tabella Sintetica Giornaliera"):
                cols_to_group = ['Calorie', 'Carboidrati', 'Proteine', 'Grassi']
                if 'Sale' in df_rep.columns: cols_to_group.append('Sale')
                df_day = df_rep.groupby(['Data', 'Stato'])[cols_to_group].sum().reset_index()
                df_day = df_day.sort_values(['Data', 'Stato'], ascending=[False, True])
                
                format_dict = {"Calorie": "{:.0f}", "Carboidrati": "{:.1f}", "Proteine": "{:.1f}", "Grassi": "{:.1f}"}
                if 'Sale' in df_day.columns: format_dict["Sale"] = "{:.2f}"
                st.dataframe(df_day.style.format(format_dict), use_container_width=True, hide_index=True)
        else: st.warning("Nessun dato per i pasti selezionati in questo periodo.")
    else: st.info("Nessun dato registrato nell'intervallo selezionato.")