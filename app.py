import streamlit as st
import pandas as pd
import io
import logging


# --------------------- CONFIGURACIÓN INICIAL ---------------------
st.set_page_config(page_title="Cartera APP", layout="wide")

st.markdown("""
<h1 style='text-align: center;'>📊 Cartera App – Procesador de Archivos</h1>
<p style='text-align: center; font-size: 18px;'>Sube un archivo Excel y genera la cartera final con cálculos automáticos.</p>
""", unsafe_allow_html=True)

# Configurar logs visibles
log_messages = []


def log(msg, level="info"):
    """Registra logs visibles para el usuario."""
    log_messages.append((level, msg))
    if level == "error":
        logging.error(msg)
    elif level == "warning":
        logging.warning(msg)
    else:
        logging.info(msg)


# --------------------------- BARRA LATERAL ------------------------
with st.sidebar:
    st.header("📝 Registro del proceso")
    st.write("Aquí verás los logs del proceso paso a paso.")


# -------------------------- CARGA DEL ARCHIVO ---------------------
st.subheader("📥 Cargar archivo")
uploaded_file = st.file_uploader("Selecciona un archivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:

    # Mostrar loading
    st.toast("Procesando archivo...", icon="⏳")

    # Leer hojas disponibles
    try:
        excel_obj = pd.ExcelFile(uploaded_file)
        available_sheets = excel_obj.sheet_names
        log(f"Hojas detectadas: {available_sheets}")

    except Exception as e:
        st.error("❌ Error al leer el archivo. Asegúrate de que es un .xlsx válido.")
        log(f"Error leyendo archivo: {str(e)}", "error")
        st.stop()

    # VALIDAR HOJAS NECESARIAS
    required_sheets = ["PUC", "CARTERA", "Quitar"]
    missing = [s for s in required_sheets if s not in available_sheets]

    if missing:
        st.error(f"❌ El archivo está incompleto. Faltan las hojas: {missing}")
        log(f"Hojas faltantes: {missing}", "error")
        st.stop()

    log("Validación de hojas completada ✔")

    # Cargar hojas
    try:
        puc_df = pd.read_excel(uploaded_file, sheet_name='PUC')
        Cartera_df = pd.read_excel(uploaded_file, sheet_name='CARTERA')
        Quitar_df = pd.read_excel(uploaded_file, sheet_name='Quitar')
        log("Hojas cargadas correctamente ✔")

    except Exception as e:
        st.error("❌ Error cargando las hojas del Excel.")
        log(f"Error en lectura de hojas: {str(e)}", "error")
        st.stop()

    # VALIDAR COLUMNAS MÍNIMAS
    required_cartera_cols = ["codigo", "anticipos"]

    for col in required_cartera_cols:
        if col not in Cartera_df.columns:
            st.error(f"❌ La hoja CARTERA no contiene la columna obligatoria: '{col}'")
            log(f"Falta '{col}' en CARTERA", "error")
            st.stop()

    log("Validación de columnas en CARTERA ✔")

    # Validar columna en Quitar
    if "codigo_retirar" not in Quitar_df.columns:
        st.error("❌ La hoja Quitar debe contener la columna 'codigo_retirar'.")
        log("Falta 'codigo_retirar' en Quitar", "error")
        st.stop()

    log("Validación hoja Quitar completada ✔")

    # --------------------- PROCESAMIENTO ---------------------

    st.subheader("🔄 Procesando datos...")

    columnas_eliminar = [
        'agru_bloq', 'interior', 'apto', 'nombre', 'descuento', 'promedio',
        'ult_fpago', 'ult_vpago', 'ult_rpago', 'ult_fpag2', 'ult_vpag2',
        'ult_rpag2', 'Hoja'
    ]
    Cartera_df = Cartera_df.drop(columnas_eliminar, axis=1, errors='ignore')

    # Multiplicar anticipos
    Cartera_df['anticipos'] = Cartera_df['anticipos'] * -1
    log("Se ajustó la columna 'anticipos' ✔")

    # Pivot
    pivoted_df = Cartera_df.melt(
        id_vars=['codigo'],
        var_name='Columna',
        value_name='Valor'
    )
    pivoted_df['Columna'] = pivoted_df['Columna'].str.replace('c_', '', regex=False)
    pivoted_df['Valor'] = pivoted_df['Valor'].fillna(0)

    puc_df['codigo_cuenta'] = puc_df['codigo_cuenta'].astype(str)
    pivoted_df['Columna'] = pivoted_df['Columna'].astype(str)

    merged_df = pd.merge(
        pivoted_df,
        puc_df[['codigo_cuenta', 'Homologo APP']],
        left_on='Columna',
        right_on='codigo_cuenta',
        how='left'
    )

    pivoted_df = merged_df.dropna(subset=['codigo_cuenta'])
    pivoted_df = pivoted_df[pivoted_df['codigo_cuenta'] != ""]

    # Crear tabla final
    cartera_app = pivoted_df.pivot_table(
        index='codigo',
        columns='Homologo APP',
        values='Valor',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    # Orden columnas
    orden_columnas = [
        'codigo', 'ADMINISTRACION', 'INTERESES', 'PARQUEADEROS',
        'SANCIONES', 'EXTRAORDINARIA', 'ABOGADOS', 'OTROS',
        'TOTAL A PAGAR', 'SALDO A FAVOR'
    ]

    cartera_app = cartera_app.reindex(columns=orden_columnas)

    # Reglas de negocio
    if 'TOTAL A PAGAR' in cartera_app:
        cartera_app['TOTAL A PAGAR'] = cartera_app.apply(
            lambda row: 0 if row['SALDO A FAVOR'] < 0 else row['TOTAL A PAGAR'], axis=1
        )

    if 'SALDO A FAVOR' in cartera_app:
        cartera_app['SALDO A FAVOR'] = cartera_app['SALDO A FAVOR'].apply(
            lambda x: int(abs(x)) if x != 0 else x
        )

    # Convertir a enteros
    for col in orden_columnas[1:]:
        if col in cartera_app:
            cartera_app[col] = cartera_app[col].astype(int)

    # Quitar códigos
    cartera_app = cartera_app[~cartera_app['codigo'].isin(Quitar_df['codigo_retirar'])]

    st.success("Proceso completado correctamente ✔")

    # Mostrar tabla
    st.subheader("📄 Resultado final")
    st.dataframe(cartera_app, use_container_width=True)

    # ------------------------ DESCARGAS -------------------------
    st.subheader("⬇ Descargar resultados")

    csv = cartera_app.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Descargar CSV",
        csv,
        "cartera_app.csv",
        "text/csv"
    )

    # XLSX
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        cartera_app.to_excel(writer, sheet_name='Cartera App', index=False)

    st.download_button(
        "📥 Descargar Excel (XLSX)",
        buffer.getvalue(),
        "cartera_app.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# -------------------- MOSTRAR LOGS AL USUARIO --------------------
with st.sidebar:
    for level, msg in log_messages:
        if level == "error":
            st.error("❌ " + msg)
        elif level == "warning":
            st.warning("⚠ " + msg)
        else:
            st.info("ℹ " + msg)

    # ------------------------ GENERAR CARTERA POR TORRE (WORD) -------------------------
    st.subheader("📄 Cartera por Torre")

    st.write("Genera un archivo Word con los morosos agrupados por torre.")

    Fecha_corte_str = st.text_input("Fecha de corte (dd/mm/aaaa):")

    if st.button("📄 Generar Cartera por Torre"):
        from datetime import datetime
        from docx import Document

        # Validar inputs
        if not Fecha_corte_str:
            st.error("⚠ Debes ingresar la fecha de corte.")
            st.stop()

        try:
            Fecha_corte = datetime.strptime(Fecha_corte_str, "%d/%m/%Y").date()
        except:
            st.error("❌ Formato de fecha inválido. Debe ser dd/mm/aaaa.")
            st.stop()

        try:
            # Usar la hoja original CARTERA
            df_cartera_word = pd.read_excel(uploaded_file, sheet_name='CARTERA')

            # Validar columnas
            if "total" not in df_cartera_word.columns or "interior" not in df_cartera_word.columns:
                st.error("❌ La hoja CARTERA no contiene las columnas necesarias: 'total' y 'interior'")
                st.stop()

            # Filtrar morosos
            df_cartera_filtered = df_cartera_word[df_cartera_word["total"] > 1000]

            if df_cartera_filtered.empty:
                st.warning("No hay morosos con total mayor a 1000.")
                st.stop()

            # Crear documento Word
            document = Document()

            unique_towers = df_cartera_filtered["interior"].unique()

            first_tower = True

            for tower in unique_towers:

                if not first_tower:
                    document.add_page_break()
                else:
                    first_tower = False

                df_tower = df_cartera_filtered[df_cartera_filtered["interior"] == tower]

                document.add_heading(f"MOROSOS TORRE {tower}", level=1)
                document.add_paragraph(
                    f"A continuación se relacionan los morosos de la torre {tower} "
                    f"con corte a {Fecha_corte.strftime('%d/%m/%Y')}"
                )

                # Crear tabla
                table = document.add_table(rows=1, cols=2)
                table.style = "Table Grid"

                hdr_cells = table.rows[0].cells
                hdr_cells[0].text = "Código"
                hdr_cells[1].text = "Total"

                for idx, row in df_tower.iterrows():
                    row_cells = table.add_row().cells
                    row_cells[0].text = str(row["codigo"])
                    row_cells[1].text = f"{row['total']:,}"

            # Guardar en memoria
            buffer_word = io.BytesIO()
            document.save(buffer_word)
            buffer_word.seek(0)

            st.success("✔ Archivo Word generado correctamente.")

            st.download_button(
                label="📄 Descargar Word – Cartera por Torre",
                data=buffer_word,
                file_name="Cartera_por_Torre.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        except Exception as e:
            st.error("❌ Error generando el archivo Word.")
            st.write(str(e))





