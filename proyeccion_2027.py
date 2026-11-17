"""
proyeccion_2027.py - Pestana "Proyeccion 2027" de AEGIS-INTELLECT v2.0

Expedientes de referencia:
  EXP-0014  Proyeccion 2027 por rangos de volatilidad (663 puestos, mediana +3,22 %, sigma 33,79 %)
  VIS-DEC-0026  Protocolo de validacion de campo (288 fichas: 33 ROJO + 255 sin linea base)
  EXP-0031  Resolucion 87 vs 88 - la cabecera del CSV no es un municipio
  VIS-DEC-0019  Cifras medidas del corpus MMV 2023

Fecha de generacion: 2026-11-16
Dependencias: pandas, streamlit  (numpy se usa solo via pandas)

DISENO EN TRES NIVELES
  N1  data/EXP-0014_puestos_volatilidad.csv existe  -> lectura directa (rapido)
  N2  no existe, pero estan los dos MMV en data/    -> recalculo en tiempo real (lento, cacheado)
  N3  no hay nada                                    -> DEUDA_DE_ACCESO, no se inventa

NOTA DE ESQUEMA (correccion al encargo):
  Los dos MMV usan la columna `Total Votos`, NO `Votos`. Verificado en ambos archivos.
  Por eso COLS_VOTOS prueba `Total Votos` primero y `Votos` despues.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------- #
# Constantes auditadas (EXP-0013 / EXP-0014). No se recalculan aqui.
# --------------------------------------------------------------------------- #

MEDIANA = 3.22          # % de variacion mediana 2019->2023
SIGMA = 33.79          # % desviacion estandar transversal
LIM_INF_1 = MEDIANA - SIGMA          # -30.57
LIM_SUP_1 = MEDIANA + SIGMA          # +37.01
LIM_SUP_2 = MEDIANA + 2 * SIGMA      # +70.80

DATA_DIR = Path("data")

# Los dos MMV usan "Total Votos". "Votos" se admite por si cambia la fuente.
COLS_VOTOS = ("Total Votos", "Votos")

# Columnas minimas del corpus MMV (18 en la fuente real).
C_MUN, C_PUE, C_NOM, C_CORP = "Código Municipio", "Código Puesto", "Nombre Puesto", "Nombre Corporación"

ETIQUETAS = {
    "VERDE": "🟢 Dentro de lo típico",
    "AMARILLO": "🟡 Ajuste alto",
    "ROJO": "🔴 Alta volatilidad",
    "SIN_BASE": "📝 Sin línea base",
}

# Reglas de abreviatura verificadas en VIS-DEC-0026 (COL->IE y SED->SEDE con votos casi identicos).
# Se canonicalizan AMBOS lados del par: COL e IE -> IE ; SED y SE -> SEDE.
REGLAS_RENOMBRE = (("SED ", "SEDE "), ("SE ", "SEDE "), ("COL. ", "IE "), ("COL ", "IE "), ("I.E. ", "IE "))


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

def _normalizar(nombre: str) -> str:
    """
    Mayusculas, sin espacios dobles y con las abreviaturas canonicalizadas.

    Las tres reglas se aplican a AMBOS lados del par, que es lo que significa "COL<->IE":
      COL / I.E. -> IE        (mismo establecimiento, distinto prefijo)
      SED        -> SEDE
      SE         -> SEDE
    Se normaliza a una forma comun, no a una preferida: el nombre real no se reescribe.
    """
    n = " " + str(nombre).upper().strip() + " "
    for _ in range(2):  # dos pasadas: "SE " -> "SEDE " es estable en la segunda
        for a, b in REGLAS_RENOMBRE:
            n = n.replace(a, b)
    return " ".join(n.split())


def asignar_bucket(variacion: float) -> str:
    """
    Bucket segun EXP-0014. Particion completa y sin solape:
      VERDE     [mediana - sigma, mediana + sigma]   -> -30,57 % .. +37,01 %
      AMARILLO  (mediana + sigma, mediana + 2*sigma] -> +37,01 % .. +70,80 %
      ROJO      < mediana - sigma  o  > mediana + 2*sigma
    """
    if variacion < LIM_INF_1 or variacion > LIM_SUP_2:
        return "ROJO"
    if variacion > LIM_SUP_1:
        return "AMARILLO"
    return "VERDE"


def _columna_votos(df: pd.DataFrame) -> str | None:
    for c in COLS_VOTOS:
        if c in df.columns:
            return c
    return None


# --------------------------------------------------------------------------- #
# N1 - lectura del CSV de EXP-0014
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner=False)
def cargar_exp0014() -> pd.DataFrame | None:
    ruta = DATA_DIR / "EXP-0014_puestos_volatilidad.csv"
    if not ruta.exists():
        return None
    try:
        df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception as exc:
        st.error(f"No se pudo leer `{ruta.name}`: {exc}")
        return None

    # El archivo real usa minusculas; se admite el esquema descrito en el encargo.
    mapa = {"Municipio": "municipio", "Puesto": "puesto", "Bucket": "bucket",
            "Variacion_2019_2023": "var_pct", "Votos_2019": "v2019", "Votos_2023": "v2023"}
    df = df.rename(columns={k: v for k, v in mapa.items() if k in df.columns})

    for c in ("v2019", "v2023", "var_pct", "rango_inf_2027", "rango_sup_2027"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "bucket" not in df.columns and "var_pct" in df.columns:
        df["bucket"] = df["var_pct"].map(asignar_bucket)
    df["origen"] = "EXP-0014"
    return df


# --------------------------------------------------------------------------- #
# N2 - recalculo desde los MMV crudos
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner="Recalculando buckets desde los MMV (puede tardar ~2 min)...")
def recalcular_desde_mmv() -> pd.DataFrame | None:
    """
    Recalcula la variacion 2019->2023 por puesto para GOBERNADOR.

    Clave compuesta: Codigo Municipio + Codigo Puesto + Nombre Puesto.
    Se descartan los codigos de municipio NO numericos: es la cabecera del CSV
    que en EXP-0031 se contaba como un municipio 88 inexistente.
    """
    f19, f23 = DATA_DIR / "MMV_2019_27_SANTANDER.csv", DATA_DIR / "MMV_2023_27_SANTANDER.csv"
    if not (f19.exists() and f23.exists()):
        return None

    def carga(ruta: Path) -> dict[tuple[str, str, str], int] | None:
        df = pd.read_csv(ruta, encoding="utf-8-sig", low_memory=False, dtype=str)
        col_v = _columna_votos(df)
        if col_v is None or not {C_MUN, C_PUE, C_NOM, C_CORP}.issubset(df.columns):
            st.error(f"`{ruta.name}` no tiene el esquema esperado (Total Votos / Codigo / Puesto).")
            return None
        df = df[df[C_CORP].str.upper().str.strip() == "GOBERNADOR"]
        # EXP-0031: un codigo municipal no numerico es la cabecera, no un municipio.
        df = df[df[C_MUN].str.strip().str.isdigit()]
        df["_v"] = pd.to_numeric(df[col_v], errors="coerce").fillna(0)
        return df.groupby([C_MUN, C_PUE, C_NOM])["_v"].sum().to_dict()

    d19, d23 = carga(f19), carga(f23)
    if d19 is None or d23 is None:
        return None

    filas = []
    for k in set(d19) & set(d23):
        a, b = d19[k], d23[k]
        var = (b - a) / max(a, 1) * 100.0
        filas.append({"municipio": k[0], "puesto_cod": k[1], "puesto": k[2],
                      "v2019": a, "v2023": b, "var_pct": round(var, 2),
                      "bucket": asignar_bucket(var)})
    df = pd.DataFrame(filas)
    k = df["var_pct"]
    df["rango_inf_2027"] = (df["v2023"] * (1 + (MEDIANA - SIGMA) / 100)).round(0)
    df["rango_sup_2027"] = (df["v2023"] * (1 + (MEDIANA + SIGMA) / 100)).round(0)
    df.loc[df["bucket"] == "ROJO", "rango_inf_2027"] = (
        df["v2023"] * (1 + (MEDIANA - 2 * SIGMA) / 100)).round(0)
    df.loc[df["bucket"] == "ROJO", "rango_sup_2027"] = (
        df["v2023"] * (1 + (MEDIANA + 2 * SIGMA) / 100)).round(0)
    df["origen"] = "recalculado"
    _ = k  # evita un warning de variable sin uso en linters estrictos
    return df


# --------------------------------------------------------------------------- #
# Sin linea base (255) + emparejador de renombres
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner=False)
def cargar_sin_base() -> pd.DataFrame | None:
    """Lee las 288 fichas de VIS-DEC-0026 y aisla los 255 puestos sin linea base."""
    ruta = DATA_DIR / "PROTOCOLO_CAMPO_puestos.csv"
    if not ruta.exists():
        return None
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if "grupo" not in df.columns:
        return None
    return df[df["grupo"].str.startswith("SIN_BASE")].copy()


def emparejar_renombres(sin_base: pd.DataFrame) -> pd.DataFrame:
    """
    Cruza los puestos SIN_BASE_2019 contra SIN_BASE_2023 por firma normalizada.

    No empata: PROPONE. La confirmacion es una foto de la placa (VIS-DEC-0026).
    """
    if sin_base.empty:
        return pd.DataFrame()
    a = sin_base[sin_base["grupo"] == "SIN_BASE_2019"].copy()
    b = sin_base[sin_base["grupo"] == "SIN_BASE_2023"].copy()
    if a.empty or b.empty:
        return pd.DataFrame()

    a["v19"] = pd.to_numeric(a.get("v2019"), errors="coerce").fillna(0)
    b["v23"] = pd.to_numeric(b.get("v2023"), errors="coerce").fillna(0)
    a["firma"] = a["puesto"].map(_normalizar)
    b["firma"] = b["puesto"].map(_normalizar)

    pares = a.merge(b, on=["municipio", "firma"], suffixes=("_19", "_23"))
    if pares.empty:
        return pares
    pares["dif_votos"] = (pares["v23"] - pares["v19"]).abs()
    pares["dif_pct"] = (100 * pares["dif_votos"] / pares["v19"].clip(lower=1)).round(1)
    pares["confianza"] = pares["dif_pct"].map(
        lambda x: "ALTA" if x <= 5 else ("MEDIA" if x <= 20 else "BAJA")
    )
    return pares.sort_values("dif_pct")[
        ["municipio", "puesto_19", "v19", "puesto_23", "v23", "dif_votos", "dif_pct", "confianza"]
    ]


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #

def render_proyeccion_2027() -> None:
    """Pestana completa. Autocontenida: no depende de nada externo a este modulo."""
    st.subheader("Proyección 2027 · rangos, nunca un número")
    st.caption(
        f"EXP-0014 · mediana {MEDIANA:+.2f} % · σ {SIGMA:.2f} % · "
        f"rango = Votos_2023 × (1 + (mediana ± k·σ)) · k=1 típico · k=2 volátil"
    )

    # ---- Carga con fallback -------------------------------------------------
    df = cargar_exp0014()
    if df is not None:
        st.success("Fuente: `data/EXP-0014_puestos_volatilidad.csv` (lectura directa).")
    else:
        st.warning(
            "No está `data/EXP-0014_puestos_volatilidad.csv`. "
            "Se intenta recalcular desde los MMV crudos de `data/`."
        )
        df = recalcular_desde_mmv()
        if df is not None:
            st.success("Buckets recalculados desde los MMV en tiempo real (cacheados).")

    sin_base = cargar_sin_base()

    if df is None and sin_base is None:
        st.error(
            "**DEUDA_DE_ACCESO** · No hay datos para esta pestaña.\n\n"
            "Falta `data/EXP-0014_puestos_volatilidad.csv` y también los dos MMV "
            "(`MMV_2019_27_SANTANDER.csv`, `MMV_2023_27_SANTANDER.csv`) en `data/`. "
            "**No se estima nada**: los rangos exigen una varianza medida, no supuesta."
        )
        return

    # ---- Filtros globales ---------------------------------------------------
    c1, c2 = st.columns([1, 2])
    with c1:
        munis = ["TODOS"] + (sorted(df["municipio"].dropna().unique()) if df is not None else [])
        muni = st.selectbox("Municipio", munis, key="proy_muni")
    with c2:
        disponibles = []
        if df is not None:
            disponibles += [ETIQUETAS[b] for b in ("VERDE", "AMARILLO", "ROJO") if b in set(df["bucket"])]
        if sin_base is not None:
            disponibles.append(ETIQUETAS["SIN_BASE"])
        sel = st.multiselect("Bucket", disponibles, default=disponibles, key="proy_bucket")

    # ---- Tabla filtrada -----------------------------------------------------
    partes = []
    if df is not None:
        d = df if muni == "TODOS" else df[df["municipio"] == muni]
        d = d.copy()
        d["bucket_etq"] = d["bucket"].map(ETIQUETAS).fillna(d["bucket"])
        d = d[d["bucket_etq"].isin(sel)]
        partes.append(d)
    if sin_base is not None and ETIQUETAS["SIN_BASE"] in sel:
        s = sin_base if muni == "TODOS" else sin_base[sin_base["municipio"] == muni]
        s = s.copy()
        s["bucket_etq"] = ETIQUETAS["SIN_BASE"]
        s["var_pct"] = pd.NA
        partes.append(s)

    vista = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    if vista.empty:
        st.info("Ningún puesto cumple los filtros seleccionados.")
        return

    st.metric("Puestos en la vista", f"{len(vista)}")

    # ---- Sección A · Emparejador de renombres -------------------------------
    st.divider()
    st.markdown("#### A · Emparejador de renombres *(mejora creadora · VIS-DEC-0026)*")
    st.caption(
        "Aplica `COL`↔`IE`, `SED`↔`SEDE` y `SE`↔`SEDE` sobre los puestos sin línea base y "
        "ordena por diferencia de votos. **No empata: propone.**"
    )
    if sin_base is None:
        st.info("Sin `data/PROTOCOLO_CAMPO_puestos.csv`: el emparejador no tiene insumo.")
    else:
        sb = sin_base if muni == "TODOS" else sin_base[sin_base["municipio"] == muni]
        pares = emparejar_renombres(sb)
        if pares.empty:
            st.info("No se encontraron pares candidatos con estas reglas en el filtro actual.")
        else:
            utiles = pares[pares["confianza"].isin(["ALTA", "MEDIA"])]
            st.success(
                f"**{len(utiles)} puestos identificados como probables renombres**, "
                f"ahorrando visitas de campo (de {len(pares)} pares candidatos)."
            )
            st.dataframe(utiles, use_container_width=True, hide_index=True)
            st.warning("**Tome foto de la placa para confirmar.** Un par propuesto no es un par resuelto.")
            st.download_button(
                "Descargar pares propuestos (CSV)",
                utiles.to_csv(index=False).encode("utf-8-sig"),
                "pares_renombre_propuestos.csv", "text/csv", key="dl_pares",
            )

    # ---- Sección B · Fichas de validación de campo -------------------------
    st.divider()
    st.markdown("#### B · Fichas de validación de campo")
    tabla = vista.copy()
    tabla["Pregunta_Campo"] = tabla["bucket_etq"].map({
        ETIQUETAS["ROJO"]: "¿Cambiaron las mesas? ¿Hubo traslado o cierre?",
        ETIQUETAS["AMARILLO"]: "¿Se le asignaron mesas nuevas entre 2019 y 2023?",
        ETIQUETAS["VERDE"]: "Verificar solo si el nombre del puesto cambió.",
        ETIQUETAS["SIN_BASE"]: "¿Es el mismo puesto con otro nombre? Foto de la placa.",
    }).fillna("Verificar nombre y mesas.")
    cols = [c for c in ("municipio", "puesto", "bucket_etq", "var_pct", "Pregunta_Campo") if c in tabla.columns]
    tabla = tabla[cols].rename(columns={"municipio": "Municipio", "puesto": "Puesto",
                                        "bucket_etq": "Bucket", "var_pct": "Variación"})
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button(
        "Descargar fichas filtradas (CSV · utf-8-sig)",
        tabla.to_csv(index=False).encode("utf-8-sig"),
        "fichas_proyeccion_2027.csv", "text/csv", key="dl_fichas",
    )

    # ---- Advertencias forenses ---------------------------------------------
    st.divider()
    st.error(
        "**Un rango de 1.527 a 7.321 votos no es una proyección: es una advertencia de que falta el "
        "dato de mesas.** Ningún puesto tiene valor puntual."
    )
    st.info(
        "**Varianza transversal ≠ temporal.** 663 puestos medidos en una pareja de comicios. "
        "No se estima tendencia entre más de dos elecciones."
    )
    st.caption(
        "Esta proyección se basa en varianza transversal histórica (2019→2023). "
        "No constituye predicción puntual."
    )


# Permite probar la logica pura sin Streamlit:  python proyeccion_2027.py
if __name__ == "__main__":
    print("MEDIANA=%.2f SIGMA=%.2f" % (MEDIANA, SIGMA))
    print("cortes: -1s=%.2f +1s=%.2f +2s=%.2f" % (LIM_INF_1, LIM_SUP_1, LIM_SUP_2))
    for v in (-54.4, -30.6, 0.0, 37.0, 37.5, 70.8, 427.2):
        print("  %8.1f%% -> %s" % (v, asignar_bucket(v)))
    print("normalizacion:")
    for n in ("COL JORGE ARDILA DUARTE SEDE A", "IE JORGE ARDILA DUARTE SEDE A",
              "IE AURELIO MARTINEZ MUTIS SED A", "IE AURELIO MARTINEZ MUTIS SEDE A",
              "IE N S DEL PILAR SE B", "IE N S DEL PILAR SEDE B"):
        print("  %-38s -> %s" % (n, _normalizar(n)))
