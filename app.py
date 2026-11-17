"""
AEGIS-INTELLECT v2.0 · Santander Predictivo
===========================================

Dashboard predictivo construido SOBRE EXPEDIENTES AUDITADOS, no sobre cifras de prensa.

Auditoría de la v1 (para el changelog, no para el código):
  `AEGIS-POLITICA/06_Herramientas/agente_intellect/deploy/app.py` · 1.013 líneas · 6 pestañas
  (`t1..t6` en L611) · título «Santander: inteligencia predictiva» · 0 `st.metric` ·
  carga 4 CSV propios (detalle_candidatos, anomalias_y_clusters, atlas_partidos, atlas_maestro) ·
  NO conoce el corpus MMV ni ningún expediente de auditoría.
  Las cifras 825/87/983.070 **no están en su código** (0 ocurrencias): viven en sus CSV.

REGLA DE ORO
  Si un dato no está, se muestra NO_CALCULABLE o DEUDA_DE_INSUMO_EXTERNO.
  Nunca se rellena con un supuesto. Nunca se dibuja un DataFrame vacío que parezca un cero.

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"

# --------------------------------------------------------------------------- #
# Constantes auditadas (VIS-DEC-0018 / 0019)
# --------------------------------------------------------------------------- #

CORPUS_2023 = {
    "puestos": 818,            # medida con código municipal válido
    "puestos_techo_v1": 825,   # cifra declarada por la v1, sin sustento en el corpus
    "municipios": 87,          # DIVIPOLA confirmada: 87 (EXP-0031)
    "votos_total": 5_144_492,
    "votos_validos": 4_503_255,
    "nulos": 112_843,
    "blancos": 528_394,
    "fuente": "MMV_2023_27_SANTANDER.csv",
    "sha256": "16d999f6522f1d2cfb6d4aa35f407f07d0a24c4b14ce14e3fe5dc828f1a2b5da",
}

DRIFT = {"comparables": 663, "mediana": 3.22, "sigma": 33.79, "solo_2019": 100, "solo_2023": 155}

NO_CALCULABLE = "NO_CALCULABLE"
DEUDA = "DEUDA_DE_INSUMO_EXTERNO"

# Reglas de renombre verificadas en VIS-DEC-0026 (con votos, no solo con nombres).
REGLAS_RENOMBRE = [("COL ", "IE "), ("IE ", "COL "), ("SED ", "SEDE "), ("SE ", "SEDE "), ("SEDE ", "SEDE ")]


# --------------------------------------------------------------------------- #
# Carga con degradación explícita
# --------------------------------------------------------------------------- #

@st.cache_data(show_spinner=False)
def cargar_csv(nombre: str) -> pd.DataFrame | None:
    """Devuelve None si no existe: obliga a la pestaña a declarar la deuda."""
    ruta = DATA_DIR / nombre
    if not ruta.exists():
        return None
    try:
        return pd.read_csv(ruta, dtype=str, keep_default_na=False)
    except Exception as exc:
        st.error(f"No se pudo leer {nombre}: {exc}")
        return None


@st.cache_data(show_spinner=False)
def cargar_partidos() -> dict[str, str] | None:
    """Catálogo oficial de partidos (347 entradas). Copiado de POLITICA en solo lectura."""
    ruta = DATA_DIR / "mapeo_partidos_2026.json"
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception as exc:
        st.error(f"No se pudo leer el mapeo de partidos: {exc}")
        return None
    partidos = datos.get("partidos") or {}
    # La clave de MAIS es "12", NO "0012": se conservan ambas formas para no fallar por relleno.
    tabla = {}
    for codigo, nombre in partidos.items():
        tabla[str(codigo)] = nombre
        tabla[str(codigo).lstrip("0") or "0"] = nombre
    return tabla


def resolver_partido(codigo: str, tabla: dict[str, str] | None) -> str:
    """Convierte '3020' en 'ALIANZA POR COLOMBIA'. Si no hay mapeo, deja el código visible."""
    if not codigo:
        return ""
    if tabla is None:
        return f"{codigo} (sin mapeo)"
    return tabla.get(str(codigo)) or tabla.get(str(codigo).lstrip("0")) or f"{codigo} (no catalogado)"


def exigir(df: pd.DataFrame | None, nombre: str, expediente: str) -> pd.DataFrame | None:
    if df is None:
        st.warning(
            f"**{DEUDA}** · Falta `data/{nombre}`.\n\n"
            f"Lo produce el expediente **{expediente}**. "
            f"Sin ese archivo esta pestaña no muestra datos: no se estiman."
        )
        return None
    return df


# --------------------------------------------------------------------------- #
# Encabezado y filtro global
# --------------------------------------------------------------------------- #

def encabezado() -> None:
    st.title("AEGIS-INTELLECT v2.0 · Santander Predictivo")
    st.caption(
        "Construido sobre expedientes auditados. "
        "Las cifras de la v1 (825 puestos, 87 municipios, 983.070 votos) fueron refutadas "
        "en VIS-DEC-0018/0019 y sustituidas por las medidas."
    )


def filtro_anio() -> str:
    return st.radio(
        "Año de análisis",
        ["2023", "2019", "2026", "Comparar 2019↔2023"],
        horizontal=True,
        help=(
            "2019 y 2023 son elecciones REGIONALES comparables. 2026 es NACIONAL: "
            "no se compara por partido (INCOHERENTE_CONTEXTO)."
        ),
    )


# --------------------------------------------------------------------------- #
# 1 · Dashboard
# --------------------------------------------------------------------------- #

def tab_dashboard() -> None:
    st.subheader("Dashboard ejecutivo · cifras medidas")
    st.caption(
        f"Fuente `{CORPUS_2023['fuente']}` · SHA256 `{CORPUS_2023['sha256'][:16]}…` · "
        "todas las corporaciones · 2023 · Santander"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Puestos operativos", f"{CORPUS_2023['puestos']}",
              help=f"Techo declarado por la v1: {CORPUS_2023['puestos_techo_v1']} (sin sustento). "
                   f"819 si se cuenta 1 fila de código municipal no numérico.")
    c2.metric("Municipios", f"{CORPUS_2023['municipios']}", help="87 oficiales DIVIPOLA, confirmado (EXP-0031)")
    c3.metric("Votos totales", f"{CORPUS_2023['votos_total']:,}".replace(",", "."))
    c4.metric("Votos válidos", f"{CORPUS_2023['votos_validos']:,}".replace(",", "."))

    st.divider()
    comp = pd.DataFrame({
        "Categoría": ["Válidos", "Nulos", "Blancos"],
        "Votos": [CORPUS_2023["votos_validos"], CORPUS_2023["nulos"], CORPUS_2023["blancos"]],
    })
    st.plotly_chart(px.bar(comp, x="Categoría", y="Votos", text="Votos", color="Categoría"),
                    use_container_width=True)
    st.info(
        "Los válidos **no** suman el total: 4.503.255 + 112.843 nulos + 528.394 blancos = 5.144.492. "
        "Una sola columna de porcentajes sobre el total sería `TOTAL_NO_SUMA`."
    )
    st.caption(
        f"**Reporte delta 825 → 818.** La diferencia de 6–7 puestos no es un error: es el resultado "
        f"de deduplicar por la clave compuesta `(Código Municipio, Código Puesto, Nombre Puesto)`. "
        f"`Código Puesto` **no es único**: en Bucaramanga todos los puestos comparten el código 01. "
        f"Se opera sobre los {CORPUS_2023['puestos']} verificados."
    )


# --------------------------------------------------------------------------- #
# 2 · Tendencia 2019 → 2023
# --------------------------------------------------------------------------- #

def tab_tendencia() -> None:
    st.subheader("Tendencia 2019 → 2023 · variación por puesto (Gobernador)")
    st.caption(f"EXP-0013 · {DRIFT['comparables']} comparables · mediana {DRIFT['mediana']:+.2f} % · "
               f"σ {DRIFT['sigma']:.2f} %")

    df = exigir(cargar_csv("EXP-0014_puestos_volatilidad.csv"), "EXP-0014_puestos_volatilidad.csv", "EXP-0014")
    if df is None:
        return
    for col in ("v2019", "v2023", "var_pct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["bucket"] = df["bucket"].map({"VERDE": "🟢 típico", "AMARILLO": "🟡 ajuste", "ROJO": "🔴 volátil"}).fillna(df["bucket"])

    izq, der = st.columns([2, 1])
    with der:
        sel = st.multiselect("Bucket", sorted(df["bucket"].unique()), default=sorted(df["bucket"].unique()))
    vista = df[df["bucket"].isin(sel)]
    with izq:
        st.plotly_chart(px.scatter(vista, x="v2019", y="v2023", color="bucket", hover_name="puesto",
                                   labels={"v2019": "Votos 2019", "v2023": "Votos 2023"}),
                        use_container_width=True)

    st.markdown("**Los 10 de mayor variación**")
    top = vista.reindex(vista["var_pct"].abs().sort_values(ascending=False).index).head(10)
    st.dataframe(top[["municipio", "puesto", "v2019", "v2023", "var_pct", "bucket"]],
                 use_container_width=True, hide_index=True)
    st.warning(
        "**Un puesto no persuade: recibe mesas.** Los mayores saltos son compatibles con "
        "reasignación de mesas. Y **5 de los 10 mayores descensos son puestos de cárcel**: "
        "logística de sufragio, no política."
    )


# --------------------------------------------------------------------------- #
# 3 · Proyección 2027
# --------------------------------------------------------------------------- #

def tab_proyeccion() -> None:
    st.subheader("Proyección 2027 · rangos, nunca un número")
    st.caption("EXP-0014 · rango = Votos_2023 × (1 + (mediana ± k·σ)) · k=1 típico · k=2 volátil")

    df = exigir(cargar_csv("EXP-0014_puestos_volatilidad.csv"), "EXP-0014_puestos_volatilidad.csv", "EXP-0014")
    if df is None:
        return
    for col in ("v2023", "rango_inf_2027", "rango_sup_2027", "var_pct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    b = df["bucket"].value_counts().rename(index={"VERDE": "🟢 típico", "AMARILLO": "🟡 ajuste", "ROJO": "🔴 volátil"})
    st.markdown("**Buckets de volatilidad**")
    st.dataframe(b.rename("puestos"), use_container_width=True)

    rojos = df[df["bucket"] == "ROJO"]
    rojos = rojos.reindex(rojos["var_pct"].abs().sort_values(ascending=False).index)
    st.markdown("**🔴 Puestos a vigilar**")
    st.dataframe(rojos.head(12)[["municipio", "puesto", "v2023", "var_pct", "rango_inf_2027", "rango_sup_2027"]],
                 use_container_width=True, hide_index=True)
    st.download_button("Descargar rangos 2027 (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "proyeccion_2027_rangos.csv", "text/csv")

    st.error(
        "**Un rango de 1.527 a 7.321 votos no es una proyección: es una advertencia de que falta el "
        "dato de mesas.** Ningún puesto tiene valor puntual. Sin validación de campo, estos rangos "
        "no son utilizables para decidir."
    )
    st.info(
        "**Varianza transversal ≠ temporal.** Se midió cuánto difieren 663 puestos entre sí en una "
        "pareja de comicios. No se mide cómo varía un puesto entre más elecciones."
    )


# --------------------------------------------------------------------------- #
# 4 · Validación de campo + emparejador de renombres
# --------------------------------------------------------------------------- #

def proponer_renombres(df: pd.DataFrame) -> pd.DataFrame:
    """
    Empareja puestos 'SIN_BASE_2019' contra 'SIN_BASE_2023' por regla de nombre + magnitud de voto.

    Sustento: VIS-DEC-0026 verificó tres pares reales (SED→SEDE, COL→IE, SE→SEDE) donde los votos
    son casi idénticos. La propuesta NO es un empate: es una hipótesis para que el campo confirme.
    """
    solo19 = df[df["grupo"] == "SIN_BASE_2019"].copy()
    solo23 = df[df["grupo"] == "SIN_BASE_2023"].copy()
    if solo19.empty or solo23.empty:
        return pd.DataFrame()
    solo19["v19"] = pd.to_numeric(solo19["v2019"], errors="coerce").fillna(0)
    solo23["v23"] = pd.to_numeric(solo23["v2023"], errors="coerce").fillna(0)

    def firma(nombre: str) -> str:
        n = " " + str(nombre).upper() + " "
        for a, b in REGLAS_RENOMBRE:
            n = n.replace(a, b)
        return " ".join(n.split())

    solo19["firma"] = solo19["puesto"].map(firma)
    solo23["firma"] = solo23["puesto"].map(firma)
    pares = solo19.merge(solo23, on=["municipio", "firma"], suffixes=("_19", "_23"))
    if pares.empty:
        return pares
    pares["dif_votos"] = (pares["v23"] - pares["v19"]).abs()
    pares["dif_pct"] = (100 * pares["dif_votos"] / pares["v19"].clip(lower=1)).round(1)
    pares["confianza"] = pares["dif_pct"].map(lambda x: "ALTA" if x <= 5 else ("MEDIA" if x <= 20 else "BAJA"))
    return pares.sort_values("dif_pct")[
        ["municipio", "puesto_19", "v19", "puesto_23", "v23", "dif_votos", "dif_pct", "confianza"]
    ]


def tab_campo() -> None:
    st.subheader("Validación de campo · 288 fichas de terreno")
    st.caption("PROTOCOLO_VALIDACION_CAMPO_2027 · 33 🔴 + 255 sin línea base · VIS-DEC-0026")

    df = exigir(cargar_csv("PROTOCOLO_CAMPO_puestos.csv"), "PROTOCOLO_CAMPO_puestos.csv", "VIS-DEC-0026")
    if df is None:
        return

    g = df["grupo"].value_counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("Fichas totales", f"{len(df)}")
    c2.metric("🔴 a validar", f"{int(g.get('ROJO_SUBE', 0)) + int(g.get('ROJO_BAJA', 0))}")
    c3.metric("Sin línea base", f"{int(g.get('SIN_BASE_2019', 0)) + int(g.get('SIN_BASE_2023', 0))}")

    st.dataframe(g.rename("fichas"), use_container_width=True)
    st.download_button("Descargar las 288 fichas (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "fichas_campo_288.csv", "text/csv")

    st.divider()
    st.markdown("#### Emparejador de renombres *(propuesta creadora, VIS-DEC-0026)*")
    st.caption(
        "Cruza los puestos sin base 2019 contra los sin base 2023 aplicando las reglas verificadas "
        "(`COL`↔`IE`, `SED`↔`SEDE`, `SE`↔`SEDE`) y ordena por diferencia de votos. "
        "**No empata: propone.** El empate lo confirma el campo con una foto de la placa."
    )
    pares = proponer_renombres(df)
    if pares.empty:
        st.info("No se encontraron pares candidatos con estas reglas.")
    else:
        st.metric("Pares candidatos", f"{len(pares)}", help="de 255 puestos sin línea base")
        st.dataframe(pares.head(20), use_container_width=True, hide_index=True)
        st.download_button("Descargar pares propuestos (CSV)", pares.to_csv(index=False).encode("utf-8"),
                           "pares_renombre_propuestos.csv", "text/csv")
        st.warning(
            "**Un par propuesto no es un par resuelto.** La confianza ALTA reduce el trabajo de campo; "
            "no lo elimina. Los `BAJA` requieren visita."
        )

    st.markdown("#### Caso verificado")
    st.code(
        "2019: COL AURELIO MARTINEZ MUTIS SED A   -> 3.220 votos\n"
        "2023: COL AURELIO MARTINEZ MUTIS SEDE A  -> 3.209 votos\n"
        "Diferencia: 11 votos. El nombre cambió SED -> SEDE.\n"
        "No es una fuga de electores: es una abreviatura.",
        language="text",
    )


# --------------------------------------------------------------------------- #
# 5 · Partidos resueltos
# --------------------------------------------------------------------------- #

def tab_partidos() -> None:
    st.subheader("Catálogo de partidos · mapeo oficial")
    tabla = cargar_partidos()
    if tabla is None:
        st.warning(f"**{DEUDA}** · Falta `data/mapeo_partidos_2026.json` (fuente: Registraduría).")
        return

    unicos = sorted({v for v in tabla.values()})
    st.metric("Nombres distintos de partido", f"{len(unicos)}",
              help="347 códigos apuntan a 304 nombres distintos: varios códigos comparten partido.")
    st.caption(
        "EXP-0011 · el catálogo tiene **347 códigos** que resuelven a **304 nombres distintos**. "
        "`MAIS` se codifica **`12`**, no `0012`: el resolvedor acepta ambas formas."
    )
    buscar = st.text_input("Buscar partido", "")
    filas = [{"código": k, "partido": v} for k, v in sorted(tabla.items()) if len(k) > 1]
    tabla_vista = pd.DataFrame(filas)
    if buscar:
        tabla_vista = tabla_vista[tabla_vista["partido"].str.contains(buscar, case=False, na=False)]
    st.dataframe(tabla_vista, use_container_width=True, hide_index=True, height=320)

    st.error(
        f"**El desglose de voto por partido y puesto está {NO_CALCULABLE} en esta app.** "
        "Requiere cargar `MMV_2023_27_SANTANDER.csv` (192 MB), que no se versiona en el repo. "
        "El catálogo resuelve los códigos; el cruce con votos necesita el archivo completo."
    )


# --------------------------------------------------------------------------- #
# 6 · Límites
# --------------------------------------------------------------------------- #

def tab_limites() -> None:
    st.subheader("Límites del sistema y deudas abiertas")
    st.markdown(f"""
| Capacidad | Estado | Motivo |
|---|---|---|
| Puestos y votos 2023 | **OK** | corpus MMV hasheado |
| Tendencia 2019→2023 | **OK** | 663 comparables |
| Proyección 2027 por rangos | **OK** | σ transversal medida |
| Voto por partido y puesto | **{NO_CALCULABLE}** | requiere MMV completo (192 MB) |
| Nombres de candidato 2026 | **{NO_CALCULABLE}** | `santander_candidatos_2026.db` = 0 B |
| Participación por puesto | **{NO_CALCULABLE}** | sin columna de censo |
| Presidencia 2022 | **{NO_CALCULABLE}** | no está en el corpus |
| Seguridad por comuna | **{DEUDA}** | falta tabla puente zona↔comuna y población |
| Municipios 87 vs 88 | **RESUELTO** | 87 DIVIPOLA; el 88 era la cabecera (EXP-0031) |
| 255 sin línea base | **ABIERTO** | 4 verificados; el resto propuestos |
""")
    st.error(
        "**No se cruza seguridad con votación.** Dominios separados: `validar_ingesta_seguridad.py` "
        "rechaza el archivo completo si aparece un campo electoral."
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    st.set_page_config(page_title="AEGIS-INTELLECT v2.0", page_icon="🛡️", layout="wide")
    encabezado()
    anio = filtro_anio()
    if anio == "2026":
        st.warning(
            "2026 es elección **nacional** (Senado/Cámara): no se compara por partido con 2019/2023 "
            "(regionales) — `INCOHERENTE_CONTEXTO`. Los nombres de candidato 2026 no están en la fuente."
        )
    elif anio == "2019":
        st.info(
            "2019 está en el corpus (847.729 filas) pero esta app no lo carga completo: "
            "se usa a través del cruce ya calculado en EXP-0013/0014."
        )

    tabs = st.tabs(["📊 Dashboard", "📈 Tendencia 19→23", "🔮 Proyección 2027",
                    "📋 Campo y renombres", "🏛️ Partidos", "⚠️ Límites"])
    for tab, fn in zip(tabs, [tab_dashboard, tab_tendencia, tab_proyeccion, tab_campo, tab_partidos, tab_limites]):
        with tab:
            fn()


if __name__ == "__main__":
    main()
