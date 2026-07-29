import io
import json
import os
import random
import colorsys
from collections import Counter
from datetime import datetime
from PIL import Image
from rembg import new_session, remove
import requests
import streamlit as st

# Setup cartelle e database locale
ARMADIO_DIR = "armadio"
DATA_FILE = "armadio.json"
os.makedirs(ARMADIO_DIR, exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


def carica_armadio():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def salva_armadio(armadio):
    with open(DATA_FILE, "w") as f:
        json.dump(armadio, f, indent=4)


def rileva_colore(image_pil):
    """Analizza il colore reale (Hue) ignorando le ombre e la luminosità"""
    img = image_pil.copy()
    img.thumbnail((120, 120))
    img = img.convert("RGBA")
    pixels = list(img.getdata())

    voti_colori = []

    for p in pixels:
        if p[3] < 128:
            continue

        r, g, b = p[0] / 255.0, p[1] / 255.0, p[2] / 255.0
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        h_deg = h * 360

        if v < 0.18:
            colore = "Nero"
        elif s < 0.15 and v > 0.82:
            colore = "Bianco"
        elif s < 0.15:
            colore = "Grigio"
        else:
            if h_deg < 15 or h_deg >= 345:
                colore = "Rosso" if v > 0.4 else "Bordeaux"
            elif 15 <= h_deg < 45:
                colore = "Arancione" if s > 0.4 else "Marrone"
            elif 45 <= h_deg < 70:
                colore = "Giallo"
            elif 70 <= h_deg < 160:
                colore = "Verde"
            elif 160 <= h_deg < 260:
                colore = "Blu / Azzurro"
            elif 260 <= h_deg < 310:
                colore = "Viola"
            else:
                colore = "Rosa"

        voti_colori.append(colore)

    if not voti_colori:
        return "Multicolore"

    conteggio = Counter(voti_colori)
    return conteggio.most_common(1)[0][0]


def salva_capo(nome, categoria, stagione, colore, image_bytes):
    filename = f"capo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(ARMADIO_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(image_bytes)

    armadio = carica_armadio()
    armadio.append(
        {
            "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "nome": nome,
            "categoria": categoria,
            "stagione": stagione,
            "colore": colore,
            "immagine": filepath,
        }
    )
    salva_armadio(armadio)


def elimina_capo(capo_id, filepath):
    """Elimina il capo dal database e rimuove l'immagine dalla cartella"""
    armadio = carica_armadio()
    armadio_aggiornato = [c for c in armadio if c["id"] != capo_id]
    salva_armadio(armadio_aggiornato)

    if os.path.exists(filepath):
        os.remove(filepath)


def ottieni_meteo(citta):
    """Recupera la temperatura attuale da Open-Meteo in base alla città"""
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={citta}&count=1&language=it&format=json"
        geo_res = requests.get(geo_url, timeout=5).json()

        if not geo_res.get("results"):
            return None, "Città non trovata."

        lat = geo_res["results"][0]["latitude"]
        lon = geo_res["results"][0]["longitude"]
        nome_citta = geo_res["results"][0]["name"]

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        w_res = requests.get(weather_url, timeout=5).json()

        current = w_res["current_weather"]
        temp = current["temperature"]

        # Determina la stagione in base ai gradi
        if temp < 13:
            stagione = "Inverno"
            emoji = "❄️"
        elif 13 <= temp <= 22:
            stagione = "Mezza Stagione"
            emoji = "🍂"
        else:
            stagione = "Estate"
            emoji = "☀️"

        return {
            "citta": nome_citta,
            "temp": temp,
            "stagione": stagione,
            "emoji": emoji,
        }, None
    except Exception as e:
        return None, f"Errore meteo: {e}"


# --- INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="Wardrobe AI", page_icon="👔", layout="wide")
st.title("👔 Wardrobe AI - Il tuo Armadio Intelligente")

tab1, tab2, tab3 = st.tabs(
    ["✨ Scontorna & Aggiungi", "🖼️ Il Mio Armadio", "🎲 Generatore Outfit"]
)

# --- TAB 1 ---
with tab1:
    tipo_foto = st.radio(
        "Tipo di foto caricata:",
        [
            "👤 Foto indossata da un Modello (Rimuovi volto/corpo e isola solo il vestito)",
            "🧥 Foto su Gruccia / Sfondo semplice (Rimuovi solo lo sfondo)",
        ],
    )

    uploaded_file = st.file_uploader(
        "Trascina qui la foto oppure clicca per sceglierla...",
        type=["jpg", "jpeg", "png"],
    )

    if uploaded_file is not None:
        input_image = Image.open(uploaded_file)
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Foto Originale")
            st.image(input_image, use_container_width=True)

        img_byte_arr = io.BytesIO()
        input_image.save(img_byte_arr, format="PNG")

        with st.spinner("L'IA sta elaborando l'immagine..."):
            if "Modello" in tipo_foto:
                session = new_session("u2net_cloth_seg")
            else:
                session = new_session("u2net")

            output_bytes = remove(img_byte_arr.getvalue(), session=session)
            output_image = Image.open(io.BytesIO(output_bytes))

        with col2:
            st.subheader("Risultato Pulito")
            st.image(output_image, use_container_width=True)

        colore_rilevato = rileva_colore(output_image)

        st.divider()
        st.subheader("📝 Dettagli Capo d'Abbigliamento")

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            nome_capo = st.text_input("Nome del Capo", value="Nuovo Capo")
        with col_b:
            cat_capo = st.selectbox(
                "Categoria",
                [
                    "Maglietta / T-Shirt",
                    "Camicia",
                    "Maglione / Felpa",
                    "Pantaloni",
                    "Giacca / Cappotto",
                    "Scarpe",
                    "Accessorio",
                ],
            )
        with col_c:
            stagione_capo = st.selectbox(
                "Stagione",
                ["Tutto l'anno", "Estate", "Inverno", "Mezza Stagione"],
            )

        lista_colori = [
            "Nero",
            "Bianco",
            "Grigio",
            "Rosso",
            "Blu / Azzurro",
            "Verde",
            "Giallo",
            "Arancione",
            "Viola",
            "Marrone",
            "Bordeaux",
            "Rosa",
            "Multicolore",
        ]

        idx_colore = (
            lista_colori.index(colore_rilevato)
            if colore_rilevato in lista_colori
            else 0
        )

        with col_d:
            colore_capo = st.selectbox(
                "Colore (Rilevato da AI 🎨)", lista_colori, index=idx_colore
            )

        if st.button("💾 Salva nell'Armadio", type="primary"):
            salva_capo(
                nome_capo, cat_capo, stagione_capo, colore_capo, output_bytes
            )
            st.success(
                f"✅ '{nome_capo}' ({colore_capo}) salvato nell'armadio!"
            )
            st.balloons()

# --- TAB 2 ---
with tab2:
    st.header("🖼️ La tua collezione")
    capi_salvati = carica_armadio()

    if not capi_salvati:
        st.info(
            "Il tuo armadio è ancora vuoto! Aggiungi dei capi nella prima scheda."
        )
    else:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            search_query = st.text_input(
                "🔍 Cerca per nome...", placeholder="es. Felpa"
            )
        with col_f2:
            cat_filter = st.selectbox(
                "📁 Categoria",
                ["Tutte"]
                + sorted(
                    list(
                        set(
                            c.get("categoria", "")
                            for c in capi_salvati
                            if c.get("categoria")
                        )
                    )
                ),
            )
        with col_f3:
            stag_filter = st.selectbox(
                "🗓️ Stagione",
                ["Tutte"]
                + sorted(
                    list(
                        set(
                            c.get("stagione", "")
                            for c in capi_salvati
                            if c.get("stagione")
                        )
                    )
                ),
            )

        capi_filtrati = capi_salvati
        if search_query:
            capi_filtrati = [
                c
                for c in capi_filtrati
                if search_query.lower() in c.get("nome", "").lower()
            ]
        if cat_filter != "Tutte":
            capi_filtrati = [
                c for c in capi_filtrati if c.get("categoria") == cat_filter
            ]
        if stag_filter != "Tutte":
            capi_filtrati = [
                c for c in capi_filtrati if c.get("stagione") == stag_filter
            ]

        st.caption(
            f"Visualizzando **{len(capi_filtrati)}** di {len(capi_salvati)} capi salvati"
        )
        st.divider()

        cols = st.columns(4)
        for i, capo in enumerate(capi_filtrati):
            with cols[i % 4]:
                if os.path.exists(capo["immagine"]):
                    st.image(
                        capo["immagine"],
                        caption=f"{capo['nome']} ({capo['categoria']})",
                        use_container_width=True,
                    )
                    st.caption(
                        f"🎨 **{capo.get('colore', 'N/D')}** | 🗓️ {capo.get('stagione', '')}"
                    )

                    if st.button("🗑️ Elimina", key=f"del_{capo['id']}"):
                        elimina_capo(capo["id"], capo["immagine"])
                        st.rerun()

# --- TAB 3: METEO & OUTFIT ---
with tab3:
    st.header("🎲 Stylist AI - Outfit Intelligente in base al Meteo")

    capi_salvati = carica_armadio()

    if len(capi_salvati) < 2:
        st.warning("Carica almeno 2-3 capi diversi per generare un outfit!")
    else:
        st.subheader("🌤️ Meteo in Tempo Reale")
        col_m1, col_m2 = st.columns([2, 1])

        with col_m1:
            citta = st.text_input("Inserisci la tua città:", value="Roma")

        data_meteo, errore = ottieni_meteo(citta)

        if errore:
            st.error(f"Impossibile recuperare il meteo per '{citta}'.")
            stagione_target = "Tutto l'anno"
        else:
            with col_m2:
                st.metric(
                    label=f"Meteo a {data_meteo['citta']}",
                    value=f"{data_meteo['temp']} °C",
                    delta=f"{data_meteo['emoji']} Consigliato: {data_meteo['stagione']}",
                )
            stagione_target = data_meteo["stagione"]

        st.divider()

        # Selezione Stagione (Auto-selezionata dal Meteo ma modificabile dall'utente)
        lista_stagioni = ["Inverno", "Mezza Stagione", "Estate", "Tutto l'anno"]
        idx_default = (
            lista_stagioni.index(stagione_target)
            if stagione_target in lista_stagioni
            else 3
        )

        stagione_scelta = st.selectbox(
            "Filtra la stagione dell'outfit:",
            lista_stagioni,
            index=idx_default,
        )

        if st.button("✨ Genera Outfit Adatto", type="primary"):
            pool = [
                c
                for c in capi_salvati
                if c.get("stagione") == stagione_scelta
                or c.get("stagione") == "Tutto l'anno"
            ]

            tops = [
                c
                for c in pool
                if c.get("categoria")
                in ["Maglietta / T-Shirt", "Camicia", "Maglione / Felpa"]
            ]
            bottoms = [
                c for c in pool if c.get("categoria") == "Pantaloni"
            ]
            shoes = [c for c in pool if c.get("categoria") == "Scarpe"]
            jackets = [
                c for c in pool if c.get("categoria") == "Giacca / Cappotto"
            ]

            top_scelto = random.choice(tops) if tops else None
            bottom_scelto = random.choice(bottoms) if bottoms else None
            shoes_scelto = random.choice(shoes) if shoes else None
            jacket_scelto = random.choice(jackets) if jackets else None

            if not (top_scelto or bottom_scelto or shoes_scelto):
                st.error(
                    f"Nessun capo trovato nel tuo armadio per la stagione '{stagione_scelta}'!"
                )
            else:
                st.success(
                    f"🎉 Outfit generato perfetto per {citta} ({stagione_scelta})!"
                )
                st.divider()

                outfit_cols = st.columns(4)
                if top_scelto:
                    with outfit_cols[0]:
                        st.subheader("👕 Sopra")
                        st.image(
                            top_scelto["immagine"],
                            caption=f"{top_scelto['nome']}",
                            use_container_width=True,
                        )
                if bottom_scelto:
                    with outfit_cols[1]:
                        st.subheader("👖 Sotto")
                        st.image(
                            bottom_scelto["immagine"],
                            caption=f"{bottom_scelto['nome']}",
                            use_container_width=True,
                        )
                if jacket_scelto:
                    with outfit_cols[2]:
                        st.subheader("🧥 Giacca")
                        st.image(
                            jacket_scelto["immagine"],
                            caption=f"{jacket_scelto['nome']}",
                            use_container_width=True,
                        )
                if shoes_scelto:
                    with outfit_cols[3]:
                        st.subheader("👟 Scarpe")
                        st.image(
                            shoes_scelto["immagine"],
                            caption=f"{shoes_scelto['nome']}",
                            use_container_width=True,
                        )