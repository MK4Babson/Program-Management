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
from insights import (filter_scope, project_summary, prime_trend, rate_spread,  # noqa: E402
                      generate_insights, prime_names, money, RULE_LABEL)

DEMO, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean_demo"
GATE_LABEL = {"PASS": "✓ PASS", "REVIEW": "! REVIEW", "HOLD": "✕ HOLD"}
GATE_COLOR = {"✓ PASS": "#0ca30c", "! REVIEW": "#fab219", "✕ HOLD": "#d03b3b"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
LEVEL = {"critical": (":red[**✕ Act now**]"), "warning": (":orange[**! Watch**]"),
         "info": (":blue[**i Plan**]"), "good": (":green[**✓ Good news**]")}
STATUS = {"Red": ":red[● Act now]", "Amber": ":orange[● Watch]", "Green": ":green[● On track]"}

st.set_page_config(page_title="Multi-Prime Commercial Control Tower", layout="wide")
st.title("Multi-Prime Commercial Control Tower")
st.caption("Invoice governance and decision support for a multi-prime data center construction program. "
           "Demo data is synthetic: contractors, sites and rates are fictional.")


def templates_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for t, cols in SCHEMA.items():
            z.writestr(f"{t}.csv", ",".join(c for c, *_ in cols) + "\n")
        dd = ROOT / "DATA_DICTIONARY.md"
        if dd.exists():
            z.writestr("DATA_DICTIONARY.md", dd.read_text())
    return buf.getvalue()


# ---------------- Sidebar: data ----------------
with st.sidebar:
    st.header("1. Data")
    source = st.radio("Choose data", ["Demo: synthetic program with planted errors",
                                      "Demo: clean invoices (use with stress test)",
                                      "Upload my own CSV files"])
    uploaded = None
    if source.startswith("Upload"):
        uploaded = st.file_uploader("Upload the 7 required CSVs (plus primes.csv and projects.csv, optional)",
                                    type="csv", accept_multiple_files=True)
        st.download_button("Download blank templates", templates_zip(), "mpct_templates.zip")


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


raw = load_tables()
if raw is None:
    st.info("Upload your CSV files in the sidebar. Start from the blank templates; DATA_DICTIONARY.md explains every column.")
    st.stop()

issues = validate(raw)
errors = [i for i in issues if i["level"] == "ERROR"]
if issues:
    with st.expander(f"Input check: {len(errors)} error(s), {len(issues) - len(errors)} warning(s)", expanded=bool(errors)):
        st.dataframe(pd.DataFrame(issues), width="stretch", hide_index=True)
if errors:
    st.error("Fix the input errors above, then upload again.")
    st.stop()

tables = {k: coerce(v, k) for k, v in raw.items() if k in SCHEMA}
if "projects" in raw:
    tables["projects"] = raw["projects"]  # keep extra columns such as campus
names = prime_names(tables)

# ---------------- Sidebar: filters + tolerances ----------------
inv_all = tables["invoices"]
all_projects = sorted(inv_all.project_id.dropna().unique())
all_primes = sorted(inv_all.prime_id.dropna().unique())
all_periods = sorted(inv_all.period.dropna().unique())
with st.sidebar:
    st.header("2. Filters")
    f_projects = st.multiselect("Projects", all_projects, default=all_projects)
    f_primes = st.multiselect("Contractors", all_primes, default=all_primes, format_func=lambda p: names.get(p, p))
    if len(all_periods) > 1:
        p0, p1 = st.select_slider("Months", options=all_periods, value=(all_periods[0], all_periods[-1]))
        f_periods = [p for p in all_periods if p0 <= p <= p1]
    else:
        f_periods = all_periods
    st.header("3. Tolerances")
    with st.expander("How strict each check is", expanded=False):
        tol = dict(TOLERANCES)
        tol["qty_review_pct"] = st.slider("Qty over verified: REVIEW above (%)", 0.0, 10.0, TOLERANCES["qty_review_pct"], 0.25)
        tol["qty_hold_pct"] = st.slider("Qty over verified: HOLD above (%)", 0.0, 20.0, TOLERANCES["qty_hold_pct"], 0.5)
        tol["rate_hold_pct"] = st.slider("Rate over contract: HOLD above (%)", 0.0, 5.0, TOLERANCES["rate_hold_pct"], 0.1)
        tol["pct_review_pts"] = st.slider("Lump-sum % over verified: REVIEW above (pts)", 0.0, 10.0, TOLERANCES["pct_review_pts"], 0.5)
        tol["pct_hold_pts"] = st.slider("Lump-sum % over verified: HOLD above (pts)", 0.0, 20.0, TOLERANCES["pct_hold_pts"], 0.5)
        tol["tm_hold_pct"] = st.slider("T&M hours over approved: HOLD above (%)", 0.0, 30.0, TOLERANCES["tm_hold_pct"], 1.0)
        cap = st.number_input("Per diem cap ($/worker-day)", value=PER_DIEM_CAP, step=1.0)

if not (f_projects and f_primes and f_periods):
    st.warning("Pick at least one project, one contractor and one month.")
    st.stop()


@st.cache_data(show_spinner="Checking invoices...")
def run_cached(_tables, key, tol_items, cap):
    return run(tolerances=dict(tol_items), tables=_tables, per_diem_cap=cap)


data_key = (source, tuple(sorted((k, len(v), float(pd.util.hash_pandas_object(v, index=False).sum()))
                                 for k, v in tables.items())))
exceptions, gates = run_cached(tables, data_key, tuple(sorted(tol.items())), cap)
gf, ef, ids = filter_scope(tables, gates, exceptions, f_projects, f_primes, f_periods)
summary = project_summary(tables, gates, ids, f_projects, f_primes, f_periods)
trend = prime_trend(gf)
spread = rate_spread(tables, f_projects, f_primes)
insights = generate_insights(tables, gf, ef, summary, trend, spread)

# ---------------- KPIs ----------------
k = st.columns(6)
k[0].metric("Projects in view", f"{len(summary)}")
k[1].metric("Billed (gross)", money(gf.gross_amount.sum()))
k[2].metric("✓ First-pass rate", f"{100 * (gf.gate == 'PASS').mean():.0f}%" if len(gf) else "-")
k[3].metric("✕ Invoices on hold", f"{(gf.gate == 'HOLD').sum()} of {len(gf)}")
k[4].metric("Amount at risk", money(gf.amount_at_risk.sum()))
k[5].metric("Pending change orders", money(summary.pending_co.sum()) if len(summary) else "$0")

tabs = st.tabs(["This week's decisions", "Portfolio", "Contractors", "Invoices", "Exceptions", "Accuracy & testing"])

# ---------------- Decisions ----------------
with tabs[0]:
    st.subheader("This week's decisions")
    st.caption("The most important findings for the projects, contractors and months selected in the sidebar, "
               "ranked by urgency and dollar impact.")
    if not insights:
        st.success("Nothing needs a decision in this view.")
    brief = ["# This week's decisions", "",
             f"Scope: {len(f_projects)} project(s), {len(f_primes)} contractor(s), {f_periods[0]} to {f_periods[-1]}", ""]
    for i, d in enumerate(insights, 1):
        with st.container(border=True):
            c1, c2 = st.columns([1, 7])
            c1.markdown(LEVEL[d["level"]])
            c2.markdown(f"**{d['title']}**  \n{d['detail']}  \n*Recommended action:* {d['action']}")
        brief += [f"{i}. **{d['title']}**", f"   - {d['detail']}", f"   - Action: {d['action']}", ""]
    st.download_button("Download this brief (Markdown)", "\n".join(brief), "decisions_brief.md")

# ---------------- Portfolio ----------------
with tabs[1]:
    st.subheader("Portfolio")
    st.caption("Contract value includes approved change orders. 'Verified' is the field-verified value of work in place. "
               "Billed excludes invoices flagged as duplicates.")
    rows = [summary.iloc[i:i + 3] for i in range(0, len(summary), 3)]
    for chunk in rows:
        cols = st.columns(3)
        for col, (_, p) in zip(cols, chunk.iterrows()):
            with col.container(border=True):
                st.markdown(f"**{p.project_id}** · {p.get('campus', '')}  \n{STATUS[p.status]}")
                a, b = st.columns(2)
                a.metric("Contract value", money(p.contract_value))
                b.metric("Billed (work)", f"{p.pct_billed:.0f}%")
                a.metric("Verified complete", f"{p.pct_verified:.0f}%")
                b.metric("At risk", money(p.amount_at_risk))
                st.caption(f"{p.risk_pct:.1f}% of billing at risk · first-pass rate {p.first_pass_pct:.0f}% · {p.on_hold} on hold · "
                           f"pending COs {money(p.pending_co)} · last billed {p.last_period}")
    long = summary.melt(id_vars="project_id", value_vars=["contract_value", "billed_work", "verified_sov"],
                        var_name="measure", value_name="value")
    long["measure"] = long.measure.map({"contract_value": "Contract value", "billed_work": "Billed (work)",
                                        "verified_sov": "Verified work in place"})
    long["value_m"] = long.value / 1e6
    order = ["Contract value", "Billed (work)", "Verified work in place"]
    bars = (alt.Chart(long).mark_bar(cornerRadiusEnd=4, stroke="#ffffff", strokeWidth=2)
            .encode(x=alt.X("project_id:N", title=None),
                    xOffset=alt.XOffset("measure:N", sort=order),
                    y=alt.Y("value_m:Q", title="$ millions"),
                    color=alt.Color("measure:N", sort=order, scale=alt.Scale(domain=order, range=SERIES[:3]),
                                    legend=alt.Legend(orient="top", title=None)),
                    tooltip=["project_id", "measure", alt.Tooltip("value_m:Q", format=",.1f", title="$M")])
            .properties(height=320))
    st.altair_chart(bars, width="stretch")
    show = summary[["project_id", "status", "contract_value", "billed_work", "pct_billed", "verified_sov", "pct_verified",
                    "billed_ahead_of_verified", "billed_tm_per_diem", "amount_at_risk", "risk_pct", "first_pass_pct",
                    "on_hold", "pending_co"]]
    st.dataframe(show, width="stretch", hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="dollar") for c in
        ["contract_value", "billed_work", "verified_sov", "billed_ahead_of_verified", "billed_tm_per_diem",
         "amount_at_risk", "pending_co"]})

# ---------------- Contractors ----------------
with tabs[2]:
    st.subheader("Contractors")
    sc = scorecard(gf, ef, tables.get("primes"))
    st.dataframe(sc, width="stretch", hide_index=True, column_config={
        "billed_gross": st.column_config.NumberColumn(format="dollar"),
        "amount_at_risk": st.column_config.NumberColumn(format="dollar")})
    if len(trend) and trend.period.nunique() > 1:
        tr = trend.assign(contractor=trend.prime_id.map(lambda p: names.get(p, p)))
        dom = [names.get(p, p) for p in all_primes]
        line = (alt.Chart(tr).mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=2)
                .encode(x=alt.X("period:O", title=None, axis=alt.Axis(labelAngle=0)),
                        y=alt.Y("first_pass_pct:Q", title="First-pass rate (%)", scale=alt.Scale(domain=[0, 100])),
                        color=alt.Color("contractor:N", scale=alt.Scale(domain=dom, range=SERIES[:len(dom)]),
                                        legend=alt.Legend(orient="top", title=None)),
                        tooltip=["contractor", "period", "first_pass_pct"])
                .properties(height=300, title="First-pass rate by month (higher is better)"))
        st.altair_chart(line, width="stretch")
    st.markdown("**Where each contractor's money at risk comes from**")
    e = ef[ef.amount_at_risk > 0].merge(gf[["invoice_id", "prime_id"]], on="invoice_id")
    if len(e):
        piv = (e.assign(issue=e.rule.map(lambda r: RULE_LABEL.get(r, r)),
                        contractor=e.prime_id.map(lambda p: names.get(p, p)))
               .pivot_table(index="issue", columns="contractor", values="amount_at_risk", aggfunc="sum", fill_value=0))
        st.dataframe(piv.round(0), width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="dollar") for c in piv.columns})
    st.markdown("**Same item, different price** (contract rates across projects)")
    if len(spread):
        sp = spread.assign(contractor=spread.prime_id.map(lambda p: names.get(p, p)))
        st.dataframe(sp[["contractor", "item_code", "description", "unit", "lowest_rate", "lowest_at",
                         "highest_rate", "highest_at", "spread_pct", "excess_vs_lowest"]],
                     width="stretch", hide_index=True, column_config={
                         "lowest_rate": st.column_config.NumberColumn(format="dollar"),
                         "highest_rate": st.column_config.NumberColumn(format="dollar"),
                         "excess_vs_lowest": st.column_config.NumberColumn(format="dollar")})
    else:
        st.caption("Needs the same contractor on at least two projects.")

# ---------------- Invoices ----------------
with tabs[3]:
    f = st.multiselect("Show gates", ["PASS", "REVIEW", "HOLD"], default=["HOLD", "REVIEW"])
    view = gf[gf.gate.isin(f)].sort_values("amount_at_risk", ascending=False)
    st.dataframe(view, width="stretch", hide_index=True)
    if len(view):
        pick = st.selectbox("Open an invoice", view.invoice_id)
        st.markdown(f"**{pick}**: {GATE_LABEL[view.set_index('invoice_id').at[pick, 'gate']]}")
        lines = tables["invoice_lines"]
        st.dataframe(lines[lines.invoice_id == pick], width="stretch", hide_index=True)
        st.dataframe(ef[ef.invoice_id == pick], width="stretch", hide_index=True)

# ---------------- Exceptions ----------------
with tabs[4]:
    rules = sorted(ef.rule.unique()) if len(ef) else []
    pick_rules = st.multiselect("Rules", rules, default=rules)
    ev = ef[ef.rule.isin(pick_rules)]
    st.dataframe(ev, width="stretch", hide_index=True)
    st.download_button("Download exceptions (CSV)", ev.to_csv(index=False), "exceptions.csv")
    st.download_button("Download invoice gates (CSV)", gf.to_csv(index=False), "invoice_gates.csv")

# ---------------- Accuracy & testing ----------------
with tabs[5]:
    st.markdown("#### Accuracy against the answer key")
    if "ground_truth_errors" in raw:
        truth = raw["ground_truth_errors"]
        if len(truth) == 0:
            st.info("This dataset has an empty answer key (no planted errors). Every exception here would be a false alarm.")
            st.metric("False alarms", len(exceptions))
        else:
            def ks(df, col):
                return set(zip(df.invoice_id.astype(str), pd.to_numeric(df.line_no, errors="coerce").fillna(-1).astype(int), df[col]))
            det, tru = ks(exceptions, "rule"), ks(truth, "error_type")
            acc = []
            for r in sorted({x[2] for x in tru}):
                d, t_ = {x for x in det if x[2] == r}, {x for x in tru if x[2] == r}
                tp = len(d & t_)
                acc.append({"rule": r, "planted": len(t_), "caught": tp, "missed": len(t_ - d),
                            "false_alarms": len(d - t_), "recall_%": round(100 * tp / len(t_), 1),
                            "precision_%": round(100 * tp / len(d), 1) if d else None})
            st.dataframe(pd.DataFrame(acc), width="stretch", hide_index=True)
            st.caption("Covers the whole dataset, not just the filtered view. Move the tolerance sliders to see the trade-off.")
    else:
        st.info("No answer key (ground_truth_errors.csv) in this dataset. Use the stress test below to create one.")

    st.markdown("#### Stress test")
    st.markdown("Plants known errors into a **copy** of the current data, reruns the engine, and reports "
                "what was caught, what was missed, and any new false alarms. Use it to test real data that has no answer key.")
    c1, c2, c3 = st.columns(3)
    n_err = c1.number_input("Errors to plant", 5, 200, 40, 5)
    subtle = c2.slider("Share of tiny errors", 0.0, 1.0, 0.25, 0.05)
    seed = c3.number_input("Random seed", 1, 9999, 1)
    if st.button("Run stress test"):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "data", Path(tmp) / "stress"
            src.mkdir()
            for name, df in tables.items():
                if name in SCHEMA:
                    coerce(df, name).to_csv(src / f"{name}.csv", index=False)
            res = subprocess.run([sys.executable, str(ROOT / "src" / "inject_errors.py"), "--data", str(src),
                                  "--out", str(dst), "--n", str(n_err), "--subtle", str(subtle), "--seed", str(seed)],
                                 capture_output=True, text=True, cwd=str(ROOT / "src"))
            if res.returncode != 0:
                st.error(res.stderr[-2000:])
            else:
                report = (dst / "stress_test_report.md").read_text()
                st.markdown(report.replace("\n## ", "\n##### ").replace("# Stress test report", "#### Stress test report"))
