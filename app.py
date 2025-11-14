import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Cartera APP", layout="wide")

st.title("📊 Procesador de Cartera – App en Streamlit")
st.write("Carga un archivo Excel con las hojas: **PUC**, **CARTERA** y **Quitar**.")

# --- CARGA DE ARCHIVO ---
uploaded_file = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if uploaded_file is not None:

    # Leer hojas del archivo
    puc_df = pd.read_excel(uploaded_file, sheet_name='PUC')
    Cartera_df = pd.read_excel(uploaded_file, sheet_name='CARTERA')
    Quitar_df = pd.read_excel(uploaded_file, sheet_name='Quitar')

    # --- LIMPIEZA Y PROCESAMIENTO ---

    columnas_eliminar = [
        'agru_bloq', 'interior', 'apto', 'nombre', 'descuento', 'promedio',
        'ult_fpago', 'ult_vpago', 'ult_rpago', 'ult_fpag2', 'ult_vpag2',
        'ult_rpag2', 'Hoja'
    ]

    Cartera_df = Cartera_df.drop(columnas_eliminar, axis=1, errors='ignore')

    # Multiplicar anticipos por -1
    if 'anticipos' in Cartera_df:
        Cartera_df['anticipos'] = Cartera_df['anticipos'] * -1

    # Pivotear
    pivoted_df = Cartera_df.melt(id_vars=['codigo'], var_name='Columna', value_name='Valor')
    pivoted_df['Columna'] = pivoted_df['Columna'].str.replace('c_', '', regex=False)
    pivoted_df['Valor'] = pivoted_df['Valor'].fillna(0)

    pivoted_df['Columna'] = pivoted_df['Columna'].astype(str)
    puc_df['codigo_cuenta'] = puc_df['codigo_cuenta'].astype(str)

    # Merge
    merged_df = pd.merge(
        pivoted_df,
        puc_df[['codigo_cuenta', 'Homologo APP']],
        left_on='Columna',
        right_on='codigo_cuenta',
        how='left'
    )

    pivoted_df = merged_df
    pivoted_df = pivoted_df[pivoted_df['codigo_cuenta'].notna()]
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

    # Reindexar con columnas esperadas si existen
    columnas_existentes = [c for c in orden_columnas if c in cartera_app.columns]
    cartera_app = cartera_app.reindex(columns=columnas_existentes)

    # Reglas de negocio
    if 'TOTAL A PAGAR' in cartera_app and 'SALDO A FAVOR' in cartera_app:
        cartera_app['TOTAL A PAGAR'] = cartera_app.apply(
            lambda row: 0 if row['SALDO A FAVOR'] < 0 else row['TOTAL A PAGAR'],
            axis=1
        )

        cartera_app['SALDO A FAVOR'] = cartera_app['SALDO A FAVOR'].apply(
            lambda x: int(abs(x)) if x != 0 else x
        )

    columnas_a_convertir = [
        'ADMINISTRACION', 'INTERESES', 'PARQUEADEROS', 'SANCIONES',
        'EXTRAORDINARIA', 'ABOGADOS', 'OTROS',
        'TOTAL A PAGAR', 'SALDO A FAVOR'
    ]

    for col in columnas_a_convertir:
        if col in cartera_app:
            cartera_app[col] = cartera_app[col].astype(int)

    # Quitar códigos
    if 'codigo_retirar' in Quitar_df:
        cartera_app = cartera_app[~cartera_app['codigo'].isin(Quitar_df['codigo_retirar'])]

    st.success("Archivo procesado correctamente ✔")
    st.subheader("Resultado final")
    st.dataframe(cartera_app, use_container_width=True)

    # --- DESCARGAS ---
    st.subheader("Descargar resultados")

    # CSV
    csv = cartera_app.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇ Descargar CSV",
        data=csv,
        file_name="cartera_app.csv",
        mime="text/csv"
    )

    # XLSX
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        cartera_app.to_excel(writer, index=False, sheet_name='Cartera App')

    st.download_button(
        label="⬇ Descargar Excel (XLSX)",
        data=buffer.getvalue(),
        file_name="cartera_app.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("📥 Por favor sube un archivo Excel para iniciar el procesamiento.")

