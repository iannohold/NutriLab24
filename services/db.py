import streamlit as st
import requests
import pandas as pd
import re
import uuid
import json
import os
from sqlalchemy import text

# ==========================================
# ⚙️ COSTANTI GLOBALI
# ==========================================
ADMIN_ID = "vins"
SPREADSHEET_URL = "SUPABASE_MIGRATED"

RUOLI_LIST = ["Impasto", "Farcitura", "Topping", "Salsa", "Decorazione", "Altro"]
CATEGORIE_LIST = ["☕ Colazione", "🍰 Dessert", "🍝 Primo", "🥩 Secondo", "🍲 Piatto unico", "🥪 Spuntino", "💪 Post work-out", "🔹 Altro"]

FALLBACK_DB = {
    "Farina di avena": (370.0, 13.5, 68.0, 7.0, 10.0, 1.2, 0.0, 0.0, "g"),
    "Latte (Senza lattosio)": (47.0, 3.4, 5.0, 1.5, 0.0, 1.0, 0.0, 0.0, "ml"),
    "Uova intere": (143.0, 12.5, 0.6, 9.5, 0.0, 3.1, 0.0, 55.0, "pz")
}

# ==========================================
# 🔌 CONNESSIONE E LETTURA DATABASE (SUPABASE)
# ==========================================

def get_conn():
    # Ottimizzazione del pool per Supabase
    return st.connection(
        "supabase", 
        type="sql", 
        kwargs={"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True}
    )

@st.cache_data(ttl=60)  
def get_user_macros_db(user_id):
    conn = get_conn()
    try:
        df = conn.query("SELECT * FROM macros", ttl=0)
        if df.empty or 'nome' not in [c.lower() for c in df.columns]:
            return FALLBACK_DB
            
        df.columns = [c.lower() for c in df.columns]
        df = df.dropna(subset=['nome'])
        
        if 'var_cottura' not in df.columns: df['var_cottura'] = 0.0
        if 'peso_medio_pz' not in df.columns: df['peso_medio_pz'] = 0.0
        if 'unita_default' not in df.columns: df['unita_default'] = 'g'
        if 'user_id' not in df.columns: df['user_id'] = ADMIN_ID 
        
        df_visibile = df[(df['user_id'] == ADMIN_ID) | (df['user_id'] == user_id)]
        df_visibile = df_visibile.sort_values('user_id').drop_duplicates(subset=['nome'], keep='last')
        
        mdb = {}
        for _, row in df_visibile.iterrows():
            nome = str(row['nome']).strip()
            cal = float(row.get('calorie', 0.0)) if pd.notna(row.get('calorie')) else 0.0
            c = float(row.get('carboidrati', 0.0)) if pd.notna(row.get('carboidrati')) else 0.0
            p = float(row.get('proteine', 0.0)) if pd.notna(row.get('proteine')) else 0.0
            f = float(row.get('grassi', 0.0)) if pd.notna(row.get('grassi')) else 0.0
            sat = float(row.get('di_cui_saturi', 0.0)) if pd.notna(row.get('di_cui_saturi')) else 0.0
            fib = float(row.get('fibre', 0.0)) if pd.notna(row.get('fibre')) else 0.0
            var_cott = float(row.get('var_cottura', 0.0)) if pd.notna(row.get('var_cottura')) else 0.0
            peso_pz = float(row.get('peso_medio_pz', 0.0)) if pd.notna(row.get('peso_medio_pz')) else 0.0
            unita_def = str(row.get('unita_default', 'g')).strip().lower()
            if unita_def not in ['g', 'ml', 'pz']: unita_def = 'g'
            
            mdb[nome] = (cal, p, c, f, fib, sat, var_cott, peso_pz, unita_def)
        return mdb if mdb else FALLBACK_DB
    except Exception as e:
        st.error(f"🚨 ERRORE SQL MACROS: {e}")
        return FALLBACK_DB

def get_current_macros_db():
    user_id = st.session_state.get("username", ADMIN_ID)
    return get_user_macros_db(user_id)


# ==========================================
# ☁️ SCRITTURA ED ELIMINAZIONE IN CLOUD (SUPABASE)
# ==========================================

def salva_su_cloud(nome, cal, p, c, f, sat, fib, var_cott, peso_pz, unita_def):
    user_id = st.session_state.get("username", ADMIN_ID)
    conn = get_conn()
    try:
        df_current = conn.query("SELECT * FROM macros", ttl=0)
        if not df_current.empty:
            df_current.columns = [c.lower() for c in df_current.columns]
            df_current = df_current.dropna(subset=['nome'])
            if 'user_id' not in df_current.columns: df_current['user_id'] = ADMIN_ID
                
            mask_esistente = (df_current['nome'].str.lower() == nome.lower()) & (df_current['user_id'] == user_id)
            df_current = df_current[~mask_esistente]
        else:
            df_current = pd.DataFrame(columns=["nome", "calorie", "carboidrati", "proteine", "grassi", "di_cui_saturi", "fibre", "var_cottura", "peso_medio_pz", "unita_default", "user_id"])
            
        nuova_riga = pd.DataFrame({
            "nome": [nome.title()], "calorie": [cal], "carboidrati": [c], "proteine": [p],
            "grassi": [f], "di_cui_saturi": [sat], "fibre": [fib], "var_cottura": [var_cott],
            "peso_medio_pz": [peso_pz], "unita_default": [unita_def], "user_id": [user_id]
        })
        df_updated = pd.concat([df_current, nuova_riga], ignore_index=True)
        
        cols_final = ["nome", "calorie", "carboidrati", "proteine", "grassi", "di_cui_saturi", "fibre", "var_cottura", "peso_medio_pz", "unita_default", "user_id"]
        for col in cols_final:
            if col not in df_updated.columns: df_updated[col] = 0.0
        df_updated = df_updated[cols_final]
        
        with conn.engine.begin() as engine_conn:
            df_updated.to_sql("macros", engine_conn, if_exists='replace', index=False)
            
        st.cache_data.clear()
        return True
    except Exception as e: 
        st.error(f"🚨 ERRORE SALVATAGGIO MACROS: {e}")
        return False

def elimina_da_cloud(nome):
    user_id = st.session_state.get("username", ADMIN_ID)
    conn = get_conn()
    try:
        df_current = conn.query("SELECT * FROM macros", ttl=0)
        if df_current.empty: return True
        df_current.columns = [c.lower() for c in df_current.columns]
        if 'user_id' not in df_current.columns: df_current['user_id'] = ADMIN_ID
        
        mask_da_eliminare = (df_current['nome'].str.lower() == nome.lower()) & (df_current['user_id'] == user_id)
        df_current = df_current[~mask_da_eliminare]
        
        with conn.engine.begin() as engine_conn:
            df_current.to_sql("macros", engine_conn, if_exists='replace', index=False)
            
        st.cache_data.clear()
        return True
    except Exception as e: 
        st.error(f"🚨 ERRORE ELIMINAZIONE MACROS: {e}")
        return False


# ==========================================
# 🔍 FUNZIONI DI RICERCA (WEB E LOCALE)
# ==========================================

@st.cache_data(ttl=3600) 
def cerca_alimento_web(nome):
    url = f"https://it.openfoodfacts.org/cgi/search.pl?search_terms={nome}&search_simple=1&action=process&json=1&page_size=5"
    try:
        res = requests.get(url, timeout=5).json()
        if res.get("products") and len(res["products"]) > 0:
            for prod in res["products"]:
                n = prod.get("nutriments", {})
                if "energy-kcal_100g" in n or "proteins_100g" in n:
                    cal = float(n.get("energy-kcal_100g", 0.0) or 0.0)
                    p = float(n.get("proteins_100g", 0.0) or 0.0)
                    c = float(n.get("carbohydrates_100g", 0.0) or 0.0)
                    f = float(n.get("fat_100g", 0.0) or 0.0)
                    fib = float(n.get("fiber_100g", 0.0) or 0.0)
                    sat = float(n.get("saturated-fat_100g", 0.0) or 0.0)
                    return True, cal, p, c, f, fib, sat, 0.0, 0.0, "g"
    except: pass
    return False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "g"

def cerca_locale(nome):
    nome_clean = nome.lower().replace("d'", "di ").strip()
    match_parziale = None
    macros_db = get_current_macros_db()
    
    for db_nome, macros in macros_db.items():
        db_clean = db_nome.lower().replace("d'", "di ")
        if db_clean == nome_clean:
            return True, db_nome, macros[0], macros[1], macros[2], macros[3], macros[4], macros[5], macros[6], macros[7], macros[8]
            
        if not match_parziale:
            if db_clean in nome_clean or nome_clean in db_clean:
                match_parziale = (True, db_nome, macros[0], macros[1], macros[2], macros[3], macros[4], macros[5], macros[6], macros[7], macros[8])
            elif len(set(nome_clean.split()).intersection(set(db_clean.split()))) >= 2:
                match_parziale = (True, db_nome, macros[0], macros[1], macros[2], macros[3], macros[4], macros[5], macros[6], macros[7], macros[8])
                
    if match_parziale: return match_parziale
    return False, "", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "g"

def get_macros_and_match(nome):
    trovato, db_nome, cal, p, c, f, fib, sat, var_cott, peso_pz, unita = cerca_locale(nome)
    if trovato: return db_nome, cal, p, c, f, fib, sat, var_cott, peso_pz, unita
    else: return nome, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "g"


# ==========================================
# 💾 GESTIONE BOZZE E SESSIONE LOCALE
# ==========================================

def salva_bozza_locale():
    username = st.session_state.get('username')
    if not username: return
    file_name = f"bozza_{username}.json"
    try:
        dati = {
            "nome_ricetta": st.session_state.get("nome_ricetta", "Nuova Ricetta"), 
            "ingredients": st.session_state.get("ingredients", [])
        }
        with open(file_name, "w") as f: json.dump(dati, f)
    except: pass

def carica_bozza_locale():
    username = st.session_state.get('username')
    if not username: return
    file_name = f"bozza_{username}.json"
    if os.path.exists(file_name):
        try:
            with open(file_name, "r") as f:
                dati = json.load(f)
                st.session_state.nome_ricetta = dati.get("nome_ricetta", "Nuova Ricetta")
                st.session_state.ingredients = dati.get("ingredients", [])
        except: pass

def svuota_laboratorio():
    st.session_state.ingredients = []
    st.session_state.nome_ricetta = "Nuova Ricetta"
    salva_bozza_locale()


# ==========================================
# 📝 PARSING E RICETTE
# ==========================================

def parse_ingredient_line(line):
    line = line.strip()
    if not line or line.startswith('#'): return None
    line = re.sub(r'^[\-\*\•]\s*', '', line)
    
    if ',' in line:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 2:
            try:
                qty = float(parts[1])
                unit_str = parts[2].lower() if len(parts) > 2 else ""
                unit = 'ml' if unit_str in ['ml', 'l'] else 'pz' if unit_str in ['pz', 'pezzi'] else 'g'
                if unit_str in ['kg', 'l']: qty *= 1000
                return qty, unit, parts[0]
            except ValueError: pass 
            
    match = re.match(r'^([0-9\.,]+)\s*(g|gr|ml|l|pz|kg|cucchiai|cucchiaini)?\s*(?:di\s+|d\')?\s*(.*)$', line, re.IGNORECASE)
    if match:
        qty = float(match.group(1).replace(',', '.'))
        u_s = (match.group(2) or '').lower()
        u = 'ml' if u_s in ['ml','l'] else 'pz' if u_s == 'pz' else 'g'
        if u_s in ['kg', 'l']: qty *= 1000
        return qty, u, match.group(3).strip()
    return 100.0, 'g', line 

def process_ingredient_list(lines):
    aggiunti = 0
    if "ingredients" not in st.session_state: st.session_state.ingredients = []
    for line in lines:
        parsed = parse_ingredient_line(line)
        if not parsed: continue
        qty, unit, name = parsed
        m_name, cal, p, c, f, fib, sat, var_cott, db_peso_pz, db_unita = get_macros_and_match(name)
        if unit == 'g' and qty < 20 and any(x in name.lower() for x in ["uov", "banan", "datter"]): unit = 'pz'
        st.session_state.ingredients.append({
            "id": uuid.uuid4().hex, "nome": name.title(), "matched_name": m_name, 
            "quantita": qty, "unita": unit, "peso_pz": db_peso_pz, "peso": qty * db_peso_pz if unit == 'pz' else qty, 
            "ruolo": "Impasto", "cal_100": cal, "prot_100": p, "carb_100": c, "fat_100": f, "sat_100": sat, "fib_100": fib
        })
        aggiunti += 1
    salva_bozza_locale()
    return aggiunti

def ricalcola_ingrediente(ing_id):
    if "ingredients" not in st.session_state: return
    for ing in st.session_state.ingredients:
        if ing['id'] == ing_id:
            ing['nome'] = st.session_state.get(f"n_{ing_id}", ing['nome'])
            ing['quantita'] = st.session_state.get(f"q_{ing_id}", ing['quantita'])
            ing['unita'] = st.session_state.get(f"u_{ing_id}", ing['unita'])
            ing['ruolo'] = st.session_state.get(f"ruolo_{ing_id}", ing.get('ruolo', 'Impasto'))
            if ing['unita'] == 'pz': ing['peso_pz'] = st.session_state.get(f"pw_{ing_id}", 0.0)
            ing['peso'] = ing['quantita'] * ing['peso_pz'] if ing['unita'] == 'pz' else ing['quantita']
            ing['cal_100'] = st.session_state.get(f"cal2_{ing_id}", ing['cal_100'])
            ing['prot_100'] = st.session_state.get(f"p2_{ing_id}", ing['prot_100'])
            ing['carb_100'] = st.session_state.get(f"c2_{ing_id}", ing['carb_100'])
            ing['fat_100'] = st.session_state.get(f"f2_{ing_id}", ing['fat_100'])
            ing['sat_100'] = st.session_state.get(f"sat2_{ing_id}", ing['sat_100'])
            ing['fib_100'] = st.session_state.get(f"fib2_{ing_id}", ing['fib_100'])
            break
    salva_bozza_locale()

def safe_fl(val, default=0.0):
    try: return float(val) if pd.notna(val) else default
    except: return default

def ripristina_ricetta(df):
    if df.empty: return
    row0 = df.iloc[0]
    nome_r = str(row0.get('Ricetta_Nome', 'Nuova Ricetta'))
    if not nome_r or nome_r.lower() in ['nan', 'none', '']: nome_r = "Nuova Ricetta"
    st.session_state.nome_ricetta = nome_r
    st.session_state.procedimento = str(row0.get('Ricetta_Procedimento', '') or '')
    st.session_state.riposo = str(row0.get('Ricetta_Riposo', '') or '')
    cat_str = str(row0.get('Ricetta_Categorie', '') or '')
    if cat_str and cat_str.lower() != 'nan': st.session_state.tipo_ricetta = [c.strip() for c in cat_str.split(',')]
    else: st.session_state.tipo_ricetta = []
    st.session_state.porzioni = int(safe_fl(row0.get('Ricetta_Porzioni', 1), 1))
    st.session_state.richiede_cottura = bool(row0.get('Cottura_Richiesta', False))
    st.session_state.m_cot = str(row0.get('Cottura_Modalita', 'Forno') or 'Forno')
    st.session_state.t_cot = str(row0.get('Cottura_Tempo', '') or '')
    st.session_state.temp_cot = int(safe_fl(row0.get('Cottura_Temperatura', 180), 180))
    st.session_state.tipo_resa = str(row0.get('Cottura_TipoResa', 'Usa % di stima') or 'Usa % di stima')
    if 'Cottura_Variazione' in row0: st.session_state.var_cottura = float(safe_fl(row0['Cottura_Variazione'], -15.0))
    else: st.session_state.var_cottura = -float(safe_fl(row0.get('Cottura_Calo', 15.0), 15.0))
    st.session_state.peso_cotto_reale = float(safe_fl(row0.get('Cottura_PesoReale', 85.0), 85.0))
    st.session_state.qta_teglia = float(safe_fl(row0.get('Cottura_QtaTeglia', 100.0), 100.0))
    st.session_state.ingredients = []
    for _, row in df.iterrows():
        qty = safe_fl(row.get('Quantita', 0))
        u = str(row.get('Unita', 'g')).strip()
        pz_w = safe_fl(row.get('Peso_pz', 0.0), 0.0)
        nome_ing = str(row.get('Nome', 'Ingrediente')).strip()
        if not nome_ing or nome_ing.lower() in ['nan', 'none']: nome_ing = "Ingrediente"
        st.session_state.ingredients.append({
            "id": uuid.uuid4().hex, "nome": nome_ing, "matched_name": nome_ing,
            "quantita": qty, "unita": u, "peso_pz": pz_w, "peso": qty * pz_w if u == 'pz' else qty,
            "ruolo": str(row.get('Utilizzo', 'Impasto')) if pd.notna(row.get('Utilizzo')) else 'Impasto',
            "cal_100": safe_fl(row.get('Cal_100g'), 0.0), "prot_100": safe_fl(row.get('Prot_100g'), 0.0),
            "carb_100": safe_fl(row.get('Carb_100g'), 0.0), "fat_100": safe_fl(row.get('Fat_100g'), 0.0),
            "sat_100": safe_fl(row.get('Sat_100g'), 0.0), "fib_100": safe_fl(row.get('Fib_100g'), 0.0)
        })
    salva_bozza_locale()

# ==========================================
# 🧪 CLOUD RICETTE
# ==========================================

def get_ricette_utente_e_community(user_id, admin_id):
    conn = get_conn()
    try:
        query = "SELECT * FROM ricette"
        df = conn.query(query, ttl=0)
        if df.empty: return pd.DataFrame(columns=["Nome Ricetta", "Categoria", "Dati JSON", "User_ID", "Condivisa"])
        cols_map = {c.lower(): c for c in df.columns}
        c_nome = cols_map.get('nome_ricetta') or cols_map.get('nomericetta') or cols_map.get('nome')
        c_cat = cols_map.get('categoria')
        c_json = cols_map.get('dati_json') or cols_map.get('datijson') or cols_map.get('json')
        c_user = cols_map.get('user_id') or cols_map.get('userid')
        c_cond = cols_map.get('condivisa')
        res = pd.DataFrame()
        res['Nome Ricetta'] = df[c_nome] if c_nome else "Senza Titolo"
        res['Categoria'] = df[c_cat] if c_cat else ""
        res['Dati JSON'] = df[c_json] if c_json else "{}"
        res['User_ID'] = df[c_user] if c_user else admin_id
        res['Condivisa'] = df[c_cond] if c_cond else True
        res['Nome Ricetta'] = res['Nome Ricetta'].fillna("Senza Titolo").astype(str)
        res['Nome Ricetta'] = res['Nome Ricetta'].apply(lambda x: "Senza Titolo" if x.strip() in ["", "nan", "None"] else x)
        return res
    except Exception as e:
        st.error(f"🚨 ERRORE SQL RICETTE: {e}")
        return pd.DataFrame(columns=["Nome Ricetta", "Categoria", "Dati JSON", "User_ID", "Condivisa"])

def salva_ricetta_cloud(user_id, nome_ricetta, categoria, json_dati, condivisa):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM ricette WHERE LOWER(user_id) = LOWER(:uid) AND LOWER(nome_ricetta) = LOWER(:nome)"), {"uid": user_id, "nome": nome_ricetta})
            e.execute(text("INSERT INTO ricette (user_id, nome_ricetta, categoria, dati_json, condivisa) VALUES (:uid, :nome, :cat, :dati, :cond)"), {"uid": user_id, "nome": nome_ricetta, "cat": categoria, "dati": json_dati, "cond": condivisa})
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE SALVATAGGIO RICETTA: {e}")
        return False

def elimina_ricetta_cloud(user_id, nome_ricetta):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM ricette WHERE LOWER(user_id) = LOWER(:uid) AND LOWER(nome_ricetta) = LOWER(:nome)"), {"uid": user_id, "nome": nome_ricetta})
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE ELIMINAZIONE RICETTA: {e}")
        return False

# ==========================================
# 📅 GESTIONE DIARIO
# ==========================================

def get_diario_utente(user_id):
    conn = get_conn()
    try:
        query_sql = ("SELECT id, data, pasto, elemento, quantita, unita, calorie, "
                     "carboidrati, proteine, grassi, saturi, fibre, user_id, "
                     "tgt_cal, tgt_c, tgt_p, tgt_f, stato "
                     "FROM diario WHERE LOWER(user_id) = LOWER(:uid)")
        df = conn.query(query_sql, params={"uid": user_id}, ttl=0)
        if df.empty: return pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"])
        df.columns = ["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"]
        return df
    except Exception as e:
        st.error(f"🚨 ERRORE SQL DIARIO: {e}")
        return pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"])

def elimina_voce_diario(id_voce):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM diario WHERE id = :id_voce"), {"id_voce": id_voce})
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE ELIMINAZIONE VOCE DIARIO: {e}")
        return False

def aggiorna_voce_diario(id_voce, nuova_qta, cal, c, p, f, stato, elemento=None):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            if elemento:
                query_sql = ("UPDATE diario SET quantita = :qta, calorie = :cal, carboidrati = :c, "
                             "proteine = :p, grassi = :f, stato = :st, elemento = :elem WHERE id = :id_voce")
                e.execute(text(query_sql), {"qta": nuova_qta, "cal": cal, "c": c, "p": p, "f": f, "st": stato, "elem": elemento, "id_voce": id_voce})
            else:
                query_sql = ("UPDATE diario SET quantita = :qta, calorie = :cal, carboidrati = :c, "
                             "proteine = :p, grassi = :f, stato = :st WHERE id = :id_voce")
                e.execute(text(query_sql), {"qta": nuova_qta, "cal": cal, "c": c, "p": p, "f": f, "st": stato, "id_voce": id_voce})
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE AGGIORNAMENTO DIARIO: {e}")
        return False

# ==========================================
# 📆 GESTIONE MEAL PLANNER
# ==========================================

def get_pasti_futuri_utente(user_id, oggi_str):
    conn = get_conn()
    try:
        query_sql = ("SELECT id, data, pasto, elemento, quantita, unita, calorie, "
                     "carboidrati, proteine, grassi, saturi, fibre, user_id, "
                     "tgt_cal, tgt_c, tgt_p, tgt_f, stato "
                     "FROM diario WHERE LOWER(user_id) = LOWER(:uid) "
                     "AND (data > :oggi OR (data = :oggi AND stato = 'Pianificato'))")
        df = conn.query(query_sql, params={"uid": user_id, "oggi": oggi_str}, ttl=0)
        if df.empty: return pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"])
        df.columns = ["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"]
        return df
    except Exception as e:
        st.error(f"🚨 ERRORE SQL MEAL PLANNER: {e}")
        return pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"])

def elimina_giornata_planner(user_id, data_str):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM diario WHERE LOWER(user_id) = LOWER(:uid) AND data = :data"), {"uid": user_id, "data": data_str})
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE ELIMINAZIONE PLANNER: {e}")
        return False

def clona_giornata_db(nuovi_pasti_list):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            query_sql = ("INSERT INTO diario (id, data, pasto, elemento, quantita, unita, calorie, "
                         "carboidrati, proteine, grassi, saturi, fibre, user_id, tgt_cal, tgt_c, tgt_p, tgt_f, stato) "
                         "VALUES (:id, :data, :pasto, :elemento, :quantita, :unita, :calorie, "
                         ":carboidrati, :proteine, :grassi, :saturi, :fibre, :user_id, :tgt_cal, :tgt_c, :tgt_p, :tgt_f, :stato)")
            for p in nuovi_pasti_list:
                e.execute(text(query_sql), p)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE CLONAZIONE PLANNER: {e}")
        return False

# ==========================================
# 📦 GESTIONE DISPENSA
# ==========================================

def get_dispensa_utente(user_id):
    conn = get_conn()
    try:
        query = "SELECT nome, quantita, unita, monitora, user_id FROM dispensa WHERE LOWER(user_id) = LOWER(:uid)"
        df = conn.query(query, params={"uid": user_id}, ttl=0)
        if df.empty: return pd.DataFrame(columns=["User_ID", "Nome", "Quantita", "Unita", "Monitora"])
        df.columns = ["Nome", "Quantita", "Unita", "Monitora", "User_ID"]
        return df[['User_ID', 'Nome', 'Quantita', 'Unita', 'Monitora']]
    except Exception as e:
        st.error(f"🚨 ERRORE SQL DISPENSA: {e}")
        return pd.DataFrame(columns=["User_ID", "Nome", "Quantita", "Unita", "Monitora"])

def aggiungi_item_dispensa(user_id, nome, quantita, unita, monitora=True):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            query_sql = ("INSERT INTO dispensa (user_id, nome, quantita, unita, monitora) "
                         "VALUES (:uid, :nome, :qta, :unita, :mon) ON CONFLICT (user_id, nome) "
                         "DO UPDATE SET quantita = EXCLUDED.quantita, unita = EXCLUDED.unita, monitora = EXCLUDED.monitora")
            e.execute(text(query_sql), {"uid": user_id, "nome": nome, "qta": quantita, "unita": unita, "mon": monitora})
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE AGGIUNTA DISPENSA: {e}")
        return False

def salva_modifiche_dispensa(user_id, edited_df):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM dispensa WHERE LOWER(user_id) = LOWER(:uid)"), {"uid": user_id})
            for _, r in edited_df.iterrows():
                e.execute(text("INSERT INTO dispensa (user_id, nome, quantita, unita, monitora) VALUES (:uid, :nome, :qta, :unita, :mon)"), {
                    "uid": user_id, "nome": r['Nome'], "qta": float(r['Quantita']), "unita": r['Unita'], "mon": bool(r['Monitora'])
                })
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE SALVATAGGIO DISPENSA: {e}")
        return False

# ==========================================
# 👤 GESTIONE PROFILO
# ==========================================

def get_profilo_utente(user_id):
    conn = get_conn()
    try:
        query = "SELECT user_id, peso, altezza, eta, sesso, attivita, tgt_cal, tgt_c, tgt_p, tgt_f FROM profilo WHERE LOWER(user_id) = LOWER(:uid)"
        df = conn.query(query, params={"uid": user_id}, ttl=0)
        if df.empty: return pd.DataFrame(columns=["User_ID", "Peso", "Altezza", "Eta", "Sesso", "Attivita", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F"])
        df.columns = ["User_ID", "Peso", "Altezza", "Eta", "Sesso", "Attivita", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F"]
        return df
    except Exception as e:
        st.error(f"🚨 ERRORE SQL PROFILO: {e}")
        return pd.DataFrame(columns=["User_ID", "Peso", "Altezza", "Eta", "Sesso", "Attivita", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F"])

def salva_profilo_utente(user_id, peso, altezza, eta, sesso, attivita, tgt_cal, tgt_c, tgt_p, tgt_f):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            query_sql = ("INSERT INTO profilo (user_id, peso, altezza, eta, sesso, attivita, tgt_cal, tgt_c, tgt_p, tgt_f) "
                         "VALUES (:uid, :peso, :altezza, :eta, :sesso, :attivita, :tgt_cal, :tgt_c, :tgt_p, :tgt_f) "
                         "ON CONFLICT (user_id) DO UPDATE SET peso = EXCLUDED.peso, altezza = EXCLUDED.altezza, "
                         "eta = EXCLUDED.eta, sesso = EXCLUDED.sesso, attivita = EXCLUDED.attivita, "
                         "tgt_cal = EXCLUDED.tgt_cal, tgt_c = EXCLUDED.tgt_c, tgt_p = EXCLUDED.tgt_p, tgt_f = EXCLUDED.tgt_f")
            e.execute(text(query_sql), {
                "uid": user_id, "peso": peso, "altezza": altezza, "eta": eta, 
                "sesso": sesso, "attivita": attivita, "tgt_cal": tgt_cal, 
                "tgt_c": tgt_c, "tgt_p": tgt_p, "tgt_f": tgt_f
            })
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 ERRORE SALVATAGGIO PROFILO: {e}")
        return False