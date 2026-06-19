"""CSS injection for Savant-style percentile sliders."""

from __future__ import annotations

import streamlit as st

PERCENTILE_SLIDER_CSS = """
<style>
/* Savant-style red (0) → blue (100) gradient track */
div[data-testid="stSlider"][data-baseweb="slider"] div[data-testid="stThumbValue"],
div[data-testid="stSlider"] div[data-baseweb="slider"] div[data-testid="stTickBarMin"],
div[data-testid="stSlider"] div[data-baseweb="slider"] div[data-testid="stTickBarMax"] {
    color: var(--text-color);
    font-size: 0.85rem;
}

.percentile-slider div[data-baseweb="slider"] > div > div {
    background: linear-gradient(
        90deg,
        #d7191c 0%,
        #fdae61 25%,
        #ffffbf 50%,
        #abd9e9 75%,
        #2c7bb6 100%
    ) !important;
}

.percentile-slider div[data-baseweb="slider"] > div > div > div {
    background: transparent !important;
}

.percentile-slider label {
    font-weight: 600;
    color: var(--text-color);
}

/* Theme-aware player cards (fixes white-on-white in dark mode) */
.stMarkdown .player-card {
    color: var(--text-color);
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    background-color: var(--secondary-background-color);
}

.stMarkdown .player-card h3 {
    color: var(--text-color) !important;
    margin: 0 0 0.25rem 0;
    font-size: 1.35rem;
}

.stMarkdown .player-card .meta {
    color: var(--text-color);
    opacity: 0.72;
    font-size: 0.9rem;
    margin-bottom: 0.75rem;
}

.metric-pill {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    margin-right: 0.35rem;
    border-radius: 999px;
    background-color: var(--secondary-background-color);
    color: var(--text-color);
    border: 1px solid rgba(128, 128, 128, 0.35);
    font-size: 0.8rem;
}
</style>
"""


def inject_savant_styles() -> None:
    st.markdown(PERCENTILE_SLIDER_CSS, unsafe_allow_html=True)
