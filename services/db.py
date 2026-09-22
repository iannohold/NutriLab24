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
ADMIN_ID = "iannovins@gmail.com"

RUOLI_LIST = ["Impasto", "Farcitura", "Topping", "Salsa", "Decorazione", "Altro"]
CATEGORIE_LIST = ["☕ Colazione", "🍰 Dessert", "🍝 Primo", "🥩 Secondo", "🍲 Piatto unico", "🥪 Spuntino", "💪 Post work-out", "🔹 Altro"]

FALLBACK_DB = {
    "Farina di avena": (370.0, 13.5, 68.0, 7.0, 10.0, 1.2, 0.0, 0.0, 0.0, "g", "", "Materia Prima"),
    "Latte (Senza lattosio)": (47.0, 3.4, 5.0, 1.5, 0.0, 1.0, 0.0, 0.0, 0.0, "ml", "", "Materia Prima"),
    "Uova intere": (143.0, 12.5, 0.6, 9.5, 0.0, 3.1, 0.0, 0.0, 55.0, "pz", "", "Materia Prima")
}

def get_conn():
   return st.connection("supabase", type="sql", pool_size=5, max_overflow=10, pool_pre_ping=True)

# ==========================================
# 🗄️ DATABASE PRODOTTI (MACROS)
# ==========================================

@st.cache_data(ttl=60)
def get_ean_mapping(user_id):
    conn = get_conn()
    try:
        query = "SELECT nome, ean FROM macros WHERE ean IS NOT NULL AND ean != '' AND LOWER(user_id) IN (LOWER(:adm), LOWER(:uid))"
        df = conn.query(query, params={"adm": ADMIN_ID, "uid": user_id}, ttl=0)
        if not df.empty:
            return dict(zip(df['ean'].astype(str).str.strip(), df['nome']))
    except Exception: pass
    return {}

@st.cache_data(ttl=60)  
def get_user_macros_db(user_id):
    conn = get_conn()
    try:
        query = """
            SELECT nome, calorie, carboidrati, proteine, grassi, di_cui_saturi, fibre, sale, 
                   var_cottura, peso_medio_pz, unita_default, marca, tipologia, user_id 
            FROM macros 
            WHERE LOWER(user_id) IN (LOWER(:adm), LOWER(:uid))
        """
        df = conn.query(query, params={"adm": ADMIN_ID, "uid": user_id}, ttl=0)
        if df.empty: return FALLBACK_DB
        
        df['nome'] = df['nome'].astype(str).str.strip()
        df = df.sort_values('user_id').drop_duplicates(subset=['nome'], keep='last')
        
        mdb = {}
        for _, row in df.iterrows():
            nome = row['nome']
            cal = float(row.get('calorie') or 0.0)
            c = float(row.get('carboidrati') or 0.0)
            p = float(row.get('proteine') or 0.0)
            f = float(row.get('grassi') or 0.0)
            sat = float(row.get('di_cui_saturi') or 0.0)
            fib = float(row.get('fibre') or 0.0)
            sale = float(row.get('sale') or 0.0)
            var_cott = float(row.get('var_cottura') or 0.0)
            peso_pz = float(row.get('peso_medio_pz') or 0.0)
            unita_def = str(row.get('unita_default') or 'g').strip().lower()
            if unita_def not in ['g', 'ml', 'pz']: unita_def = 'g'
            marca = str(row.get('marca') or '').strip()
            tipologia = str(row.get('tipologia') or 'Materia Prima').strip()
            
            mdb[nome] = (cal, p, c, f, fib, sat, sale, var_cott, peso_pz, unita_def, marca, tipologia)
        return mdb if mdb else FALLBACK_DB
    except Exception as e:
        st.error(f"🚨 ERRORE SQL MACROS: {e}")
        return FALLBACK_DB

def get_current_macros_db():
    return get_user_macros_db(st.session_state.get("username", ADMIN_ID))

def salva_su_cloud(nome, cal, p, c, f, sat, fib, sale, var_cott, peso_pz, unita_def, marca="", tipologia="Materia Prima", ean=""):
    user_id = st.session_state.get("username", ADMIN_ID)
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM macros WHERE LOWER(nome) = LOWER(:nome) AND LOWER(user_id) = LOWER(:uid)"), 
                      {"nome": nome, "uid": user_id})
            
            query = text("""
                INSERT INTO macros 
                (nome, calorie, carboidrati, proteine, grassi, di_cui_saturi, fibre, sale, var_cottura, peso_medio_pz, unita_default, user_id, marca, tipologia, ean) 
                VALUES (:n, :cal, :c, :p, :f, :sat, :fib, :sal, :var, :pz, :u, :uid, :m, :t, :ean)
            """)
            e.execute(query, {
                "n": nome.title(), "cal": cal, "c": c, "p": p, "f": f, "sat": sat, "fib": fib, 
                "sal": sale, "var": var_cott, "pz": peso_pz, "u": unita_def, "uid": user_id, 
                "m": marca, "t": tipologia, "ean": ean
            })
        st.cache_data.clear()
        return True
    except Exception as ex:
        st.error(f"🚨 ERRORE SALVATAGGIO CLOUD: {ex}")
        return False

def elimina_da_cloud(nome):
    user_id = st.session_state.get("username", ADMIN_ID)
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM macros WHERE LOWER(nome) = LOWER(:nome) AND LOWER(user_id) = LOWER(:uid)"), 
                      {"nome": nome, "uid": user_id})
        st.cache_data.clear()
        return True
    except Exception as ex: 
        st.error(f"🚨 ERRORE ELIMINAZIONE MACROS: {ex}")
        return False

@st.cache_data(ttl=3600)

def cerca_alimento_web(query):
    query = str(query).strip()
    headers = {"User-Agent": "NutriLab24 - WebApp/1.0 - Streamlit (vincenzo)"}
    
    if query.isdigit() and len(query) >= 8:
        url = f"https://world.openfoodfacts.org/api/v0/product/{query}.json"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()  # Blocca e segnala se il server dà errore (es. 500, 503)
            data = res.json()
            
            if data.get("status") == 1:
                n = data.get("product", {}).get("nutriments", {})
                marca = data.get("product", {}).get("brands", "").split(",")[0].title()
                return True, float(n.get("energy-kcal_100g") or 0.0), float(n.get("proteins_100g") or 0.0), float(n.get("carbohydrates_100g") or 0.0), float(n.get("fat_100g") or 0.0), float(n.get("fiber_100g") or 0.0), float(n.get("saturated-fat_100g") or 0.0), float(n.get("salt_100g") or 0.0), 0.0, 0.0, "g", marca, "Prodotto Confezionato"
        except Exception as e:
            st.error(f"⚠️ Dettaglio errore OpenFoodFacts (Codice a barre): {e}")
    else:
        url = f"https://it.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=3"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()  # Blocca e segnala se il server dà errore
            data = res.json()
            
            if data.get("products") and len(data["products"]) > 0:
                for prod in data["products"]:
                    n = prod.get("nutriments", {})
                    if "energy-kcal_100g" in n or "proteins_100g" in n:
                        marca = prod.get("brands", "").split(",")[0].title()
                        return True, float(n.get("energy-kcal_100g") or 0.0), float(n.get("proteins_100g") or 0.0), float(n.get("carbohydrates_100g") or 0.0), float(n.get("fat_100g") or 0.0), float(n.get("fiber_100g") or 0.0), float(n.get("saturated-fat_100g") or 0.0), float(n.get("salt_100g") or 0.0), 0.0, 0.0, "g", marca, "Prodotto Confezionato"
        except Exception as e:
            st.error(f"⚠️ Dettaglio errore OpenFoodFacts (Ricerca Testuale): {e}")
            
    return False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "g", "", "Materia Prima"

def cerca_locale(nome):
    nome_clean = nome.lower().replace("d'", "di ").strip()
    macros_db = get_current_macros_db()
    
    if nome_clean.isdigit():
        ean_map = get_ean_mapping(st.session_state.get("username", ADMIN_ID))
        if nome_clean in ean_map:
            vero_nome = ean_map[nome_clean]
            if vero_nome in macros_db:
                mac = macros_db[vero_nome]
                return True, vero_nome, mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], mac[6], mac[7], mac[8], mac[9], mac[10], mac[11]

    match_parziale = None
    for db_nome, macros in macros_db.items():
        db_clean = db_nome.lower().replace("d'", "di ")
        if db_clean == nome_clean:
            return True, db_nome, macros[0], macros[1], macros[2], macros[3], macros[4], macros[5], macros[6], macros[7], macros[8], macros[9], macros[10], macros[11]
            
        if not match_parziale:
            if db_clean in nome_clean or nome_clean in db_clean:
                match_parziale = (True, db_nome, macros[0], macros[1], macros[2], macros[3], macros[4], macros[5], macros[6], macros[7], macros[8], macros[9], macros[10], macros[11])
            elif len(set(nome_clean.split()).intersection(set(db_clean.split()))) >= 2:
                match_parziale = (True, db_nome, macros[0], macros[1], macros[2], macros[3], macros[4], macros[5], macros[6], macros[7], macros[8], macros[9], macros[10], macros[11])
                
    if match_parziale: return match_parziale
    return False, "", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "g", "", "Materia Prima"

def get_macros_and_match(nome):
    trovato, db_nome, cal, p, c, f, fib, sat, sale, var_cott, peso_pz, unita, marca, tipo = cerca_locale(nome)
    if trovato: return db_nome, cal, p, c, f, fib, sat, sale, var_cott, peso_pz, unita, marca, tipo
    else: return nome, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "g", "", "Materia Prima"

# ==========================================
# 💾 GESTIONE BOZZE E SESSIONE LOCALE
# ==========================================

def salva_bozza_locale():
    try:
        dati = {"nome_ricetta": st.session_state.get("nome_ricetta", "Nuova Ricetta"), "ingredients": st.session_state.get("ingredients", [])}
        with open(f"bozza_{st.session_state.get('username')}.json", "w") as f: json.dump(dati, f)
    except: pass

def carica_bozza_locale():
    file_name = f"bozza_{st.session_state.get('username')}.json"
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
        m_name, cal, p, c, f, fib, sat, sale, var_cott, db_peso_pz, db_unita, m_marca, m_tipo = get_macros_and_match(name)
        if unit == 'g' and qty < 20 and any(x in name.lower() for x in ["uov", "banan", "datter"]): unit = 'pz'
        st.session_state.ingredients.append({
            "id": uuid.uuid4().hex, "nome": name.title(), "matched_name": m_name, 
            "quantita": qty, "unita": unit, "peso_pz": db_peso_pz, "peso": qty * db_peso_pz if unit == 'pz' else qty, 
            "ruolo": "Impasto", "cal_100": cal, "prot_100": p, "carb_100": c, "fat_100": f, "sat_100": sat, "fib_100": fib, "sale_100": sale
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
            ing['sat_100'] = st.session_state.get(f"sat2_{ing_id}", ing.get('sat_100', 0.0))
            ing['fib_100'] = st.session_state.get(f"fib2_{ing_id}", ing.get('fib_100', 0.0))
            ing['sale_100'] = st.session_state.get(f"sale2_{ing_id}", ing.get('sale_100', 0.0))
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
            "sat_100": safe_fl(row.get('Sat_100g'), 0.0), "fib_100": safe_fl(row.get('Fib_100g'), 0.0),
            "sale_100": safe_fl(row.get('Sale_100g'), 0.0)
        })
    salva_bozza_locale()

# ==========================================
# 🧪 CLOUD RICETTE
# ==========================================

def get_ricette_utente_e_community(user_id, admin_id):
    conn = get_conn()
    try:
        query = """
            SELECT nome_ricetta AS "Nome Ricetta", categoria AS "Categoria", 
                   dati_json AS "Dati JSON", user_id AS "User_ID", condivisa AS "Condivisa" 
            FROM ricette
        """
        df = conn.query(query, ttl=0)
        if df.empty: return pd.DataFrame(columns=["Nome Ricetta", "Categoria", "Dati JSON", "User_ID", "Condivisa"])
        
        df['Condivisa'] = df['Condivisa'].apply(lambda x: True if str(x).lower() in ['1', 'true', 't'] else False)
        df['Nome Ricetta'] = df['Nome Ricetta'].fillna("Senza Titolo").astype(str)
        return df
    except Exception as e:
        st.error(f"🚨 ERRORE SQL RICETTE: {e}")
        return pd.DataFrame(columns=["Nome Ricetta", "Categoria", "Dati JSON", "User_ID", "Condivisa"])

def salva_ricetta_cloud(user_id, nome_ricetta, categoria, json_dati, condivisa):
    conn = get_conn()
    try:
        cond_val = 1 if condivisa else 0
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM ricette WHERE LOWER(user_id) = LOWER(:uid) AND LOWER(nome_ricetta) = LOWER(:nome)"), 
                      {"uid": user_id, "nome": nome_ricetta})
            e.execute(text("INSERT INTO ricette (user_id, nome_ricetta, categoria, dati_json, condivisa) VALUES (:uid, :nome, :cat, :dati, :cond)"), 
                      {"uid": user_id, "nome": nome_ricetta, "cat": categoria, "dati": json_dati, "cond": cond_val})
        st.cache_data.clear()
        return True
    except Exception as ex: 
        st.error(f"🚨 ERRORE SALVATAGGIO RICETTA: {ex}")
        return False

def elimina_ricetta_cloud(user_id, nome_ricetta):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM ricette WHERE LOWER(user_id) = LOWER(:uid) AND LOWER(nome_ricetta) = LOWER(:nome)"), 
                      {"uid": user_id, "nome": nome_ricetta})
        st.cache_data.clear()
        return True
    except Exception as ex: 
        return False

# ==========================================
# 📅 GESTIONE DIARIO E MEAL PLANNER
# ==========================================

def get_diario_utente(user_id):
    conn = get_conn()
    try:
        query_sql = """
            SELECT id, data, pasto, elemento, quantita, unita, calorie, carboidrati, proteine, 
                   grassi, saturi, fibre, sale, user_id, tgt_cal, tgt_c, tgt_p, tgt_f, stato 
            FROM diario WHERE LOWER(user_id) = LOWER(:uid)
        """
        df = conn.query(query_sql, params={"uid": user_id}, ttl=0)
        if df.empty: return pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "Sale", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"])
        df.columns = ["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "Sale", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"]
        return df
    except: return pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "Sale", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"])

def elimina_voce_diario(id_voce):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM diario WHERE id = :id_voce"), {"id_voce": id_voce})
        st.cache_data.clear()
        return True
    except: return False

def aggiorna_voce_diario(id_voce, nuova_qta, cal, c, p, f, sal, stato, elemento=None):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            if elemento:
                query = text("""
                    UPDATE diario SET quantita=:qta, calorie=:cal, carboidrati=:c, proteine=:p, 
                    grassi=:f, sale=:sal, stato=:st, elemento=:elem WHERE id=:id_voce
                """)
                e.execute(query, {"qta": nuova_qta, "cal": cal, "c": c, "p": p, "f": f, "sal": sal, "st": stato, "elem": elemento, "id_voce": id_voce})
            else:
                query = text("""
                    UPDATE diario SET quantita=:qta, calorie=:cal, carboidrati=:c, proteine=:p, 
                    grassi=:f, sale=:sal, stato=:st WHERE id=:id_voce
                """)
                e.execute(query, {"qta": nuova_qta, "cal": cal, "c": c, "p": p, "f": f, "sal": sal, "st": stato, "id_voce": id_voce})
        st.cache_data.clear()
        return True
    except: return False

def get_pasti_futuri_utente(user_id, oggi_str):
    conn = get_conn()
    try:
        query_sql = """
            SELECT id, data, pasto, elemento, quantita, unita, calorie, carboidrati, proteine, 
                   grassi, saturi, fibre, sale, user_id, tgt_cal, tgt_c, tgt_p, tgt_f, stato 
            FROM diario 
            WHERE LOWER(user_id) = LOWER(:uid) AND (data > :oggi OR (data = :oggi AND stato = 'Pianificato'))
        """
        df = conn.query(query_sql, params={"uid": user_id, "oggi": oggi_str}, ttl=0)
        if df.empty: return pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "Sale", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"])
        df.columns = ["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "Sale", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"]
        return df
    except: return pd.DataFrame(columns=["ID", "Data", "Pasto", "Elemento", "Quantita", "Unita", "Calorie", "Carboidrati", "Proteine", "Grassi", "Saturi", "Fibre", "Sale", "User_ID", "TGT_Cal", "TGT_C", "TGT_P", "TGT_F", "Stato"])

def elimina_giornata_planner(user_id, data_str):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM diario WHERE LOWER(user_id) = LOWER(:uid) AND data = :data"), 
                      {"uid": user_id, "data": data_str})
        st.cache_data.clear()
        return True
    except: return False

def clona_giornata_db(nuovi_pasti_list):
    if not nuovi_pasti_list: return True
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            query_sql = text("""
                INSERT INTO diario (id, data, pasto, elemento, quantita, unita, calorie, carboidrati, 
                proteine, grassi, saturi, fibre, sale, user_id, tgt_cal, tgt_c, tgt_p, tgt_f, stato) 
                VALUES (:id, :data, :pasto, :elemento, :quantita, :unita, :calorie, :carboidrati, 
                :proteine, :grassi, :saturi, :fibre, :sale, :user_id, :tgt_cal, :tgt_c, :tgt_p, :tgt_f, :stato)
            """)
            e.execute(query_sql, nuovi_pasti_list)
        st.cache_data.clear()
        return True
    except Exception as ex: 
        st.error(f"🚨 ERRORE CLONAZIONE PLANNER: {ex}")
        return False

# ==========================================
# 📦 GESTIONE DISPENSA E PROFILO
# ==========================================

def get_dispensa_utente(user_id):
    conn = get_conn()
    try:
        query = "SELECT user_id, nome, quantita, unita, monitora FROM dispensa WHERE LOWER(user_id) = LOWER(:uid)"
        df = conn.query(query, params={"uid": user_id}, ttl=0)
        if df.empty: return pd.DataFrame(columns=["User_ID", "Nome", "Quantita", "Unita", "Monitora"])
        df.columns = ["User_ID", "Nome", "Quantita", "Unita", "Monitora"]
        return df[['User_ID', 'Nome', 'Quantita', 'Unita', 'Monitora']]
    except: return pd.DataFrame(columns=["User_ID", "Nome", "Quantita", "Unita", "Monitora"])

def aggiungi_item_dispensa(user_id, nome, quantita, unita, monitora=True):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            query = text("""
                INSERT INTO dispensa (user_id, nome, quantita, unita, monitora) 
                VALUES (:uid, :nome, :qta, :unita, :mon) 
                ON CONFLICT (user_id, nome) 
                DO UPDATE SET quantita = EXCLUDED.quantita, unita = EXCLUDED.unita, monitora = EXCLUDED.monitora
            """)
            e.execute(query, {"uid": user_id, "nome": nome, "qta": quantita, "unita": unita, "mon": monitora})
        st.cache_data.clear()
        return True
    except: return False

def salva_modifiche_dispensa(user_id, edited_df):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            e.execute(text("DELETE FROM dispensa WHERE LOWER(user_id) = LOWER(:uid)"), {"uid": user_id})
            records = [{"uid": user_id, "nome": r['Nome'], "qta": float(r['Quantita']), "unita": r['Unita'], "mon": bool(r['Monitora'])} for _, r in edited_df.iterrows()]
            
            if records:
                query = text("INSERT INTO dispensa (user_id, nome, quantita, unita, monitora) VALUES (:uid, :nome, :qta, :unita, :mon)")
                e.execute(query, records)
        st.cache_data.clear()
        return True
    except Exception as ex:
        st.error(f"🚨 ERRORE SALVATAGGIO DISPENSA: {ex}")
        return False

# ----------------- PROFILO E STORICO -----------------

def get_profilo_utente(user_id):
    conn = get_conn()
    try:
        query = """
            SELECT user_id, peso, altezza, eta, sesso, attivita, tgt_cal, tgt_c, tgt_p, tgt_f, tgt_sale, tgt_acqua,
                   obiettivo, circ_collo, circ_petto, circ_vita, circ_fianchi, circ_braccio, circ_coscia, circ_polpaccio,
                   massa_grassa, massa_muscolare, massa_ossea, acqua_corporea 
            FROM profilo WHERE LOWER(user_id) = LOWER(:uid)
        """
        df = conn.query(query, params={"uid": user_id}, ttl=0)
        if not df.empty: df.columns = [c.lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def salva_profilo_utente(user_id, data_pesata, peso, altezza, eta, sesso, attivita, tgt_cal, tgt_c, tgt_p, tgt_f, tgt_sale, tgt_acqua,
                         obiettivo, c_col, c_pet, c_vit, c_fia, c_bra, c_cos, c_pol, m_grassa, m_musc, m_ossea, acqua):
    conn = get_conn()
    try:
        with conn.engine.begin() as e:
            query_prof = text("""
                INSERT INTO profilo (user_id, peso, altezza, eta, sesso, attivita, tgt_cal, tgt_c, tgt_p, tgt_f, tgt_sale, tgt_acqua,
                                     obiettivo, circ_collo, circ_petto, circ_vita, circ_fianchi, circ_braccio, circ_coscia, circ_polpaccio,
                                     massa_grassa, massa_muscolare, massa_ossea, acqua_corporea) 
                VALUES (:uid, :peso, :altezza, :eta, :sesso, :attivita, :tgt_cal, :tgt_c, :tgt_p, :tgt_f, :tgt_sale, :tgt_acqua,
                        :ob, :c_col, :c_pet, :c_vit, :c_fia, :c_bra, :c_cos, :c_pol, :m_gra, :m_mus, :m_oss, :acq) 
                ON CONFLICT (user_id) 
                DO UPDATE SET peso=EXCLUDED.peso, altezza=EXCLUDED.altezza, eta=EXCLUDED.eta, sesso=EXCLUDED.sesso, attivita=EXCLUDED.attivita, 
                              tgt_cal=EXCLUDED.tgt_cal, tgt_c=EXCLUDED.tgt_c, tgt_p=EXCLUDED.tgt_p, tgt_f=EXCLUDED.tgt_f, tgt_sale=EXCLUDED.tgt_sale, tgt_acqua=EXCLUDED.tgt_acqua,
                              obiettivo=EXCLUDED.obiettivo, circ_collo=EXCLUDED.circ_collo, circ_petto=EXCLUDED.circ_petto, circ_vita=EXCLUDED.circ_vita, 
                              circ_fianchi=EXCLUDED.circ_fianchi, circ_braccio=EXCLUDED.circ_braccio, circ_coscia=EXCLUDED.circ_coscia, circ_polpaccio=EXCLUDED.circ_polpaccio,
                              massa_grassa=EXCLUDED.massa_grassa, massa_muscolare=EXCLUDED.massa_muscolare, massa_ossea=EXCLUDED.massa_ossea, acqua_corporea=EXCLUDED.acqua_corporea
            """)
            e.execute(query_prof, {
                "uid": user_id, "peso": peso, "altezza": altezza, "eta": eta, "sesso": sesso, "attivita": attivita, 
                "tgt_cal": tgt_cal, "tgt_c": tgt_c, "tgt_p": tgt_p, "tgt_f": tgt_f, "tgt_sale": tgt_sale, "tgt_acqua": tgt_acqua, "ob": obiettivo,
                "c_col": c_col, "c_pet": c_pet, "c_vit": c_vit, "c_fia": c_fia, "c_bra": c_bra, "c_cos": c_cos, "c_pol": c_pol,
                "m_gra": m_grassa, "m_mus": m_musc, "m_oss": m_ossea, "acq": acqua
            })
            
            query_storico = text("""
                INSERT INTO storico_profilo (user_id, data, peso, tgt_cal, tgt_c, tgt_p, tgt_f, tgt_sale, tgt_acqua,
                                             obiettivo, circ_collo, circ_petto, circ_vita, circ_fianchi, circ_braccio, circ_coscia, circ_polpaccio,
                                             massa_grassa, massa_muscolare, massa_ossea, acqua_corporea)
                VALUES (:uid, :data, :peso, :tgt_cal, :tgt_c, :tgt_p, :tgt_f, :tgt_sale, :tgt_acqua,
                        :ob, :c_col, :c_pet, :c_vit, :c_fia, :c_bra, :c_cos, :c_pol, :m_gra, :m_mus, :m_oss, :acq)
                ON CONFLICT (user_id, data) 
                DO UPDATE SET peso=EXCLUDED.peso, tgt_cal=EXCLUDED.tgt_cal, tgt_c=EXCLUDED.tgt_c, tgt_p=EXCLUDED.tgt_p, tgt_f=EXCLUDED.tgt_f, tgt_sale=EXCLUDED.tgt_sale, tgt_acqua=EXCLUDED.tgt_acqua,
                              obiettivo=EXCLUDED.obiettivo, circ_collo=EXCLUDED.circ_collo, circ_petto=EXCLUDED.circ_petto, circ_vita=EXCLUDED.circ_vita, 
                              circ_fianchi=EXCLUDED.circ_fianchi, circ_braccio=EXCLUDED.circ_braccio, circ_coscia=EXCLUDED.circ_coscia, circ_polpaccio=EXCLUDED.circ_polpaccio,
                              massa_grassa=EXCLUDED.massa_grassa, massa_muscolare=EXCLUDED.massa_muscolare, massa_ossea=EXCLUDED.massa_ossea, acqua_corporea=EXCLUDED.acqua_corporea
            """)
            e.execute(query_storico, {
                "uid": user_id, "data": str(data_pesata), "peso": peso, "tgt_cal": tgt_cal, "tgt_c": tgt_c, "tgt_p": tgt_p, "tgt_f": tgt_f, "tgt_sale": tgt_sale, "tgt_acqua": tgt_acqua,
                "ob": obiettivo, "c_col": c_col, "c_pet": c_pet, "c_vit": c_vit, "c_fia": c_fia, "c_bra": c_bra, "c_cos": c_cos, "c_pol": c_pol,
                "m_gra": m_grassa, "m_mus": m_musc, "m_oss": m_ossea, "acq": acqua
            })
        st.cache_data.clear()
        return True
    except Exception as ex: 
        st.error(f"🚨 ERRORE SQL PROFILO: {ex}")
        return False

def get_storico_profilo(user_id):
    conn = get_conn()
    try:
        query = """
            SELECT data, peso, tgt_cal, tgt_c, tgt_p, tgt_f, tgt_sale, tgt_acqua, obiettivo, 
                   circ_collo, circ_petto, circ_vita, circ_fianchi, circ_braccio, circ_coscia, circ_polpaccio,
                   massa_grassa, massa_muscolare, massa_ossea, acqua_corporea
            FROM storico_profilo WHERE LOWER(user_id) = LOWER(:uid) ORDER BY data ASC
        """
        df = conn.query(query, params={"uid": user_id}, ttl=0)
        if not df.empty: df.columns = [c.lower() for c in df.columns]
        return df
    except: return pd.DataFrame()
