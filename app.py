import streamlit as st
import pandas as pd
import unicodedata
from io import BytesIO
import matplotlib.pyplot as plt

# Función para normalizar nombres
def normalizar_nombre(nombre):
    if pd.isna(nombre):
        return ""
    nombre = str(nombre).strip().lower()
    nombre = unicodedata.normalize('NFD', nombre).encode('ascii', 'ignore').decode('utf-8')
    return nombre

st.set_page_config(page_title="Consolidación SIMCE", layout="wide")
st.title("📊 Consolidación y Análisis de Puntajes SIMCE")

# Subida de archivos
st.header("🔹 Paso 1: Cargar archivos")
archivo_1 = st.file_uploader("📘 Archivo 1 (Grupos y ensayos anteriores)", type=["xlsx"])
archivos_2 = st.file_uploader("📗 Archivos 2 (uno o más cursos del último ensayo)", type=["xlsx"], accept_multiple_files=True)

if archivo_1 and archivos_2:
    xls1 = pd.ExcelFile(archivo_1)
    ejemplo_hoja = xls1.parse(xls1.sheet_names[0])
    columnas = ejemplo_hoja.columns
    ensayos_previos = [col for col in columnas if isinstance(col, str) and "ensayo" in col.lower()]
    num_ensayo_nuevo = len(ensayos_previos) + 1
    nombre_columna_nueva = f"Ensayo {num_ensayo_nuevo}"

    df_ensayo = pd.DataFrame()
    for archivo in archivos_2:
        xls2 = pd.ExcelFile(archivo)
        for sheet in xls2.sheet_names:
            df_temp = xls2.parse(sheet)
            df_ensayo = pd.concat([df_ensayo, df_temp], ignore_index=True)

    df_ensayo["Nombre Normalizado"] = df_ensayo["Nombre"].apply(normalizar_nombre)
    duplicados_ensayo2 = df_ensayo["Nombre Normalizado"].duplicated(keep=False)
    duplicados = df_ensayo[duplicados_ensayo2]
    nombre_a_puntaje = df_ensayo.set_index("Nombre Normalizado")["Puntaje"].to_dict()

    total_estudiantes = 0
    total_con_coincidencia = 0
    total_sin_coincidencia = 0
    lista_no_encontrados = set()
    consolidado = BytesIO()
    writer = pd.ExcelWriter(consolidado, engine='xlsxwriter')
    historial = []

    for hoja in xls1.sheet_names:
        df = xls1.parse(hoja)
        col_nombre = None
        for col in df.columns:
            if df[col].astype(str).str.lower().str.contains("apellido|nombre").any():
                col_nombre = col
                break
        if col_nombre is None:
            col_nombre = df.columns[1]

        nuevos_puntajes = []
        for nombre in df[col_nombre]:
            total_estudiantes += 1
            nombre_norm = normalizar_nombre(nombre)
            puntaje = nombre_a_puntaje.get(nombre_norm, None)
            if puntaje is not None:
                total_con_coincidencia += 1
            else:
                total_sin_coincidencia += 1
                lista_no_encontrados.add(nombre)
            nuevos_puntajes.append(puntaje)

            if ensayos_previos and nombre_norm in nombre_a_puntaje:
                puntajes_anteriores = df.loc[df[col_nombre] == nombre, ensayos_previos].values.flatten().tolist()
                historial.append({
                    "Nombre": nombre,
                    "Grupo": hoja,
                    "Puntajes": puntajes_anteriores + [puntaje]
                })

        df[nombre_columna_nueva] = nuevos_puntajes
        df.to_excel(writer, sheet_name=hoja, index=False)

    writer.close()
    consolidado.seek(0)

    st.header("📌 Resumen del análisis")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("👥 Total estudiantes", total_estudiantes)
        st.metric("✅ Coincidencias", total_con_coincidencia)
        st.metric("❌ Sin coincidencia", total_sin_coincidencia)
    with col2:
        if not duplicados.empty:
            st.subheader("⚠️ Nombres duplicados detectados (archivo 2)")
            st.dataframe(duplicados[["Nombre", "Puntaje"]])

    if lista_no_encontrados:
        st.subheader("🧾 Nombres sin coincidencia")
        df_sin_match = pd.DataFrame({"Nombre no encontrado": list(lista_no_encontrados)})
        st.dataframe(df_sin_match)
        buffer_no_match = BytesIO()
        df_sin_match.to_excel(buffer_no_match, index=False)
        buffer_no_match.seek(0)
        st.download_button("📥 Descargar nombres sin coincidencia", buffer_no_match, file_name="sin_coincidencia.xlsx")

    st.subheader("📤 Exportar archivo consolidado")
    st.download_button("📥 Descargar consolidado.xlsx", data=consolidado, file_name="consolidado.xlsx")

    if historial:
        st.header("📈 Evolución individual de puntajes")
        historial_df = pd.DataFrame(historial)
        nombres_unicos = historial_df["Nombre"].unique()
        seleccionado = st.selectbox("Selecciona un estudiante para ver su evolución:", nombres_unicos)
        data_seleccionada = historial_df[historial_df["Nombre"] == seleccionado].iloc[0]
        puntajes = data_seleccionada["Puntajes"]
        plt.figure(figsize=(8, 4))
        plt.plot(range(1, len(puntajes)+1), puntajes, marker='o')
        plt.xticks(range(1, len(puntajes)+1), [f"Ensayo {i}" for i in range(1, len(puntajes)+1)])
        plt.title(f"Evolución de puntajes - {seleccionado}")
        plt.xlabel("Ensayo")
        plt.ylabel("Puntaje")
        plt.grid(True)
        st.pyplot(plt)
