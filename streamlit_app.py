import httpx
import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="MCP Token Management Console",
    page_icon="🔑",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_css() -> None:
    """Load Google Fonts and the external stylesheet."""
    css_path = Path(__file__).parent / ".streamlit" / "streamlit_styles.css"
    css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    html_content = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
{css_content}
</style>
"""
    st.html(html_content)

_load_css()

if "token" not in st.session_state:
    st.session_state.token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "api_url" not in st.session_state:
    st.session_state.api_url = "http://localhost:8004"
if "logout_reason" not in st.session_state:
    st.session_state.logout_reason = None

API_BASE_URL = st.session_state.api_url


@st.cache_data(ttl=10)
def check_api_health(_api_url: str) -> str:
    """
    Check the API health endpoint with a 10-second cache.

    The leading underscore in ``_api_url`` tells Streamlit not to hash
    the parameter (it's used only for cache-busting when the URL changes).
    """
    try:
        response = httpx.get(f"{_api_url}/api/health", timeout=3.0)
        if response.status_code == 200:
            return response.json().get("status", "healthy")
    except Exception:
        pass
    return "offline"


def render_status_indicator(label: str, status: str) -> None:
    """
    Render a status indicator pill with a pulsing dot.

    Args:
        label: Text label shown on the left side (e.g. 'Connection Status').
        status: One of 'healthy', 'degraded', or 'offline'.
    """
    css_class = {
        "healthy": "online",
        "degraded": "degraded",
    }.get(status, "offline")

    title = css_class.capitalize()

    st.markdown(
        f"""
        <div class="status-container">
            <span class="status-text">{label}</span>
            <span class="status-dot {css_class}" title="{title}"></span>
        </div>
        """,
        unsafe_allow_html=True,
    )
def handle_unauthorized(status_code: int) -> None:
    """Clear session data and store a logout reason, redirecting to the login screen."""
    if status_code == 401:
        st.session_state.token = None
        st.session_state.user_email = None
        st.session_state.logout_reason = "Your session has expired. Please sign in again."
        st.rerun()

if st.session_state.token is None:
    with st.sidebar:
        st.markdown("### 🌐 API Connection Settings")
        new_url = st.text_input("FastAPI Base URL", value=API_BASE_URL, key="login_api_url_input")
        if new_url != API_BASE_URL:
            st.session_state.api_url = new_url.strip()
            st.rerun()

        st.markdown("---")
        health = check_api_health(API_BASE_URL)
        render_status_indicator("Connection Status", health)

    col_left, col_center, col_right = st.columns([1, 1.8, 1])
    with col_center:
        if st.session_state.logout_reason:
            st.error(st.session_state.logout_reason)
            st.session_state.logout_reason = None

        with st.form("login_form", clear_on_submit=False):
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <div style="font-size: 3rem; filter: drop-shadow(0 0 15px rgba(99, 102, 241, 0.45)); margin-bottom: 1rem; display: inline-block;">🔑</div>
                    <h2 style="font-size: 1.8rem; font-weight: 800; color: #ffffff; margin-bottom: 0.5rem; letter-spacing: -0.025em; font-family: 'Outfit', sans-serif; border: none; padding: 0;">MCP Token Console</h2>
                    <p style="color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 0;">Authenticate with your admin account credentials to generate and audit collection scopes.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            email = st.text_input("Admin Email Address", placeholder="name@example.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submit_btn = st.form_submit_button("Sign In to Console", use_container_width=True)

            if submit_btn:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    try:
                        with st.spinner("Authenticating..."):
                            response = httpx.post(
                                f"{API_BASE_URL}/auth/login",
                                json={"email": email, "password": password},
                                timeout=10.0,
                            )
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.token = data["access_token"]
                            st.session_state.user_email = email
                            st.success("Successfully logged in!")
                            st.rerun()
                        else:
                            st.error(f"Login failed: {response.json().get('detail', 'Invalid credentials')}")
                    except Exception as exc:
                        st.error(f"Could not connect to API server: {exc}")
                        st.info(f"Double check that the FastAPI service is running on port {API_BASE_URL.split(':')[-1]}")


else:
    health = check_api_health(API_BASE_URL)

    with st.sidebar:
        st.markdown("### 🖥️ Console Session")
        render_status_indicator("FastAPI Gateway", health)

        st.markdown(
            f"""
            <div class="user-profile">
                <div style="font-size: 0.725rem; text-transform: uppercase; letter-spacing: 0.05em; color: #818cf8; font-weight:600;">Logged In User</div>
                <div class="user-email">📧 {st.session_state.user_email}</div>
                <div style="font-size: 0.725rem; color: #64748b; margin-top: 0.5rem; font-weight:500;">Role: System Admin</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.sidebar.expander("⚙️ Connection Settings"):
            new_url = st.text_input("FastAPI Base URL", value=API_BASE_URL, key="dashboard_api_url_input")
            if new_url != API_BASE_URL:
                st.session_state.api_url = new_url.strip()
                st.rerun()

        st.markdown("---")
        if st.sidebar.button("Log Out of Console", type="primary", use_container_width=True):
            try:
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                httpx.post(f"{API_BASE_URL}/auth/logout", headers=headers, timeout=5.0)
            except Exception:
                pass
            st.session_state.token = None
            st.session_state.user_email = None
            st.rerun()

    st.markdown(
        """
        <div class="dashboard-header">
            <h1 class="dashboard-title">🔑 Access Token Controller</h1>
            <p class="dashboard-subtitle">Provision, audit, and revoke utility-wise collection scopes for the Notion Ingestion MCP Gateway</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if health == "offline":
        st.error("🚨 Critical Error: Cannot connect to the API backend. Token generation and metadata lookup will not work.")

    col_gen, col_guide = st.columns([1.2, 0.8])

    with col_gen:
        st.markdown('<div class="glass-card"><h3>✨ Mint Scope Access Token</h3>', unsafe_allow_html=True)

        db_collections = []
        try:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            response = httpx.get(f"{API_BASE_URL}/api/token/collections", headers=headers, timeout=5.0)
            if response.status_code == 200:
                db_collections = response.json()
            elif response.status_code == 401:
                handle_unauthorized(response.status_code)
        except Exception:
            pass

        options_list = ["All Collections (*)"] + db_collections + ["Custom Collection..."]
        collection_sel = st.selectbox(
            "Select Target Collection Scope",
            options=options_list,
            help="Choose the vector database collection this token is allowed to read. Wildcard (*) allows all collections.",
        )

        collection_name = ""
        if collection_sel == "Custom Collection...":
            collection_name = st.text_input("Enter Custom Collection Name", placeholder="e.g. workspace_documentation").strip()
        elif collection_sel == "All Collections (*)":
            collection_name = "*"
        else:
            collection_name = collection_sel

        duration_days = st.radio(
            "Access Expiry Period",
            options=[30, 60, 90],
            format_func=lambda x: f"{x} Days Validity",
            horizontal=True,
            help="The duration in days before this token automatically expires.",
        )

        generate_btn = st.button("Generate Secure Token", type="primary", use_container_width=True)

        if generate_btn:
            if not collection_name:
                st.error("Error: Please specify a valid collection scope name.")
            else:
                try:
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    payload = {"collection_name": collection_name, "expires_days": duration_days}

                    with st.spinner("Cryptographically generating token and saving record..."):
                        response = httpx.post(
                            f"{API_BASE_URL}/api/token/generate",
                            json=payload,
                            headers=headers,
                            timeout=10.0,
                        )

                    if response.status_code == 200:
                        res_data = response.json()
                        st.success(f"Successfully generated token for scope '{collection_name}'!")

                        st.markdown('<div class="vault-box">', unsafe_allow_html=True)
                        st.markdown(
                            """
                            <div style="font-size: 0.8rem; text-transform: uppercase; color: #10b981; font-weight: 700; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.35rem;">
                                <span>🛡️ Secure Decoded Credential</span>
                            </div>
                            <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.75rem;">
                                Copy this token. Any existing token for this collection scope has been invalidated.
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.code(res_data["token"], language="text")

                        st.markdown(
                            f"""
                            <div style="font-size: 0.85rem; color: #cbd5e1; margin-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.75rem;">
                                <strong>Scope:</strong> <code>{res_data['collection_name']}</code> &nbsp;|&nbsp;
                                <strong>Duration:</strong> <code>{res_data['duration_days']} days</code><br>
                                <strong>Expires:</strong> <code>{res_data['expires_at']}</code>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.markdown('</div>', unsafe_allow_html=True)
                    elif response.status_code == 401:
                        handle_unauthorized(response.status_code)
                    else:
                        st.error(f"Generation failed: {response.json().get('detail', 'Unknown error')}")
                except Exception as exc:
                    st.error(f"Error during API call: {exc}")

        st.markdown('</div>', unsafe_allow_html=True)

    with col_guide:
        st.markdown('<div class="glass-card"><h3>💡 Scope & Integration Guide</h3>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="guide-container">
                <div class="guide-row">
                    <span class="guide-icon">✦</span>
                    <div class="guide-text">
                        <strong>Utility-wise Restriction</strong>: Each token grants query access <em>only</em> to the collection name configured in its claims.
                    </div>
                </div>
                <div class="guide-row">
                    <span class="guide-icon">✦</span>
                    <div class="guide-text">
                        <strong>Automatic Invalidation</strong>: Generating a new token for an existing collection name automatically invalidates all previous tokens for that scope.
                    </div>
                </div>
                <div class="guide-row">
                    <span class="guide-icon">✦</span>
                    <div class="guide-text">
                        <strong>HTTP Authorization</strong>: Pass this token in your MCP Client headers:
                        <pre style="margin-top: 0.5rem; background: rgba(0,0,0,0.3); padding: 0.5rem; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); font-family: monospace; font-size: 0.85rem;">Authorization: Bearer &lt;TOKEN&gt;</pre>
                    </div>
                </div>
                <div class="guide-row">
                    <span class="guide-icon">✦</span>
                    <div class="guide-text">
                        <strong>Database Obfuscation</strong>: Tokens are encrypted in the PostgreSQL schema. The console reversibly decodes them for administrative auditing.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### 📋 Credential Audit Log & Registry")

    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    try:
        response = httpx.get(f"{API_BASE_URL}/api/token/list", headers=headers, timeout=10.0)
        if response.status_code == 200:
            tokens_list = response.json()

            if not tokens_list:
                st.info("No credentials have been generated yet in this database.")
            else:
                # Search and Filters
                col_filt_1, col_filt_2 = st.columns([1.8, 1.2])

                with col_filt_1:
                    search_query = st.text_input("🔍 Search Scopes", placeholder="Filter by collection name...")
                with col_filt_2:
                    status_filter = st.selectbox("Filter by Status", ["All Statuses", "Active Only", "Revoked Only"])

                formatted_data = []
                for t in tokens_list:
                    token_val = t["token"]
                    token_val = token_val[:12] + "..." + token_val[-12:] if len(token_val) > 24 else token_val

                    is_active = t["is_valid"]
                    status_emoji = "🟢 Active" if is_active else "🔴 Revoked"

                    if status_filter == "Active Only" and not is_active:
                        continue
                    if status_filter == "Revoked Only" and is_active:
                        continue
                    if search_query and search_query.lower() not in t["collection_name"].lower():
                        continue

                    try:
                        created_dt = datetime.datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
                        expires_dt = datetime.datetime.fromisoformat(t["expires_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        created_dt = t["created_at"]
                        expires_dt = t["expires_at"]

                    formatted_data.append({
                        "ID": t["id"],
                        "Collection Scope": t["collection_name"],
                        "Validity Period": f"{t['duration_days']} Days",
                        "Status": status_emoji,
                        "Created At (UTC)": created_dt,
                        "Expires At (UTC)": expires_dt,
                        "Bearer Token": token_val,
                    })

                if not formatted_data:
                    st.info("No token records match the applied search filters.")
                else:
                    df = pd.DataFrame(formatted_data)
                    st.dataframe(
                        df,
                        use_container_width=True,
                        column_config={
                            "ID": st.column_config.NumberColumn(width=60),
                            "Collection Scope": st.column_config.TextColumn(width=220),
                            "Validity Period": st.column_config.TextColumn(width=130),
                            "Status": st.column_config.TextColumn(width=120),
                            "Created At (UTC)": st.column_config.TextColumn(width=160),
                            "Expires At (UTC)": st.column_config.TextColumn(width=160),
                            "Bearer Token": st.column_config.TextColumn(width=450),
                        },
                        hide_index=True,
                    )
        elif response.status_code == 401:
            handle_unauthorized(response.status_code)
        else:
            st.error("Failed to load credential list from API gateway.")
    except Exception as exc:
        st.error(f"Could not connect to query audit registry: {exc}")

    st.markdown('<div class="footer">🔑 Notion Ingestion Service Admin Console • Built with Streamlit</div>', unsafe_allow_html=True)
