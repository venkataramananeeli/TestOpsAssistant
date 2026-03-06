"""
TestOps Conversational Agent App

A Streamlit app that lets users interact with TestOps data via natural language prompts.
Uses CustomAgent to interpret intents and execute DB queries conversationally.
"""

import os
from typing import Optional
import streamlit as st
import pandas as pd

from modules.database_engine import DatabaseEngine
from modules.agent import QueryAgent, AgentResponse

# =========================================================
# Page Setup
# =========================================================
st.set_page_config(page_title="Agent", layout="wide")
st.markdown("<h1>🤖 Agent</h1>", unsafe_allow_html=True)
st.caption("Ask questions about your test suites and scripts in natural language.")

# Inject minimal CSS for a cleaner, demo-ready look
st.markdown(
        """
        <style>
            .stApp { background-color: #f7fafc; }
            h1 { font-family: 'Segoe UI', Roboto, Helvetica, Arial; font-weight:700; }
            .card { background: white; border-radius: 10px; padding: 12px; box-shadow: 0 2px 8px rgba(16,24,40,0.04); }
            .quick-btn { width:100%; font-weight:600; }
            .stDownloadButton > button { background-color:#0369a1; color: white; }
        </style>
        """,
        unsafe_allow_html=True,
)

# --- Demo header / KPI row ---
kpicol1, kpicol2, kpicol3 = st.columns([1,1,1])

with kpicol1:
    try:
        ls_resp = None
        if st.session_state.get("agent"):
            ls_resp = st.session_state.agent._list_suites()
        total_suites = ls_resp.metadata.get("count") if ls_resp and ls_resp.metadata else "—"
    except Exception:
        total_suites = "—"
    st.markdown(f"<div class='card'><h3 style='margin:4px;'>Total Suites</h3><h2 style='margin:4px;color:#0b5cff;'>{total_suites}</h2></div>", unsafe_allow_html=True)

with kpicol2:
    try:
        last_mod = "—"
        if st.session_state.get("db_engine"):
            rows = st.session_state.db_engine.query("SELECT MAX(modification_date) AS last_mod FROM test_transaction_ids_view;")
            if rows and rows[0]:
                last_mod = rows[0].get("last_mod") or rows[0].get("MAX(modification_date)") or "—"
    except Exception:
        last_mod = "—"
    st.markdown(f"<div class='card'><h3 style='margin:4px;'>Last Modified</h3><div style='margin:4px;'>{last_mod}</div></div>", unsafe_allow_html=True)

with kpicol3:
    db_status = "Connected" if st.session_state.get("db_connected") else "Not Connected"
    st.markdown(f"<div class='card'><h3 style='margin:4px;'>DB Status</h3><h2 style='margin:4px;color:#059669;'>{db_status}</h2></div>", unsafe_allow_html=True)

# =========================================================
# Secrets/ENV helper
# =========================================================
def _has_streamlit_secrets_file() -> bool:
    """Check common Streamlit secrets.toml locations before touching st.secrets."""
    candidates = [
        os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml"),
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
    ]
    return any(os.path.exists(path) for path in candidates)


def _get_secret(section: str, key: str, default=None):
    """Resolve value from env aliases first, then st.secrets, else default."""
    env_aliases = {
        ("mysql", "host"): ["MYSQL_HOST"],
        ("mysql", "port"): ["MYSQL_PORT"],
        ("mysql", "user"): ["MYSQL_USER"],
        ("mysql", "password"): ["MYSQL_PASS", "MYSQL_PASSWORD"],
        ("mysql", "database"): ["MYSQL_DB", "MYSQL_DATABASE"],
        ("mysql", "pool_size"): ["MYSQL_POOL_SIZE"],
    }

    for env_key in env_aliases.get((section, key), [f"{section}_{key}".upper()]):
        val = os.getenv(env_key)
        if val is None or val == "":
            continue
        if key in {"port", "pool_size"}:
            try:
                return int(val)
            except Exception:
                return default
        return val

    # Avoid noisy "No secrets files found" warnings in Docker when secrets.toml is absent.
    if _has_streamlit_secrets_file():
        try:
            if section in st.secrets and key in st.secrets[section]:
                val = st.secrets[section][key]
                if key in {"port", "pool_size"}:
                    try:
                        return int(val)
                    except Exception:
                        return default
                return val
        except Exception:
            pass

    return default


# =========================================================
# Config
# =========================================================
MYSQL_HOST = _get_secret("mysql", "host", "172.21.18.50")
MYSQL_PORT = _get_secret("mysql", "port", 3306)
MYSQL_USER = _get_secret("mysql", "user", None)
MYSQL_PASS = _get_secret("mysql", "password", None)
MYSQL_DB = _get_secret("mysql", "database", None)
MYSQL_POOL_SIZE = _get_secret("mysql", "pool_size", 10)


# =========================================================
# Session Management
# =========================================================
if "db_engine" not in st.session_state:
    st.session_state.db_engine = None

if "agent" not in st.session_state:
    st.session_state.agent = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "db_connected" not in st.session_state:
    st.session_state.db_connected = False


def ensure_db_connected() -> bool:
    """Initialize DB connection and agent if not already done."""
    if st.session_state.db_connected and st.session_state.agent:
        return True

    # Prompt for credentials if missing
    if not (MYSQL_USER and MYSQL_PASS and MYSQL_DB):
        st.warning("🔐 MySQL credentials not configured.")
        st.info("Set MYSQL_USER, and either MYSQL_PASS or MYSQL_PASSWORD, and either MYSQL_DB or MYSQL_DATABASE.")
        return False

    try:
        st.session_state.db_engine = DatabaseEngine(
            MYSQL_HOST,
            MYSQL_USER,
            MYSQL_PASS,
            MYSQL_DB,
            port=MYSQL_PORT,
            pool_size=MYSQL_POOL_SIZE,
        )
        st.session_state.agent = QueryAgent(st.session_state.db_engine)
        st.session_state.db_connected = True
        return True
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        return False


def render_agent_response(response: AgentResponse) -> None:
    """Render an AgentResponse in Streamlit UI."""
    if response.success:
        st.success(response.message)
    else:
        st.error(response.message)
        if response.error:
            st.code(response.error, language="text")

    # Render metadata
    if response.metadata:
        with st.expander("📋 Metadata"):
            st.json(response.metadata)

    # Render data as table
    if response.data and len(response.data) > 0:
        try:
            total_rows = len(response.data)
            st.subheader(f"📊 Results ({total_rows:,} rows)")
            
            # For large datasets, show pagination
            if total_rows > 1000:
                st.info(f"⚠️ Large dataset ({total_rows:,} rows). Showing first 1,000 rows for performance. Download CSV to see all data.")
                df = pd.DataFrame(response.data[:1000])
            else:
                df = pd.DataFrame(response.data)
            
            # Display the table
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Add download button for full dataset
            csv_data = pd.DataFrame(response.data).to_csv(index=False)
            st.download_button(
                label=f"⬇️ Download CSV ({total_rows:,} rows)",
                data=csv_data,
                file_name=f"testops_{response.action}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Error rendering table: {e}")
            # Show a sample of the data for debugging
            if response.data:
                st.warning("Data available but couldn't render as table. Showing sample:")
                st.code(str(response.data[:3]), language="python")
    elif response.data is not None and len(response.data) == 0:
        st.info("✓ Query executed but no records found for the given criteria.")


# =========================================================
# Sidebar: Settings & History
# =========================================================
with st.sidebar:
    st.subheader("⚙️ Settings")
    
    # Connection status
    if st.session_state.db_connected:
        st.success("✅ Database Connected")
    else:
        st.warning("❌ Not Connected")
    
    # Test connection button
    if st.button("🔌 Test Connection"):
        if ensure_db_connected():
            try:
                rows = st.session_state.db_engine.query("SELECT VERSION() AS ver;")
                st.success(f"Connected! MySQL: {rows[0] if rows else 'unknown version'}")
            except Exception as e:
                st.error(f"Query failed: {e}")
        else:
            st.info("Setup DB credentials first.")
    
    st.divider()
    
    # Chat history
    st.subheader("💬 Conversation History")
    if st.button("🗑️ Clear History"):
        st.session_state.chat_history = []
        st.success("History cleared.")
    
    if st.session_state.chat_history:
        with st.expander("View History"):
            for i, msg in enumerate(st.session_state.chat_history, 1):
                st.caption(f"**{i}. {msg['role'].upper()}:** {msg['content'][:60]}...")
    else:
        st.caption("(No history yet)")


# =========================================================
# Main Chat Interface
# =========================================================
st.subheader("💬 Chat with Your Data")
st.caption("Ask me anything about suites, scripts, or data status.")

# Ensure DB is connected before accepting input
if not ensure_db_connected():
    st.stop()

def _handle_quick_action(prompt: str) -> None:
    """Append user message, run agent immediately, and append agent response."""
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.spinner(f"Processing: '{prompt}'..."):
        response = st.session_state.agent.respond(prompt)
    st.session_state.chat_history.append({
        "role": "agent",
        "content": response.message,
        "action": response.action,
        "success": response.success,
        "data": response.data,
    })

# Quick prompts dropdown (run selected prompt immediately)
with st.container():
    prompts = [
        "list suites",
        "show suites",
        "tpreggold",
        "diagnostics",
    ]
    cols = st.columns([3,1])
    with cols[0]:
        sel = st.selectbox("Quick prompts", prompts, index=0)
    with cols[1]:
        if st.button("Run Prompt"):
            _handle_quick_action(sel)

# Chat input
user_input = st.chat_input("Ask me about suites, scripts, or diagnostics...", key="user_input")

# Process user input
if user_input:
    # Add to history
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    # Get agent response
    with st.spinner(f"Processing: '{user_input}'..."):
        response = st.session_state.agent.respond(user_input)
    
    # Add agent response to history
    st.session_state.chat_history.append({
        "role": "agent",
        "content": response.message,
        "action": response.action,
        "success": response.success,
        "data": response.data,  # Store data in history too
    })

st.divider()

# Display conversation in natural order (chronological)
if st.session_state.chat_history:
    st.subheader("💬 Conversation")
    
    for msg in st.session_state.chat_history:
        role = msg["role"].upper()
        content = msg["content"]
        
        if role == "USER":
            with st.chat_message("user"):
                st.write(f"👤 **You:** {content}")
        else:
            with st.chat_message("assistant"):
                status = "✅" if msg.get("success", False) else "❌"
                action = msg.get("action", "response").replace("_", " ").title()
                st.write(f"🤖 **Agent** [{status}] {action}:\n{content}")
                
                # If there's data, render it inline
                if msg.get("data"):
                    try:
                        data = msg.get("data", [])
                        if data and len(data) > 0:
                            st.subheader("📊 Results")
                            
                            total_rows = len(data)
                            # Show pagination for large datasets
                            if total_rows > 1000:
                                st.info(f"⚠️ Large dataset ({total_rows:,} rows). Showing first 1,000 rows.")
                                df = pd.DataFrame(data[:1000])
                            else:
                                df = pd.DataFrame(data)
                            
                            # Display the table
                            st.dataframe(df, use_container_width=True, hide_index=True)
                            
                            # Download button for full dataset
                            csv_data = pd.DataFrame(data).to_csv(index=False)
                            st.download_button(
                                label=f"⬇️ Download CSV ({total_rows:,} rows)",
                                data=csv_data,
                                file_name=f"testops_{msg.get('action', 'export')}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                            )
                    except Exception as e:
                        st.warning(f"Could not render results: {e}")
else:
    st.info("Start by asking a question above!")


# =========================================================
# Footer / Help
# =========================================================
with st.expander("❓ Need Help?"):
    st.markdown("""
    ### Example Prompts:
    
    - **"list suites"** → Fetch distinct suite names
    - **"show suites"** → Get high-level suite overview
    - **"fetch only inactive scripts for suite name tpreggold"** → Inactive scripts for a suite
    - **"fetch only active scripts for suite name tpreggold for owner is tulasi"** → Active scripts for suite + owner
    - **"show inactive scripts for suite name tpreggold owner is tulasi modified after 2025-01-01"** → Combine suite, status, owner, and date filter
    - **"show scripts for suite name tpreggold modified between 2025-01-01 and 2025-03-01"** → Date-range filter
    - **"test database"** → Run connectivity diagnostics
    - **"help"** → Show all supported commands
    
    ### Behind the Scenes:
    
    The **CustomAgent** (in `modules/agent.py`) parses your natural language prompt,
    identifies the intent, and executes the corresponding database query using a
    shared MySQL connection pool.
    
    Each query:
    1. Borrows a DB connection from the pool
    2. Executes the SQL
    3. Returns the connection to the pool
    4. Shows results as a table and CSV download
    """)
