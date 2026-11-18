"""Mission Control (home), Insights (project cards) and Project (deep dive) pages."""
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from insights import RULE_LABEL, money
from health import WEIGHTS, CASH_RULES
from ui import visuals
from ui.theme import SERIES, STATUS, GATE_COLOR, ACCENT

PILL = {"Healthy": "good", "Watch": "warn", "At risk": "crit", "No data": "warn"}
HCOL = {"Healthy": STATUS["good"], "Watch": STATUS["warning"], "At risk": STATUS["critical"], "No data": "#8792a6"}
FLAG_ICON = {"crit": "✕", "warn": "!", "info": "i"}
FLAG_COL = {"crit": "#ff6b6b", "warn": "#fab219", "info": "#7fb8ff"}
STATUS_TO_PIN = {"Healthy": "Green", "Watch": "Amber", "At risk": "Red"}


def ring(score, size=74, label=True):
    s = 0 if pd.isna(score) else max(0, min(100, score))
    col = HCOL["Healthy"] if s >= 80 else HCOL["Watch"] if s >= 60 else HCOL["At risk"]
    r = size / 2 - 6
    circ = 2 * np.pi * r
    txt = "–" if pd.isna(score) else f"{s:.0f}"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<circle cx="{size/2}" cy="{size/2}" r="{r}" stroke="rgba(255,255,255,0.08)" stroke-width="6" fill="none"/>'
            f'<circle cx="{size/2}" cy="{size/2}" r="{r}" stroke="{col}" stroke-width="6" fill="none" stroke-linecap="round" '
            f'stroke-dasharray="{circ * s / 100:.1f} {circ:.1f}" transform="rotate(-90 {size/2} {size/2})" '
            f'style="filter:drop-shadow(0 0 6px {col}88)"/>'
            f'<text x="50%" y="52%" text-anchor="middle" dominant-baseline="middle" fill="#e8eef8" '
            f'font-family="JetBrains Mono, monospace" font-size="{size*0.28:.0f}" font-weight="600">{txt}</text>'
            + (f'<text x="50%" y="74%" text-anchor="middle" fill="#8792a6" font-size="{size*0.11:.0f}" font-family="Space Grotesk, system-ui, sans-serif" letter-spacing="1">HEALTH</text>' if label else "")
            + "</svg>")


def subbars(h):
    out = '<div class="grid4">'
    for k, lab in [("cost", "Cost"), ("schedule", "Schedule"), ("billing", "Billing"), ("cash", "Cash")]:
        v = h.get(f"{k}_score", np.nan)
        col = "#8792a6" if pd.isna(v) else (HCOL["Healthy"] if v >= 80 else HCOL["Watch"] if v >= 60 else HCOL["At risk"])
        w = 0 if pd.isna(v) else v
        out += (f'<div><div class="lbl"><span>{lab}</span><span class="kv">{"–" if pd.isna(v) else f"{v:.0f}"}</span></div>'
                f'<div class="subbar"><div style="width:{w:.0f}%;background:{col}"></div></div></div>')
    return out + "</div>"


def flags_html(flags, n=3):
    if not flags:
        return '<div class="flag" style="color:#3fd13f">✓ No open flags</div>'
    return "".join(f'<div class="flag"><span style="color:{FLAG_COL[l]};font-weight:700">{FLAG_ICON[l]}</span> {t}</div>'
                   for l, t in flags[:n])


def fmt_date(d):
    return d.strftime("%d %b %Y") if pd.notna(d) else "–"


# ---------------------------------------------------------------- Mission Control
def home(ctx):
    st.markdown('<div class="eyebrow">Multi-Prime Commercial Control Tower</div>'
                '<div class="hero-title">Mission Control</div>'
                '<div class="hero-sub">Every active construction program, from orbit to invoice line. Pins mark each '
                'project\'s exact coordinates; color shows its health.</div>', unsafe_allow_html=True)
    snaps = ctx.snapshots
    pts, tour, i = [], [], 0
    for prog in snaps:
        ps = prog["projects"]
        for r in ps.itertuples():
            pts.append({"id": r.project_id, "i": i, "name": r.name, "lat": float(r.latitude), "lng": float(r.longitude),
                        "status": STATUS_TO_PIN.get(r.health_status, "Blue"), "location": r.location})
            i += 1
        lat, lng = float(ps.latitude.mean()), float(ps.longitude.mean())
        span = max(ps.latitude.max() - ps.latitude.min(), ps.longitude.max() - ps.longitude.min())
        tour.append({"lat": lat, "lng": lng, "alt": 0.9, "rotate": True, "ids": [], "program": prog["label"],
                     "title": prog["region"], "coord": f"{abs(lat):.4f}° {'N' if lat >= 0 else 'S'}, {abs(lng):.4f}° {'E' if lng >= 0 else 'W'}",
                     "status": f"{len(ps)} projects · health {prog['health']:.0f}", "color": HCOL[prog["status"]]})
        for r in ps.itertuples():
            tour.append({"lat": float(r.latitude), "lng": float(r.longitude), "alt": max(0.16, span * 0.02), "rotate": False,
                         "ids": [r.project_id], "program": prog["label"], "title": f"{r.name}: {r.location}",
                         "coord": f"{abs(r.latitude):.4f}° {'N' if r.latitude >= 0 else 'S'}, {abs(r.longitude):.4f}° {'E' if r.longitude >= 0 else 'W'}",
                         "status": f"{r.health_status} · {r.health:.0f}" if pd.notna(r.health) else "No data",
                         "color": HCOL.get(r.health_status, ACCENT)})
    visuals.globe(pts, tour, height=540)

    tot_value = sum(p["committed"] for p in snaps)
    c = st.columns(4)
    c[0].metric("Programs", len(snaps))
    c[1].metric("Active sites", sum(len(p["projects"]) for p in snaps))
    c[2].metric("Committed value", money(tot_value))
    c[3].metric("Sites at risk", sum(int((p["projects"].health_status == "At risk").sum()) for p in snaps))

    st.markdown("### Programs")
    cols = st.columns(len(snaps))
    for col, prog in zip(cols, snaps):
        with col, st.container(border=True):
            visuals.structure(prog["structure"], prog["progress"], height=150, cell=4, seed=hash(prog["label"]) % 997,
                              label=f'{visuals.STRUCT_LABEL.get(prog["structure"], "")} program')
            st.markdown(
                f'<div style="display:flex;gap:14px;align-items:center">{ring(prog["health"], 80)}'
                f'<div><p class="card-title">{prog["label"]}</p><p class="card-sub">{prog["region"]}</p>'
                f'<span class="pill {PILL[prog["status"]]}">{prog["status"]}</span></div></div>'
                f'<div class="stat-row"><div class="stat"><div class="v">{len(prog["projects"])}</div><div class="k">Projects</div></div>'
                f'<div class="stat"><div class="v">{money(prog["committed"])}</div><div class="k">Committed</div></div>'
                f'<div class="stat"><div class="v">{prog["progress"]*100:.0f}%</div><div class="k">Verified</div></div>'
                f'<div class="stat"><div class="v">{money(prog["blocked"])}</div><div class="k">Blocked</div></div></div>'
                + flags_html(prog["flags"], 2), unsafe_allow_html=True)
            st.button("Open program insights →", key=f"open_{prog['source']}", width="stretch",
                      on_click=ctx.go, args=("insights", prog["source"], None))


# ---------------------------------------------------------------- Insights
def insights(ctx):
    pt, H = ctx.pt, ctx.health
    st.markdown(f'<div class="eyebrow">Insights · {ctx.program_label}</div><div class="hero-title">Project health</div>'
                f'<div class="hero-sub">{ctx.region}. One card per project: health score, what drives it, and what needs '
                f'attention. Open a project for the full analysis.</div>', unsafe_allow_html=True)
    j = pt.merge(H, on="project_id")
    w = j.committed.where(j.health.notna(), 0)
    prog_health = (j.health.fillna(0) * w).sum() / w.sum() if w.sum() else np.nan
    k = st.columns(6)
    k[0].metric("Program health", f"{prog_health:.0f}/100" if pd.notna(prog_health) else "–", "value-weighted", delta_color="off", delta_arrow="off")
    k[1].metric("Committed", money(j.committed.sum()))
    if ctx.has_ctl:
        vac = j.vac.sum()
        k[2].metric("Vs budget", money(abs(vac)), "under budget" if vac >= 0 else "over budget",
                    delta_color="normal" if vac >= 0 else "inverse")
    else:
        k[2].metric("Vs budget", "–")
    ver = 100 * j.verified.sum() / j.committed.sum()
    plan = (j.planned_pct * j.committed).sum() / j.committed.sum() if j.planned_pct.notna().any() else np.nan
    k[3].metric("Verified", f"{ver:.0f}%", f"{ver - plan:+.0f} pts vs plan" if pd.notna(plan) else None)
    k[4].metric("Blocked (HOLD)", money(j.blocked.fillna(0).sum()))
    k[5].metric("Penalty risk", money(j.ld_exposure.fillna(0).sum()) if ctx.has_ctl else "–")

    with st.expander("How the health score works"):
        st.markdown(
            f"""
| Part | Weight | How it's scored |
|---|---|---|
| **Cost** | {WEIGHTS['cost']:.0%} | Budget headroom: 3%+ under budget = 100, falling to 0 at 5% over budget |
| **Schedule** | {WEIGHTS['schedule']:.0%} | The worse of: schedule index (1.00 = 100, 0.70 = 0) and weeks late (−6 points per week) |
| **Billing** | {WEIGHTS['billing']:.0%} | 60% first-pass rate + 40% billing accuracy (−10 points per 1% of billing at risk) |
| **Cash** | {WEIGHTS['cash']:.0%} | 100 minus penalties: {'; '.join(f'{n} × {w:g}' for n, w in CASH_RULES)} |

**80+ Healthy · 60–79 Watch · below 60 At risk.** If a part has no data (e.g., no budget file), the other parts are re-weighted.
""")
    order = j.sort_values("health", na_position="last")
    per_row = 3
    rows = [order.iloc[i:i + per_row] for i in range(0, len(order), per_row)]
    for chunk in rows:
        cols = st.columns(per_row)
        for col, r in zip(cols, chunk.itertuples()):
            with col, st.container(border=True):
                visuals.structure(ctx.structure_of(r.project_id), (r.verified_pct or 0) / 100, height=112, cell=3,
                                  seed=abs(hash(r.project_id)) % 997)
                hs = r.health_status
                st.markdown(
                    f'<div style="display:flex;gap:12px;align-items:center">{ring(r.health, 72)}'
                    f'<div style="flex:1"><p class="card-title">{r.name}</p><p class="card-sub">{r.contractor}<br>{ctx.location_of(r.project_id)}</p>'
                    f'<span class="pill {PILL[hs]}">{hs}</span></div></div>'
                    + subbars(r._asdict())
                    + f'<div class="stat-row"><div class="stat"><div class="v">{r.verified_pct:.0f}%</div><div class="k">Done</div></div>'
                    f'<div class="stat"><div class="v">{"–" if pd.isna(r.planned_pct) else f"{r.planned_pct:.0f}%"}</div><div class="k">Planned</div></div>'
                    f'<div class="stat"><div class="v">{"–" if pd.isna(r.vac) else ("+" if r.vac >= 0 else "−") + money(abs(r.vac))}</div><div class="k">vs budget</div></div>'
                    f'<div class="stat"><div class="v">{fmt_date(r.forecast_finish) if ctx.has_ctl else "–"}</div><div class="k">Forecast finish</div></div></div>'
                    + flags_html(r.alerts, 3), unsafe_allow_html=True)
                st.button("Open project →", key=f"proj_{r.project_id}", width="stretch",
                          on_click=ctx.go, args=("project", None, r.project_id))

    st.markdown("### Program decisions this week")
    for d in ctx.insights[:5]:
        col = {"critical": "#ff6b6b", "warning": "#fab219", "info": "#7fb8ff", "good": "#3fd13f"}[d["level"]]
        st.markdown(f'<div style="border-left:3px solid {col};padding:6px 12px;margin:6px 0;background:rgba(14,21,37,.5);border-radius:6px">'
                    f'<b>{d["title"]}</b><br><span class="muted">{d["action"]}</span></div>', unsafe_allow_html=True)
    st.button("Open full program analytics →", on_click=ctx.go, args=("analytics", None, None))


# ---------------------------------------------------------------- Project
def _period_end(p):
    return pd.Period(p, "M").end_time.normalize()


def project(ctx):
    pt, H = ctx.pt, ctx.health
    ids = list(pt.project_id)
    if not ids:
        st.info("No projects in the current selection.")
        return
    cur = st.session_state.get("project") if st.session_state.get("project") in ids else ids[0]
    pick = st.selectbox("Project", ids, index=ids.index(cur), format_func=lambda p: ctx.labels.get(p, p), label_visibility="collapsed")
    st.session_state["project"] = pick
    r = pt.set_index("project_id").loc[pick]
    h = H.set_index("project_id").loc[pick]
    lat, lng = ctx.coords_of(pick)

    st.markdown(f'<div class="eyebrow">Project · {ctx.program_label}</div><div class="hero-title">{r["name"]}</div>'
                f'<div class="hero-sub">{ctx.full_name_of(pick)} · {r.contractor} · {ctx.location_of(pick)}'
                + (f' · <span class="kv">{lat:.4f}°, {lng:.4f}°</span>' if pd.notna(lat) else "") + "</div>", unsafe_allow_html=True)

    a, b = st.columns([3, 2])
    with a:
        visuals.structure(ctx.structure_of(pick), (r.verified_pct or 0) / 100, height=250, cell=5,
                          seed=abs(hash(pick)) % 997, label=f"{visuals.STRUCT_LABEL.get(ctx.structure_of(pick), '')} · live build")
    with b:
        if pd.notna(lat):
            pin = [{"id": pick, "i": 0, "name": r["name"], "lat": lat, "lng": lng,
                    "status": STATUS_TO_PIN.get(h.health_status, "Blue"), "location": ctx.location_of(pick)}]
            stop = [{"lat": lat, "lng": lng, "alt": 0.22, "rotate": False, "ids": [pick], "program": ctx.program_label,
                     "title": r["name"], "coord": f"{lat:.4f}°, {lng:.4f}°", "status": h.health_status, "color": HCOL[h.health_status]}]
            visuals.globe(pin, stop, height=248)

    # health + KPIs
    c1, c2 = st.columns([1, 3])
    with c1, st.container(border=True):
        st.markdown(f'<div style="display:flex;justify-content:center">{ring(h.health, 128)}</div>'
                    f'<div style="text-align:center;margin:4px 0 8px"><span class="pill {PILL[h.health_status]}">{h.health_status}</span></div>'
                    + subbars(h.to_dict()) + flags_html(h["alerts"], 6), unsafe_allow_html=True)
    with c2:
        k = st.columns(4)
        k[0].metric("Budget", money(r.budget) if ctx.has_ctl else "–")
        k[1].metric("Forecast cost", money(r.eac), (f"{money(abs(r.vac))} {'under' if r.vac >= 0 else 'over'}" if ctx.has_ctl else None),
                    delta_color="normal" if (ctx.has_ctl and r.vac >= 0) else "inverse")
        k[2].metric("Billed", money(r.billed), f"{r.billed_pct:.0f}% of committed", delta_color="off", delta_arrow="off")
        k[3].metric("Verified complete", f"{r.verified_pct:.0f}%", f"{r.verified_pct - r.planned_pct:+.0f} pts vs plan" if pd.notna(r.planned_pct) else None)
        k = st.columns(4)
        k[0].metric("Schedule index", f"{r.spi:.2f}" if pd.notna(r.spi) else "–")
        k[1].metric("Forecast finish", fmt_date(r.forecast_finish) if ctx.has_ctl else "–",
                    f"{r.delay_weeks:.0f} wk late" if ctx.has_ctl and pd.notna(r.delay_weeks) and r.delay_weeks > 0 else None,
                    delta_color="inverse")
        k[2].metric("Penalty exposure", money(r.ld_exposure) if ctx.has_ctl else "–")
        k[3].metric("First-pass rate", f"{r.first_pass_pct:.0f}%" if pd.notna(r.first_pass_pct) else "–")
        k = st.columns(4)
        k[0].metric("Blocked (HOLD)", money(r.blocked if pd.notna(r.blocked) else 0))
        k[1].metric("To check (REVIEW)", money(r.to_check if pd.notna(r.to_check) else 0))
        k[2].metric("Pending changes", money(r.pending_co))
        cr = ctx.cash.set_index("project_id") if len(ctx.cash) else pd.DataFrame()
        rec = cr.paid_needs_recovery.get(pick, np.nan) if "paid_needs_recovery" in cr else np.nan
        k[3].metric("To recover", money(rec) if pd.notna(rec) else "–")

    # progress + forecast
    st.markdown("### Progress and forecast")
    pr = ctx.prog[ctx.prog.project_id == pick].copy()
    pr["date"] = pr.period.map(_period_end)
    long = pr.melt(id_vars="date", value_vars=["planned_pct", "verified_pct", "billed_pct"], var_name="s", value_name="pct").dropna()
    long["s"] = long.s.map({"planned_pct": "Planned", "verified_pct": "Verified", "billed_pct": "Billed"})
    last = pr.dropna(subset=["verified_pct"]).tail(1)
    fc = pd.DataFrame()
    if ctx.has_ctl and len(last) and pd.notna(r.forecast_finish):
        fc = pd.DataFrame({"date": [last.date.iloc[0], r.forecast_finish], "pct": [last.verified_pct.iloc[0], 100.0], "s": "Forecast"})
    dom = ["Planned", "Verified", "Billed", "Forecast"]
    rng_ = [SERIES[3], SERIES[2], SERIES[0], SERIES[6]]
    base = alt.Chart(pd.concat([long, fc])).encode(
        x=alt.X("date:T", title=None), y=alt.Y("pct:Q", title="% complete", scale=alt.Scale(domain=[0, 105])),
        color=alt.Color("s:N", scale=alt.Scale(domain=dom, range=rng_), legend=alt.Legend(orient="top", title=None)),
        strokeDash=alt.condition("datum.s == 'Planned' || datum.s == 'Forecast'", alt.value([5, 4]), alt.value([1, 0])),
        tooltip=["s", alt.Tooltip("date:T", format="%b %Y"), alt.Tooltip("pct:Q", format=".1f")])
    layers = [base.mark_line(strokeWidth=2), base.mark_point(size=50, filled=True)]
    marks = []
    if ctx.has_ctl and pd.notna(r.planned_finish):
        marks.append({"d": r.planned_finish, "t": "Contract finish", "dy": -132})
    if ctx.has_ctl and pd.notna(r.forecast_finish):
        marks.append({"d": r.forecast_finish, "t": "Forecast finish", "dy": -116})
    if marks:
        mk = pd.DataFrame(marks)
        layers.append(alt.Chart(mk).mark_rule(strokeDash=[2, 3], color="#8792a6").encode(x="d:T"))
        for m in marks:
            layers.append(alt.Chart(pd.DataFrame([m])).mark_text(align="left", dx=4, dy=m["dy"], color="#b9c3d3", fontSize=11)
                          .encode(x="d:T", text="t"))
    c1, c2 = st.columns([3, 2])
    c1.altair_chart(alt.layer(*layers).properties(height=320), width="stretch")
    c1.caption("Dashed purple = forecast from the current pace to completion. Billed above Verified = paid ahead of work.")

    # cost bridge
    steps = [("Contract", 0, r.original_contract), ("+ Approved", r.original_contract, r.original_contract + r.approved_co),
             ("+ Pending", r.original_contract + r.approved_co, r.eac), ("Forecast", 0, r.eac)]
    cb = pd.DataFrame([{"step": s, "y0": a_ / 1e6, "y1": b_ / 1e6, "kind": "total" if s in ("Contract", "Forecast") else "change"}
                       for s, a_, b_ in steps])
    cb["label"] = [money(b_ - a_) if k_ == "change" else money(b_) for (s_, a_, b_), k_ in zip(steps, cb.kind)]
    cb["label"] = [("+" if k_ == "change" else "") + l_ for l_, k_ in zip(cb.label, cb.kind)]
    ch = alt.Chart(cb).mark_bar(cornerRadius=3, width=38).encode(
        x=alt.X("step:N", sort=[s for s, *_ in steps], title=None, axis=alt.Axis(labelAngle=0, labelLimit=120, labelOverlap=False)),
        y=alt.Y("y0:Q", title="$ millions"), y2="y1:Q",
        color=alt.Color("kind:N", scale=alt.Scale(domain=["total", "change"], range=[SERIES[0], SERIES[1]]), legend=None),
        tooltip=["step", alt.Tooltip("y1:Q", format=",.3f", title="$M to")])
    cl = [ch, alt.Chart(cb).mark_text(dy=-8, color="#e8eef8", fontSize=11).encode(
        x=alt.X("step:N", sort=[s for s, *_ in steps]), y="y1:Q", text="label")]
    if ctx.has_ctl and pd.notna(r.budget):
        bl = pd.DataFrame({"b": [r.budget / 1e6], "t": [f"Budget {money(r.budget)}"]})
        cl += [alt.Chart(bl).mark_rule(color=STATUS["warning"], strokeDash=[4, 3]).encode(y="b:Q"),
               alt.Chart(bl).mark_text(align="left", x=4, dy=-7, color=STATUS["warning"], fontSize=11).encode(y="b:Q", text="t")]
    c2.altair_chart(alt.layer(*cl).properties(height=320, title="Cost bridge: contract to forecast"), width="stretch")

    # bills by month
    g = ctx.gf[ctx.gf.project_id == pick]
    c1, c2 = st.columns(2)
    if len(g):
        gg = g.groupby(["period", "gate"]).gross_amount.sum().reset_index()
        gg["gate_l"] = gg.gate.map({"PASS": "✓ Pass", "REVIEW": "! Review", "HOLD": "✕ Hold"})
        bm = alt.Chart(gg).mark_bar(stroke="#0e1525", strokeWidth=2, cornerRadiusEnd=3).encode(
            x=alt.X("period:O", title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y("gross_amount:Q", title="Billed ($)"),
            color=alt.Color("gate_l:N", scale=alt.Scale(domain=["✓ Pass", "! Review", "✕ Hold"],
                                                         range=[GATE_COLOR["PASS"], GATE_COLOR["REVIEW"], GATE_COLOR["HOLD"]]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["period", "gate_l", alt.Tooltip("gross_amount:Q", format="$,.0f")]).properties(height=280, title="Bills by month and gate")
        c1.altair_chart(bm, width="stretch")
    e = ctx.ef[ctx.ef.invoice_id.isin(g.invoice_id)]
    e = e[e.amount_at_risk > 0]
    if len(e):
        ei = e.assign(issue=e.rule.map(lambda x: RULE_LABEL.get(x, x))).groupby("issue").amount_at_risk.sum().reset_index()
        ib = alt.Chart(ei).mark_bar(cornerRadiusEnd=4, color=SERIES[1], height=16).encode(
            y=alt.Y("issue:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
            x=alt.X("amount_at_risk:Q", title="Money at risk ($)"),
            tooltip=["issue", alt.Tooltip("amount_at_risk:Q", format="$,.0f")]).properties(height=alt.Step(30), title="Where the money at risk comes from")
        c2.altair_chart(ib, width="stretch")
    else:
        c2.success("No money at risk on this project's bills.")

    # rates vs program median
    st.markdown("### Rates vs program median")
    po = ctx.tables["purchase_orders"]
    pol = ctx.tables["po_lines"].merge(po[["po_id", "project_id"]], on="po_id")
    pol = pol[(pol.line_source == "CONTRACT") & (pol.unit.str.upper() != "LS") & pol.project_id.isin(ctx.pt.project_id)]
    med = pol.groupby(["item_code", "unit"]).contract_unit_rate.median().rename("median")
    shared = pol.groupby(["item_code", "unit"]).project_id.nunique().rename("n_projects")
    mine = pol[pol.project_id == pick].merge(med, on=["item_code", "unit"]).merge(shared, on=["item_code", "unit"])
    mine = mine[mine.n_projects >= 2]
    if len(mine):
        mine = mine.assign(vs_median_pct=100 * (mine.contract_unit_rate / mine["median"] - 1),
                           value=mine.contract_unit_rate * mine.contract_qty)
        top = mine.sort_values("value", ascending=False).head(12)
        rb = alt.Chart(top).mark_bar(cornerRadiusEnd=3, height=14).encode(
            y=alt.Y("description:N", sort=alt.EncodingSortField("value", order="descending"), title=None, axis=alt.Axis(labelLimit=320)),
            x=alt.X("vs_median_pct:Q", title="% vs program median rate"),
            color=alt.condition("datum.vs_median_pct > 0", alt.value(SERIES[1]), alt.value(SERIES[0])),
            tooltip=["item_code", "description", "unit", alt.Tooltip("contract_unit_rate:Q", format="$,.2f"),
                     alt.Tooltip("median:Q", format="$,.2f"), alt.Tooltip("vs_median_pct:Q", format="+.1f")]
        ).properties(height=alt.Step(24), title="Largest items by value (orange = above median)")
        st.altair_chart(rb + alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#8792a6").encode(x="x:Q"), width="stretch")
    else:
        st.caption("No items shared with other projects to compare.")

    # project-level live insights + evidence
    st.markdown("### Live insights")
    name = r["name"]
    mine_ins = [d for d in ctx.insights if name in d["title"] or name in d["detail"] or pick in d["detail"]]
    if not mine_ins and not h["alerts"]:
        st.success("Nothing needs a decision on this project right now.")
    for d in mine_ins[:6]:
        col = {"critical": "#ff6b6b", "warning": "#fab219", "info": "#7fb8ff", "good": "#3fd13f"}[d["level"]]
        st.markdown(f'<div style="border-left:3px solid {col};padding:6px 12px;margin:6px 0;background:rgba(14,21,37,.5);border-radius:6px">'
                    f'<b>{d["title"]}</b><br>{d["detail"]}<br><span class="muted">Action: {d["action"]}</span></div>', unsafe_allow_html=True)
    with st.expander(f"Evidence: {len(g)} bills on this project"):
        view = g.merge(ctx.risk, on="invoice_id", how="left").sort_values("period")
        st.dataframe(view[["invoice_id", "period", "gate", "gross_amount", "blocked", "to_check", "rules_triggered"]],
                     width="stretch", hide_index=True, column_config={
                         "gross_amount": st.column_config.NumberColumn("Billed", format="$%,.0f"),
                         "blocked": st.column_config.NumberColumn("Blocked", format="$%,.0f"),
                         "to_check": st.column_config.NumberColumn("To check", format="$%,.0f")})
    st.caption(f"Data as of {fmt_date(r.data_date) if ctx.has_ctl and pd.notna(r.data_date) else ctx.end_period}. "
               "Figures recalculate whenever the source data changes.")
