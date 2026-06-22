import streamlit as st
import uuid
import pandas as pd
from rag import execute_structured_query, ingest_file_bytes, process_urls, generate_visual_dashboard

st.set_page_config(page_title="Real Estate Research Platform", page_icon="🏢", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background-image: linear-gradient(rgba(14, 17, 23, 0.85), rgba(14, 17, 23, 0.85)), 
                         url("https://raw.githubusercontent.com/savera1226/real-estate-intelligence/main/assets/skyscraper.png");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    </style>
    """,
    unsafe_allow_html=True
)
if "tenant_id" not in st.session_state: st.session_state.tenant_id = str(uuid.uuid4())
if "messages" not in st.session_state: st.session_state.messages = []

st.title("🏢 Executive Intelligence Terminal")

with st.sidebar:
    st.header("Ingestion Console")
    files = st.file_uploader("Upload PDF/TXT", accept_multiple_files=True)
    urls_input = st.text_area("Web URLs (one per line)")
    if st.button("Sync Workspace", use_container_width=True):
        with st.spinner("Processing..."):
            if files:
                for f in files: ingest_file_bytes(f.read(), f.name, st.session_state.tenant_id)
            if urls_input.strip():
                process_urls([u.strip() for u in urls_input.splitlines() if u.strip()], st.session_state.tenant_id)
            st.success("Synced!")

# --- NEW: VISUAL DASHBOARD SECTION ---
if st.button("📊 Generate Visual Dashboard (Live + Local)"):
    with st.spinner("Compiling live web data and local vectors..."):
        dash = generate_visual_dashboard(st.session_state.tenant_id)

        st.markdown(f'<div class="metric-card">Live Pulse: {dash["market_summary"]}</div><br>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📈 Rate Trends")
            if dash["trend_chart"]["labels"][0] != "N/A":
                df_trend = pd.DataFrame({"Rate (%)": dash["trend_chart"]["values"]},
                                        index=dash["trend_chart"]["labels"])
                st.line_chart(df_trend)
            else:
                st.warning("Not enough data to plot trends.")

        with col2:
            st.subheader("⚠️ Market Risk Distribution")
            if dash["risk_chart"]["labels"][0] != "N/A":
                df_risk = pd.DataFrame({"Severity (1-10)": dash["risk_chart"]["values"]},
                                       index=dash["risk_chart"]["labels"])
                st.bar_chart(df_risk)
            else:
                st.warning("Not enough data to plot risks.")
st.divider()

# --- CHAT SECTION (Now Hyper-Concise) ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Query live data or local docs..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Analyzing web and local vectors..."):
            res = execute_structured_query(prompt, st.session_state.tenant_id)

            # Formatted to be extremely short and easy to read
            response_text = f"**Answer:** {res['executive_brief']}\n\n**Data Points:**\n"
            for insight in res["key_insights"]: response_text += f"• {insight}\n"

            st.markdown(response_text)
            with st.expander("Sources (Local + Web)"):
                for src in res["sources"]: st.write(f"- {src['source']}")

            st.session_state.messages.append({"role": "assistant", "content": response_text})