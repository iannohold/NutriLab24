#!/bin/bash

# Vai nella cartella dove si trova questo script
cd "$(dirname "$0")"

echo "============================================================"
echo "Avvio Nutrilab - Progetta, bilancia e cucina le tue idee ..."
echo "============================================================"

# Assicurati che le librerie necessarie siano installate
python3 -m pip install --upgrade pip > /dev/null 2>&1
python3 -m pip install streamlit pillow > /dev/null 2>&1

# Avvia l'applicazione Streamlit
python3 -m streamlit run NutriLab24.py