"""
Multi-Prime Commercial Control Tower: web app.

Run locally:   streamlit run app.py
Deploy:        Streamlit Community Cloud -> point it at this repo, main file app.py
"""
import io
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from config import TOLERANCES, PER_DIEM_CAP  # noqa: E402
from run_engine import run, scorecard  # noqa: E402
from schema import SCHEMA, coerce, read_folder  # noqa: E402
from validate_input import validate  # noqa: E402

DEMO, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean_demo"
GATE_LABEL = {"PASS": "✓ PASS", "REVIEW": "! REVIEW", "HOLD": "✕ HOLD"}
GATE_COLOR = {"✓ PASS": "#0ca30c", "! REVIEW": "#fab219", "✕ HOLD": "#d03b3b"}

st.set_page_config(page_title="Multi-Prime Commercial Control Tower", layout="wide")
st.title("Multi-Prime Commercial Control Tower")
st.caption("3-way match, pre-approval checks and governance gates for multi-prime construction invoices. "
           "Demo data is synthetic. Contractors, sites and rates are fictional.")


# ---------------- Data source ----------------
def templates_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for t, cols in SCHEMA.items():
            z.writestr(f"{t}.csv", ",".join(c for c, *_ in cols) + "\n")
        dd = ROOT / "DATA_DICTIONARY.md"
        if dd.exists():
            z.writestr("DATA_DICTIONARY.md", dd.read_text())
    return buf.getvalue()


with st.sidebar:
    st.header("1. Data")
    source = st.radio("Choose data", ["Demo: synthetic invoices with planted errors",
                                      "Demo: clean invoices (use with stress test)",
                                      "Upload my own CSV files"])
    uploaded = None
    if source.startswith("Upload"):
        uploaded = st.file_uploader("Upload the 7 required CSVs (plus primes.csv, optional)",
                                    type="csv", accept_multiple_files=True)
        st.download_button("Download blank templates", templates_zip(), "mpct_templates.zip")

    st.header("2. Tolerances")
    tol = dict(TOLERANCES)
    tol["qty_review_pct"] = st.slider("Qty over verified: REVIEW above (%)", 0.0, 10.0, TOLERANCES["qty_review_pct"], 0.25)
    tol["qty_hold_pct"] = st.slider("Qty over verified: HOLD above (%)", 0.0, 20.0, TOLERANCES["qty_hold_pct"], 0.5)
    tol["rate_hold_pct"] = st.slider("Rate over contract: HOLD above (%)", 0.0, 5.0, TOLERANCES["rate_hold_pct"], 0.1)
    tol["pct_review_pts"] = st.slider("Lump-sum % over verified: REVIEW above (pts)", 0.0, 10.0, TOLERANCES["pct_review_pts"], 0.5)
    tol["pct_hold_pts"] = st.slider("Lump-sum % over verified: HOLD above (pts)", 0.0, 20.0, TOLERANCES["pct_hold_pts"], 0.5)
    tol["tm_hold_pct"] = st.slider("T&M hours over approved: HOLD above (%)", 0.0, 30.0, TOLERANCES["tm_hold_pct"], 1.0)
    cap = st.number_input("Per diem cap ($/worker-day)", value=PER_DIEM_CAP, step=1.0)


def load_tables():
    if source.startswith("Demo: synthetic"):
        return read_folder(DEMO)
    if source.startswith("Demo: clean"):
        return read_folder(CLEAN)
    if not uploaded:
        return None
    tables = {}
    for f in uploaded:
        name = Path(f.name).stem
        if name in SCHEMA or name == "ground_truth_errors":
            str_cols = {c: str for c, typ, *_ in SCHEMA.get(name, []) if typ == "str"}
            tables[name] = pd.read_csv(f, dtype=str_cols or {"invoice_id": str})
        else:
            st.sidebar.warning(f"Ignored {f.name}: file name doesn't match a table name.")
    return tables


tables = load_tables()
if tables is None:
    st.info("Upload your CSV files in the sidebar. Start from the blank templates; DATA_DICTIONARY.md explains every column.")
    st.stop()

issues = validate(tables)
errors = [i for i in issues if i["level"] == "ERROR"]
if issues:
    with st.expander(f"Input check: {len(errors)} error(s), {len(issues) - len(errors)} warning(s)",
                     expanded=bool(errors)):
        st.dataframe(pd.DataFrame(issues), width="stretch", hide_index=True)
if errors:
    st.error("Fix the input errors above, then upload again.")
    st.stop()

engine_tables = {k: v for k, v in tables.items() if k in SCHEMA}
exceptions, gates = run(tolerances=tol, tables=engine_tables, per_diem_cap=cap)
sc = scorecard(gates, exceptions, tables.get("primes"))

# ---------------- KPIs ----------------
n = len(gates)
k = st.columns(5)
k[0].metric("Invoices", f"{n}")
k[1].metric("Billed (gross)", f"${gates.gross_amount.sum() / 1e6:,.1f}M")
k[2].metric("✓ First-pass rate", f"{100 * (gates.gate == 'PASS').mean():.0f}%" if n else "-")
k[3].metric("✕ On hold", f"{(gates.gate == 'HOLD').sum()}")
k[4].metric("Amount at risk", f"${gates.amount_at_risk.sum() / 1e6:,.2f}M")

tab_gate, tab_inv, tab_exc, tab_acc, tab_stress = st.tabs(
    ["Gates by prime", "Invoice drill-down", "Exceptions", "Accuracy (if answer key)", "Stress test"])

with tab_gate:
    g = gates.assign(Gate=gates.gate.map(GATE_LABEL)).groupby(["prime_id", "Gate"]).size().reset_index(name="Invoices")
    order = list(GATE_COLOR)
    chart = (alt.Chart(g).mark_bar(stroke="#ffffff", strokeWidth=2)
             .encode(y=alt.Y("prime_id:N", title=None, scale=alt.Scale(paddingInner=0.3)),
                     x=alt.X("Invoices:Q", title="Invoices"),
                     color=alt.Color("Gate:N", scale=alt.Scale(domain=order, range=[GATE_COLOR[o] for o in order]),
                                     legend=alt.Legend(orient="top", title=None)),
                     order=alt.Order("gate_order:Q"),
                     tooltip=["prime_id", "Gate", "Invoices"])
             .transform_calculate(gate_order=f"indexof({order}, datum.Gate)")
             .properties(height=alt.Step(40)))
             
    st.altair_chart(chart, width="stretch")
    st.dataframe(sc, width="stretch", hide_index=True)

with tab_inv:
    f = st.multiselect("Show gates", ["PASS", "REVIEW", "HOLD"], default=["HOLD", "REVIEW"])
    view = gates[gates.gate.isin(f)].sort_values("amount_at_risk", ascending=False)
    st.dataframe(view, width="stretch", hide_index=True)
    if len(view):
        pick = st.selectbox("Open an invoice", view.invoice_id)
        st.markdown(f"**{pick}**: {GATE_LABEL[view.set_index('invoice_id').at[pick, 'gate']]}")
        lines = coerce(tables["invoice_lines"], "invoice_lines")
        st.dataframe(lines[lines.invoice_id == pick], width="stretch", hide_index=True)
        st.dataframe(exceptions[exceptions.invoice_id == pick], width="stretch", hide_index=True)

with tab_exc:
    rules = sorted(exceptions.rule.unique()) if len(exceptions) else []
    pick_rules = st.multiselect("Rules", rules, default=rules)
    ev = exceptions[exceptions.rule.isin(pick_rules)]
    st.dataframe(ev, width="stretch", hide_index=True)
    st.download_button("Download exceptions (CSV)", ev.to_csv(index=False), "exceptions.csv")
    st.download_button("Download invoice gates (CSV)", gates.to_csv(index=False), "invoice_gates.csv")

with tab_acc:
    if "ground_truth_errors" in tables:
        truth = tables["ground_truth_errors"]
        if len(truth) == 0:
            st.info("This dataset has an empty answer key (no planted errors). Every exception here would be a false alarm.")
            st.metric("False alarms", len(exceptions))
        else:
            def ks(df, col):
                return set(zip(df.invoice_id.astype(str), pd.to_numeric(df.line_no, errors="coerce").fillna(-1).astype(int), df[col]))
            det, tru = ks(exceptions, "rule"), ks(truth, "error_type")
            rows = []
            for r in sorted({x[2] for x in tru}):
                d, t_ = {x for x in det if x[2] == r}, {x for x in tru if x[2] == r}
                tp = len(d & t_)
                rows.append({"rule": r, "planted": len(t_), "caught": tp, "missed": len(t_ - d),
                             "false_alarms": len(d - t_),
                             "recall_%": round(100 * tp / len(t_), 1),
                             "precision_%": round(100 * tp / len(d), 1) if d else None})
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption("Move the tolerance sliders and watch precision and recall change.")
    else:
        st.info("No answer key (ground_truth_errors.csv) in this dataset. Use the Stress test tab to create one.")

with tab_stress:
    st.markdown("Plants known errors into a **copy** of the current data, reruns the engine, and reports "
                "what was caught, what was missed, and any new false alarms. This is how you test the engine "
                "on real data that has no answer key.")
    c1, c2, c3 = st.columns(3)
    n_err = c1.number_input("Errors to plant", 5, 200, 40, 5)
    subtle = c2.slider("Share of tiny errors", 0.0, 1.0, 0.25, 0.05)
    seed = c3.number_input("Random seed", 1, 9999, 1)
    if st.button("Run stress test"):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "data", Path(tmp) / "stress"
            src.mkdir()
            for name, df in engine_tables.items():
                coerce(df, name).to_csv(src / f"{name}.csv", index=False)
            res = subprocess.run([sys.executable, str(ROOT / "src" / "inject_errors.py"), "--data", str(src),
                                  "--out", str(dst), "--n", str(n_err), "--subtle", str(subtle), "--seed", str(seed)],
                                 capture_output=True, text=True, cwd=str(ROOT / "src"))
            if res.returncode != 0:
                st.error(res.stderr[-2000:])
            else:
                report = (dst / "stress_test_report.md").read_text()
                st.markdown(report.replace("\n## ", "\n#### ").replace("# Stress test report", "### Stress test report"))
