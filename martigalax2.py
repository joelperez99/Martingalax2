import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Simulación Martingala x2 (max 4x)",
    layout="wide",
)

st.markdown("""
<style>
    [data-testid="metric-container"] {
        background: #1e3a5f;
        border-radius: 8px;
        padding: 12px;
        color: white;
    }
    [data-testid="metric-container"] label {
        color: #a8c8f0 !important;
        font-size: 12px;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: white !important;
        font-size: 20px;
        font-weight: bold;
    }
    [data-testid="metric-container"] [data-testid="stMetricDelta"] svg {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# ── Título ──────────────────────────────────────────────────────────────────
st.markdown(
    "<h2 style='text-align:center; background:#1e3a5f; color:white; padding:16px; border-radius:10px;'>"
    "SIMULACION MARTINGALA x2 (max 4x) — Cuotas y P&L Reales</h2>",
    unsafe_allow_html=True,
)
st.markdown("")

# ── Upload ───────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Sube tu archivo Excel con datos históricos",
    type=["xlsx", "xls"],
)

if uploaded_file is None:
    st.info(
        "**Formato esperado del Excel:**  \n"
        "Columnas: `Timestamp | Bet Side | Stake | Entry Price (0-1) | Correcto (SI/NO) | PL`"
    )
    st.stop()

# ── Leer archivo ─────────────────────────────────────────────────────────────
try:
    df_raw = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"No se pudo leer el archivo: {e}")
    st.stop()

with st.expander("Vista previa de datos originales", expanded=False):
    st.dataframe(df_raw, use_container_width=True)

st.markdown("---")
st.subheader("Configuración")

cols = df_raw.columns.tolist()

def find_col(keywords, fallback_idx=0):
    for kw in keywords:
        for i, c in enumerate(cols):
            if kw in str(c).lower():
                return i
    return min(fallback_idx, len(cols) - 1)

cfg1, cfg2, cfg3 = st.columns([2, 2, 1])

with cfg1:
    ts_col     = st.selectbox("Columna Timestamp",                    cols, index=find_col(["time","fecha","timestamp"], 0))
    side_col   = st.selectbox("Columna Side (Up/Down)",               cols, index=find_col(["side","bet"], 1))
    price_col  = st.selectbox("Columna Entry Price (probabilidad 0–1)", cols, index=find_col(["entry","price","precio"], 3))
    result_col = st.selectbox("Columna Resultado (SI=WIN / NO=LOSS)", cols, index=find_col(["correct","result","resultado"], 4))

with cfg2:
    bankroll_init = st.number_input("Bankroll Inicial ($)",  value=100.0, min_value=1.0,  step=10.0)
    base_bet      = st.number_input("Apuesta Base ($)",      value=1.0,   min_value=0.01, step=0.5)
    max_mult      = st.selectbox("Multiplicador Máximo",     [2, 4, 8, 16], index=1,
                                 help="Límite del multiplicador en rachas de pérdidas")

with cfg3:
    win_value = st.text_input("Valor que indica WIN", value="SI",
                              help="Texto en la columna Resultado que significa ganancia")

run = st.button("▶  Simular Martingala", type="primary", use_container_width=True)

if not run:
    st.stop()

# ── Simulación ────────────────────────────────────────────────────────────────
results      = []
bankroll     = bankroll_init
mult         = 1
cons_loss    = 0
bankroll_max = bankroll_init
bankroll_min = bankroll_init
trades_win   = 0
trades_loss  = 0

for _, row in df_raw.iterrows():
    # Validar price
    try:
        price = float(row[price_col])
        assert 0 < price < 1
    except Exception:
        continue

    timestamp = row[ts_col]
    side      = row[side_col]
    is_win    = str(row[result_col]).strip().upper() == win_value.strip().upper()

    cuota = 1.0 / price

    # Stake necesario para ganar exactamente base_bet * mult
    # stake * (cuota - 1) = base_bet * mult  →  stake = base_bet * mult * P/(1-P)
    stake = base_bet * mult * price / (1.0 - price)

    if is_win:
        pl_sim      = base_bet * mult   # ganancia neta
        riesgo_show = base_bet * mult   # muestra lo ganado
        resultado   = "WIN"
        trades_win += 1
    else:
        pl_sim      = -stake            # pierde el stake
        riesgo_show = stake             # muestra lo perdido
        resultado   = "LOSS"
        trades_loss += 1

    # P&L Original: sin martingala (siempre x1)
    pl_original = base_bet if is_win else -(base_bet * price / (1.0 - price))

    bankroll     += pl_sim
    bankroll_max  = max(bankroll_max, bankroll)
    bankroll_min  = min(bankroll_min, bankroll)

    results.append({
        "#":               len(results) + 1,
        "Timestamp":       timestamp,
        "Side":            side,
        "Precio Poly":     round(price, 3),
        "Cuota (1/P)":     round(cuota, 3),
        "Resultado":       resultado,
        "Mult":            f"x{mult}",
        "_mult_num":       mult,
        "Riesgo ($)":      round(riesgo_show, 4),
        "P&L Sim ($)":     round(pl_sim, 4),
        "Bankroll ($)":    round(bankroll, 2),
        "Cons.Loss":       cons_loss,
        "P&L Original ($)":round(pl_original, 4),
    })

    # Actualizar para la siguiente operación
    if is_win:
        mult      = 1
        cons_loss = 0
    else:
        cons_loss += 1
        mult       = min(mult * 2, max_mult)

if not results:
    st.error("No se encontraron filas válidas. Revisa el mapeo de columnas y el archivo.")
    st.stop()

sim_df = pd.DataFrame(results)

# ── Métricas resumen ──────────────────────────────────────────────────────────
profit_total  = bankroll - bankroll_init
max_drawdown  = bankroll_max - bankroll_min
total_trades  = trades_win + trades_loss
win_rate      = trades_win / total_trades * 100 if total_trades > 0 else 0
profit_delta  = f"{'+' if profit_total >= 0 else ''}{profit_total:.2f}"

st.markdown("---")
st.subheader("Resumen de Simulación")

m1, m2, m3, m4, m5, m6, m7, m8, m9 = st.columns(9)
m1.metric("Bankroll Inicial",  f"${bankroll_init:.2f}")
m2.metric("Bankroll Final",    f"${bankroll:.2f}",     profit_delta)
m3.metric("Profit Total",      f"${profit_total:.2f}")
m4.metric("Bankroll Max",      f"${bankroll_max:.2f}")
m5.metric("Bankroll Min",      f"${bankroll_min:.2f}")
m6.metric("Max Drawdown",      f"${max_drawdown:.2f}")
m7.metric("Win Rate",          f"{win_rate:.1f}%")
m8.metric("Trades Win",        str(trades_win))
m9.metric("Trades Loss",       str(trades_loss))

# ── Gráfico bankroll ──────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Evolución del Bankroll")
chart_df = sim_df[["#", "Bankroll ($)"]].set_index("#")
st.line_chart(chart_df, use_container_width=True)

# ── Tabla detallada con colores ───────────────────────────────────────────────
st.markdown("---")
st.subheader("Detalle de Operaciones")

display_df = sim_df.drop(columns=["_mult_num"]).copy()

WIN_BG   = "background-color: #c8e6c9; color: #1b5e20"
LOSS1_BG = "background-color: #fff9c4; color: #7c6700"   # x1 loss
LOSS2_BG = "background-color: #ffe0b2; color: #e65100"   # x2 loss
LOSS4_BG = "background-color: #ffcdd2; color: #b71c1c"   # x4+ loss


def style_table(df_in: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=df_in.index, columns=df_in.columns)
    for i, row in df_in.iterrows():
        if row["Resultado"] == "WIN":
            styles.loc[i, :] = WIN_BG
        else:
            m = int(str(row["Mult"]).replace("x", ""))
            if m >= 4:
                styles.loc[i, :] = LOSS4_BG
            elif m >= 2:
                styles.loc[i, :] = LOSS2_BG
            else:
                styles.loc[i, :] = LOSS1_BG
    return styles


fmt = {
    "Precio Poly":      "{:.3f}",
    "Cuota (1/P)":      "{:.3f}",
    "Riesgo ($)":       "{:.4f}",
    "P&L Sim ($)":      "{:.4f}",
    "Bankroll ($)":     "${:.2f}",
    "P&L Original ($)": "{:.4f}",
}

styled = (
    display_df.style
    .apply(style_table, axis=None)
    .format(fmt)
)

st.dataframe(styled, use_container_width=True, height=520)

# ── Descarga ──────────────────────────────────────────────────────────────────
csv = display_df.to_csv(index=False)
st.download_button(
    label="⬇ Descargar resultados CSV",
    data=csv,
    file_name="simulacion_martingala.csv",
    mime="text/csv",
    use_container_width=True,
)
