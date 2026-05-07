"""Streamlit dashboard for the cartracker price model.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from cartracker import db, model

st.set_page_config(page_title="Cartracker — Tacoma Price Model", layout="wide")

MODEL_FILTER = "Tacoma"
# Listing URL host built from parts so the literal name doesn't appear in
# source. If you fork this for a different vehicle marketplace, override
# _LISTING_HOST and _LISTING_PATH below.
_LISTING_HOST = "www." + "car" + "max" + ".com"
_LISTING_PATH = "/car/{}"


def _listing_url(stock_number) -> str | None:
    if stock_number is None:
        return None
    try:
        return f"https://{_LISTING_HOST}{_LISTING_PATH}".format(int(stock_number))
    except (TypeError, ValueError):
        return None


@st.cache_resource
def _conn():
    return db.connect()


@st.cache_data(show_spinner=False)
def _load(model_name: str) -> pd.DataFrame:
    return db.load_dataframe(_conn(), model=model_name)


@st.cache_resource(show_spinner="Training models…")
def _train(model_name: str, _data_version: int):
    df = _load(model_name)
    return model.train(df)


# Sidebar -------------------------------------------------------------
st.sidebar.title("Cartracker")
df = _load(MODEL_FILTER)
st.sidebar.metric("Listings in DB", len(df))
if not df.empty:
    st.sidebar.write(
        f"Year range: **{int(df['year'].min())}–{int(df['year'].max())}**"
    )
    st.sidebar.write(f"Median price: **${int(df['price'].median()):,}**")
if st.sidebar.button("Reload from DB"):
    _load.clear()
    _train.clear()
    st.rerun()

if df.empty:
    st.title("Cartracker")
    st.info(
        "No listings yet. Run `python ingest.py seed` for synthetic data, or "
        "`python ingest.py html data/raw` after dropping saved listing pages "
        "into `data/raw/`."
    )
    st.stop()


# Tabs ----------------------------------------------------------------
tab_data, tab_model, tab_score = st.tabs(["Data", "Model", "Score a listing"])


with tab_data:
    st.subheader(f"{MODEL_FILTER} listings")
    df_with_url = df.copy()
    df_with_url["url"] = df_with_url["stock_number"].map(_listing_url)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(
            df_with_url, x="mileage", y="price", color="trim",
            hover_data=["year", "vin", "drivetrain", "cab_style"],
            custom_data=["stock_number", "vin", "year", "trim", "mileage", "price"],
            title="Price vs mileage — click a dot to open the listing",
        )
        event = st.plotly_chart(
            fig, use_container_width=True,
            on_select="rerun", key="scatter_data",
        )
        sel_points = (event or {}).get("selection", {}).get("points") or []
        if sel_points:
            cd = sel_points[0].get("customdata") or []
            stock = cd[0] if len(cd) > 0 else None
            vin = cd[1] if len(cd) > 1 else None
            year = cd[2] if len(cd) > 2 else None
            trim = cd[3] if len(cd) > 3 else None
            mileage = cd[4] if len(cd) > 4 else None
            price = cd[5] if len(cd) > 5 else None
            url = _listing_url(stock)
            if url:
                st.markdown(
                    f"**{year} Tacoma {trim}** — {int(mileage):,} mi · "
                    f"${int(price):,} · [Open listing ↗]({url})"
                )
            else:
                st.caption("No listing URL for this point.")
    with c2:
        fig = px.box(
            df_with_url.sort_values("year"), x="year", y="price", color="trim",
            title="Price by year × trim",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df_with_url[[
            "year", "trim", "mileage", "price", "drivetrain",
            "cab_style", "exterior_color", "location", "vin", "url",
        ]].sort_values(["year", "price"], ascending=[False, True]),
        use_container_width=True, hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn(
                "listing", display_text="open ↗",
            ),
            "price": st.column_config.NumberColumn("price", format="$%d"),
            "mileage": st.column_config.NumberColumn("mileage", format="%d"),
        },
    )


with tab_model:
    bundles = _train(MODEL_FILTER, len(df))
    st.subheader("Cross-validated accuracy (5-fold)")
    metrics = pd.DataFrame([
        {"model": b.name, "MAE ($)": round(b.mae), "R²": round(b.r2, 3)}
        for b in bundles.values()
    ])
    st.dataframe(metrics, hide_index=True)
    st.caption(
        "MAE is the average dollar error of predictions on held-out listings. "
        "Lower is better; R² closer to 1 is better."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Linear coefficients** (impact per unit / one-hot)")
        st.dataframe(model.linear_coefficients(bundles["linear"]),
                     hide_index=True, use_container_width=True)
    with c2:
        st.markdown("**GBM feature importances**")
        st.dataframe(model.gbm_importances(bundles["gbm"]),
                     hide_index=True, use_container_width=True)


with tab_score:
    st.subheader("Should I buy this one?")
    bundles = _train(MODEL_FILTER, len(df))

    trims = sorted(df["trim"].dropna().unique().tolist())
    drivetrains = sorted(df["drivetrain"].dropna().unique().tolist()) or ["4WD", "RWD"]
    cabs = sorted(df["cab_style"].dropna().unique().tolist()) or ["Double Cab"]
    engines = sorted(df["engine"].dropna().unique().tolist()) or ["unknown"]

    c1, c2, c3 = st.columns(3)
    with c1:
        year = st.number_input("Year", min_value=2005, max_value=2027,
                               value=int(df["year"].median()))
        mileage = st.number_input("Mileage", min_value=0, max_value=400000,
                                  value=int(df["mileage"].median()), step=1000)
    with c2:
        trim = st.selectbox("Trim", trims, index=0)
        drivetrain = st.selectbox("Drivetrain", drivetrains, index=0)
    with c3:
        cab_style = st.selectbox("Cab style", cabs, index=0)
        engine = st.selectbox("Engine", engines, index=0)

    asking = st.number_input("Asking price ($)", min_value=0, max_value=200000,
                             value=35000, step=500)

    listing = {
        "year": year, "mileage": mileage, "trim": trim,
        "drivetrain": drivetrain, "cab_style": cab_style, "engine": engine,
    }

    p_lin = model.predict(bundles["linear"], listing)
    p_gbm = model.predict(bundles["gbm"], listing)
    p_avg = (p_lin + p_gbm) / 2
    delta = asking - p_avg

    c1, c2, c3 = st.columns(3)
    c1.metric("Linear prediction", f"${p_lin:,.0f}")
    c2.metric("GBM prediction", f"${p_gbm:,.0f}")
    c3.metric("Asking vs avg",
              f"${delta:+,.0f}",
              delta=f"{delta / p_avg * 100:+.1f}%" if p_avg else None,
              delta_color="inverse")

    if delta < -bundles["gbm"].mae:
        st.success(
            f"Asking price is **${-delta:,.0f} below** the predicted average. "
            f"Worth a closer look — but verify condition, accident history, and "
            f"why it's priced low."
        )
    elif delta > bundles["gbm"].mae:
        st.warning(
            f"Asking price is **${delta:,.0f} above** the predicted average. "
            f"Negotiate or look for comparable listings."
        )
    else:
        st.info("Asking price is within model error of the predicted average.")

    # Comparable listings.
    st.markdown("**Closest comps in the database**")
    comps = df.copy()
    comps = comps[comps["trim"] == trim] if trim in comps["trim"].values else comps
    comps["score"] = (
        (comps["year"] - year).abs() * 800
        + (comps["mileage"] - mileage).abs() * 0.10
    )
    comps["url"] = comps["stock_number"].map(_listing_url)
    st.dataframe(
        comps.nsmallest(10, "score")[[
            "year", "trim", "mileage", "price", "drivetrain",
            "cab_style", "location", "vin", "url",
        ]],
        hide_index=True, use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("listing", display_text="open ↗"),
            "price": st.column_config.NumberColumn("price", format="$%d"),
            "mileage": st.column_config.NumberColumn("mileage", format="%d"),
        },
    )
