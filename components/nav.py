import streamlit as st

def render_top_nav(current_page_name):
    """
    Renderizza una barra di navigazione superiore ultraleggera 
    con pulsante Home e percorso visivo (Breadcrumb).
    """
    col_home, col_path = st.columns([1.2, 4])
    
    with col_home:
        # Pulsante rapido per tornare alla dashboard principale
        if st.button("🏠 Home", use_container_width=True, key=f"nav_home_{current_page_name}"):
            st.switch_page("NutriLab24.py")
            
    with col_path:
        # Percorso di navigazione visivo compatto
        st.markdown(
            f"<div style='padding-top: 10px; font-size: 13px; color: #666; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>"
            f"📍 Home > <b>{current_page_name}</b>"
            f"</div>", 
            unsafe_allow_html=True
        )
    
    # Sottile linea di separazione pulita
    st.markdown("<hr style='margin: 0px 0px 15px 0px; border-top: 1px solid #e0e0e0;'>", unsafe_allow_html=True)
