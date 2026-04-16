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
    "<h2 style='text-align:center; background:#1e3a5f; color:white; "
    "padding:16px; border-radius:10px;'>"
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
    ts_col     = st.selectbox("Columna Timestamp",                      cols, index=find_col(["time","fecha","timestamp"], 0))
    side_col   = st.selectbox("Columna Side (Up/Down)",                 cols, index=find_col(["side","bet"], 1))
    price_col  = st.selectbox("Columna Entry Price (probabilidad 0–1)", cols, index=find_col(["entry","price","precio"], 3))
    result_col = st.selectbox("Columna Resultado (SI=WIN / NO=LOSS)",   cols, index=find_col(["correct","result","resultado"], 4))

with cfg2:
    bankroll_init = st.number_input("Bankroll Inicial ($)", value=100.0, min_value=1.0,  step=10.0)
    base_bet      = st.number_input("Apuesta Base ($)",     value=1.0,   min_value=0.01, step=0.5)
    max_mult      = st.selectbox(
        "Multiplicador Máximo",
        [2, 4, 8, 16], index=1,
        help="Al perder en este multiplicador, la secuencia REINICIA en x1",
    )

with cfg3:
    win_value = st.text_input(
        "Valor que indica WIN", value="SI",
        help="Texto en la columna Resultado que significa ganancia",
    )

run = st.button("▶  Simular Martingala", type="primary", use_container_width=True)

if not run:
    st.stop()

# ── Simulación ────────────────────────────────────────────────────────────────
# Lógica Martingala x2 (max 4x):
#   x1 → pierde → x2 → pierde → x4 → pierde → REINICIA en x1
#   En cuanto gana cualquier nivel → vuelve a x1
results      = []
bankroll     = bankroll_init
mult         = 1
cons_loss    = 0          # pérdidas consecutivas acumuladas (resetea solo en WIN)
bankroll_max = bankroll_init
bankroll_min = bankroll_init
trades_win   = 0
trades_loss  = 0

for _, row in df_raw.iterrows():
    try:
        price = float(row[price_col])
        assert 0 < price < 1
    except Exception:
        continue

    timestamp = row[ts_col]
    side      = row[side_col]
    is_win    = str(row[result_col]).strip().upper() == win_value.strip().upper()

    cuota = 1.0 / price

    # Stake para ganar exactamente base_bet × mult:
    #   stake × (cuota - 1) = base_bet × mult  →  stake = base_bet × mult × P/(1-P)
    stake = base_bet * mult * price / (1.0 - price)

    if is_win:
        pl_sim      =  base_bet * mult   # ganancia neta
        riesgo_show =  base_bet * mult   # se muestra lo ganado
        resultado   = "WIN"
        trades_win += 1
    else:
        pl_sim      = -stake             # pierde el stake
        riesgo_show =  stake             # se muestra lo perdido
        resultado   = "LOSS"
        trades_loss += 1

    # P&L Original: sin martingala (siempre x1)
    pl_original = base_bet if is_win else -(base_bet * price / (1.0 - price))

    bankroll     += pl_sim
    bankroll_max  = max(bankroll_max, bankroll)
    bankroll_min  = min(bankroll_min, bankroll)

    results.append({
        "#":                len(results) + 1,
        "Timestamp":        timestamp,
        "Side":             side,
        "Precio Poly":      round(price, 3),
        "Cuota (1/P)":      round(cuota, 3),
        "Resultado":        resultado,
        "Mult":             f"x{mult}",
        "_mult_num":        mult,
        "Riesgo ($)":       round(riesgo_show, 4),
        "P&L Sim ($)":      round(pl_sim, 4),
        "Bankroll ($)":     round(bankroll, 2),
        "Cons.Loss":        cons_loss,
        "P&L Original ($)": round(pl_original, 4),
    })

    # ── Actualizar mult para la SIGUIENTE operación ──────────────────────────
    if is_win:
        mult      = 1
        cons_loss = 0
    else:
        cons_loss += 1
        if mult >= max_mult:
            mult = 1          # ← REINICIO: al fallar en el máximo vuelve a x1
        else:
            mult = min(mult * 2, max_mult)

if not results:
    st.error("No se encontraron filas válidas. Revisa el mapeo de columnas y el archivo.")
    st.stop()

sim_df = pd.DataFrame(results)

# ── Métricas resumen ──────────────────────────────────────────────────────────
profit_total = bankroll - bankroll_init
max_drawdown = bankroll_max - bankroll_min
total_trades = trades_win + trades_loss
win_rate     = trades_win / total_trades * 100 if total_trades > 0 else 0
profit_delta = f"{'+' if profit_total >= 0 else ''}{profit_total:.2f}"

st.markdown("---")
st.subheader("Resumen de Simulación")

m1, m2, m3, m4, m5, m6, m7, m8, m9 = st.columns(9)
m1.metric("Bankroll Inicial", f"${bankroll_init:.2f}")
m2.metric("Bankroll Final",   f"${bankroll:.2f}",     profit_delta)
m3.metric("Profit Total",     f"${profit_total:.2f}")
m4.metric("Bankroll Max",     f"${bankroll_max:.2f}")
m5.metric("Bankroll Min",     f"${bankroll_min:.2f}")
m6.metric("Max Drawdown",     f"${max_drawdown:.2f}")
m7.metric("Win Rate",         f"{win_rate:.1f}%")
m8.metric("Trades Win",       str(trades_win))
m9.metric("Trades Loss",      str(trades_loss))

# ── Gráfico bankroll ──────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Evolución del Bankroll")
chart_df = sim_df[["#", "Bankroll ($)"]].set_index("#")
st.line_chart(chart_df, use_container_width=True)

# ── Tabla detallada con colores ───────────────────────────────────────────────
st.markdown("---")
st.subheader("Detalle de Operaciones")

display_df = sim_df.drop(columns=["_mult_num"]).copy()

# Paleta de colores (fondo fila, texto fila)
WIN_A  = ("#c8e6c9", "#1b5e20")   # verde claro  – WIN fila impar
WIN_B  = ("#a5d6a7", "#1b5e20")   # verde medio  – WIN fila par
L1_BG  = ("#fff9c4", "#5d4037")   # amarillo     – LOSS x1
L2_BG  = ("#ffe0b2", "#bf360c")   # naranja      – LOSS x2
L4_BG  = ("#ffcdd2", "#b71c1c")   # rojo claro   – LOSS x4


def style_table(df_in: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=df_in.index, columns=df_in.columns)
    win_toggle = 0
    for i, row in df_in.iterrows():
        if row["Resultado"] == "WIN":
            bg, fg = WIN_A if win_toggle % 2 == 0 else WIN_B
            win_toggle += 1
            base = f"background-color:{bg}; color:{fg}"
        else:
            win_toggle = 0
            m = int(str(row["Mult"]).replace("x", ""))
            if m >= 4:
                bg, fg = L4_BG
            elif m >= 2:
                bg, fg = L2_BG
            else:
                bg, fg = L1_BG
            base = f"background-color:{bg}; color:{fg}"

        styles.loc[i, :] = base

        # Texto especial en columnas Resultado y Mult
        if row["Resultado"] == "WIN":
            styles.loc[i, "Resultado"] = base + "; font-weight:bold; color:#1b5e20"
            styles.loc[i, "Mult"]      = base + "; color:#2e7d32; font-weight:bold"
        else:
            styles.loc[i, "Resultado"] = base + "; font-weight:bold; color:#c62828"
            m = int(str(row["Mult"]).replace("x", ""))
            mult_color = "#c62828" if m >= 4 else "#e65100" if m >= 2 else "#827717"
            styles.loc[i, "Mult"] = base + f"; color:{mult_color}; font-weight:bold"

        # P&L verde/rojo
        pl_val = row["P&L Sim ($)"]
        pl_color = "#1b5e20" if pl_val > 0 else "#c62828"
        styles.loc[i, "P&L Sim ($)"] = base + f"; color:{pl_color}; font-weight:bold"

    return styles


fmt = {
    "Precio Poly":       "{:.3f}",
    "Cuota (1/P)":       "{:.3f}",
    "Riesgo ($)":        "{:.4f}",
    "P&L Sim ($)":       "{:.4f}",
    "Bankroll ($)":      "${:.2f}",
    "P&L Original ($)":  "{:.4f}",
}

styled = (
    display_df.style
    .apply(style_table, axis=None)
    .format(fmt)
)

st.dataframe(styled, use_container_width=True, height=540)

# ── Descarga ──────────────────────────────────────────────────────────────────
csv = display_df.to_csv(index=False)
st.download_button(
    label="⬇ Descargar resultados CSV",
    data=csv,
    file_name="simulacion_martingala.csv",
    mime="text/csv",
    use_container_width=True,
)
