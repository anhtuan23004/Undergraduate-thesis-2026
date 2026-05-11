"""Brand theme injection for the Streamlit UI."""

from __future__ import annotations

import streamlit as st


def render_brand_theme() -> None:
    """Inject brand-aligned styling for spacing and visual consistency."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap');

        :root {
            --brand-primary: #1B8DB6;
            --brand-accent: #34A2CA;
            --brand-bg-soft: #15232D;
            --brand-border: #2D4656;
            --brand-success: #1E8E5A;
            --brand-danger: #C23B35;
            --brand-warning: #BC7A00;
        }

        html, body, [class*="css"] {
            font-family: "Be Vietnam Pro", sans-serif;
        }

        .stApp {
            background:
                radial-gradient(1200px 420px at -10% -20%, rgba(52, 162, 202, 0.14), transparent 62%),
                radial-gradient(1000px 380px at 110% 0%, rgba(27, 141, 182, 0.12), transparent 56%),
                linear-gradient(180deg, #0A1117 0%, #0E171F 55%, #121E27 100%);
            color: #E7F2F8;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0A3E55 0%, #0F4B64 100%);
        }

        [data-testid="stSidebar"] * {
            color: #F3FBFF !important;
        }

        [data-testid="stMarkdownContainer"],
        [data-testid="stText"],
        [data-testid="stCaptionContainer"] {
            color: #E7F2F8;
        }

        div[data-testid="stForm"],
        div[data-testid="stVerticalBlock"] div[data-testid="stContainer"] {
            background: rgba(15, 28, 38, 0.58);
            border-radius: 12px;
        }

        div[data-testid="stMetric"] {
            background: var(--brand-bg-soft);
            border: 1px solid var(--brand-border);
            border-radius: 12px;
            padding: 10px 12px;
            color: #E7F2F8;
        }

        div[data-testid="stButton"] > button[kind="primary"] {
            background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
            border: none;
            border-radius: 10px;
            color: #ffffff;
            font-weight: 600;
        }

        div[data-testid="stButton"] > button {
            border-radius: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
