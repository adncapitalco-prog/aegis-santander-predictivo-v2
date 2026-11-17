# AEGIS-INTELLECT v2.0 · Santander Predictivo

Dashboard predictivo construido **sobre expedientes auditados**, no sobre cifras de prensa.

## Qué es

Una app Streamlit que responde tres preguntas sobre Santander con datos verificables:

1. **¿Cuántos puestos y votos hay?** — 818 puestos operativos, 87 códigos de municipio, 5.144.492 votos.
2. **¿Qué se movió entre 2019 y 2023?** — 663 puestos comparables, mediana +3,22 %, σ 33,79 %.
3. **¿Qué puede pasar en 2027?** — rangos por volatilidad, **nunca un número puntual**.

---

## Qué mejora respecto a la v1

La v1 vive en `AEGIS-POLITICA/06_Herramientas/agente_intellect/deploy/app.py`:
**1.013 líneas, 6 pestañas** (`t1…t6` en L611), título «Santander: inteligencia predictiva»,
**0 `st.metric`**, y carga 4 CSV propios (`detalle_candidatos`, `anomalias_y_clusters`,
`atlas_partidos`, `atlas_maestro`). **No conoce el corpus MMV ni ningún expediente de auditoría.**

> **Dato de auditoría:** las cifras `825`, `87` y `983.070` **no aparecen en el código de la v1**
> (0 ocurrencias). Viven en los CSV que carga. La corrección no es del `app.py`: es de los datos.

## Changelog forense

| # | Mejora | Expediente |
|---|---|---|
| **A1** | Dashboard corregido: 825→**818** puestos (techo declarado 825), 87 municipios DIVIPOLA, 983.070→**5.144.492** votos, con válidos/nulos/blancos separados | **VIS-DEC-0019** |
| **A2** | Pestaña **Tendencia 2019→2023**: 663 comparables, scatter por bucket, top 10 de variación | **EXP-0013** |
| **A3** | Pestaña **Proyección 2027**: rangos `Votos_2023 × (1 + (mediana ± k·σ))`, sin valores puntuales | **EXP-0014** |
| **A4** | Pestaña **Campo**: las 288 fichas descargables y el caso verificado `SED`→`SEDE` (3.220→3.209) | **VIS-DEC-0026** |
| **A5** | **Emparejador de renombres** *(propuesta creadora)*: cruza los 255 sin línea base con reglas verificadas y ordena por diferencia de votos | **VIS-DEC-0026** |
| **A6** | Pestaña **Partidos**: catálogo de 347 entradas resueltas, acepta `12` y `0012` para MAIS | **EXP-0011** |
| **A7** | Pestaña **Límites**: tabla de lo que el sistema no puede hacer y por qué | **VIS-DEC-0021** |
| **A8** | `cargar_csv` devuelve `None` (no un DataFrame vacío): cada pestaña **declara la deuda** | VIS-DEC-0012 |

### La propuesta creadora (A5)

El encargo no la pedía. Se identificó al auditar el protocolo de campo: de los **255 puestos sin línea
base**, los tres pares verificados mostraban que **un renombre no cambia los votos** (3.220 vs 3.209).
Eso permite **proponer pares automáticamente** aplicando `COL`↔`IE`, `SED`↔`SEDE`, `SE`↔`SEDE` y
ordenando por diferencia de votos.

**Reduce el trabajo de campo sin sustituirlo:** el par propuesto es una hipótesis con confianza
`ALTA/MEDIA/BAJA`; el empate lo confirma una foto de la placa.

---

## Instalación y despliegue

```bash
pip install -r requirements.txt
streamlit run app.py
```

**`requirements.txt`**

```
streamlit>=1.30
pandas>=2.0
plotly>=5.18
```

### Datos requeridos

La app **no los inventa**: si faltan, cada pestaña declara la deuda y se detiene.

```
data/
├── EXP-0014_puestos_volatilidad.csv     # 663 filas · buckets y rangos
├── PROTOCOLO_CAMPO_puestos.csv          # 288 filas · fichas de campo
└── mapeo_partidos_2026.json             # 347 códigos → nombre oficial
```

Los tres se copian desde `AEGIS-VISION/04_Experimentos/` y `AEGIS-POLITICA/08_Reportes/`
(**solo lectura** en el origen). Las cifras del dashboard **no necesitan CSV**: son constantes
auditadas en `app.py`, con el hash de su fuente.

---

## Advertencias forenses

1. **No predice.** La pestaña de 2027 da **rangos de volatilidad**, no pronósticos.
2. **No compara 2026 con 2019/2023 por partido.** Nacional vs regional: `INCOHERENTE_CONTEXTO`.
3. **No cruza seguridad con votación.** Dominios separados por diseño y por validador.
4. **No tiene candidatos 2026.** El contenedor local está en **0 bytes**.
5. **No tiene participación por puesto.** No hay columna de censo en el corpus.
6. **No resuelve el voto por partido y puesto**: requiere el MMV completo (192 MB), que no se versiona.
7. **87 vs 88 municipios: RESUELTO** (EXP-0031). Son **87** oficiales; el «88» era la fila de cabecera del CSV contada como registro.
8. **255 puestos sin línea base.** Cuatro verificados como renombre; el resto, propuesto.
9. **Los rangos de los 33 volátiles no son utilizables** sin validación de campo: un rango de
   1.527 a 7.321 votos no sirve para decidir.
10. **Un par de renombre propuesto no es un par resuelto.**

## Estado

`LISTO_PARA_COMMIT` — seis pestañas, tres CSV de datos, y diez advertencias que el cliente ve antes
de creer una sola cifra.
