import httpx
import datetime
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="MCP Token Management Console",
    page_icon="🔑",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        /* General app styling */
        .main {
            background-color: #0e1117;
            color: #ffffff;
        }
        
        /* Headers and title */
        h1, h2, h3 {
            font-family: 'Outfit', 'Inter', sans-serif;
            font-weight: 700;
        }
        
        .title-container {
            background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
            padding: 2.5rem;
            border-radius: 16px;
            margin-bottom: 2rem;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
            text-align: center;
        }
        .title-text {
            color: #ffffff !important;
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        .subtitle-text {
            color: #e2e8f0;
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        /* Card-like containers */
        .card {
            background-color: #1e293b;
            padding: 2rem;
            border-radius: 12px;
            border: 1px solid #334155;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        /* Status Badges */
        .badge-valid {
            background-color: #065f46;
            color: #34d399;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            display: inline-block;
        }
        .badge-invalid {
            background-color: #7f1d1d;
            color: #f87171;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            display: inline-block;
        }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 2rem;
            color: #64748b;
            font-size: 0.875rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

API_BASE_URL = st.sidebar.text_input("API Service URL", value="http://localhost:8004")

if "token" not in st.session_state:
    st.session_state.token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None

def check_api_health() -> bool:
    try:
        response = httpx.get(f"{API_BASE_URL}/health")
        return response.status_code == 200
    except Exception:
        return False

if st.session_state.token is None:
    st.markdown(
        """
        <div style="max-width: 500px; margin: 4rem auto 2rem auto;">
            <h2 style="text-align: center; color: #4f46e5; margin-bottom: 0.5rem;">🔑 Token Generator Login</h2>
            <p style="text-align: center; color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem;">
                Authenticate with your admin account to manage MCP collection scopes.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email Address", placeholder="name@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        submit_btn = st.form_submit_button("Sign In", use_container_width=True)
        
        if submit_btn:
            if not email or not password:
                st.error("Please fill in both fields.")
            else:
                try:
                    response = httpx.post(
                        f"{API_BASE_URL}/auth/login",
                        json={"email": email, "password": password},
                        timeout=10.0
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
                    st.info("Ensure the FastAPI backend is running (e.g. `uvicorn main:app --reload`).")

else:
    st.sidebar.markdown(f"### 👤 Logged In As:\n`{st.session_state.user_email}`")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.token = None
        st.session_state.user_email = None
        st.rerun()
        
    st.markdown(
        """
        <div class="title-container">
            <h1 class="title-text">🔑 Collection Access Token Manager</h1>
            <p class="subtitle-text">Generate, revoke, and track access credentials for the Notion Ingestion MCP Server</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    if not check_api_health():
        st.warning("⚠️ Warning: Cannot connect to the API health endpoint. Operations may fail.")
        
    col_gen, col_info = st.columns([2, 1])
    
    with col_gen:
        st.markdown('<div class="card"><h3>✨ Generate Collection Bearer Token</h3>', unsafe_allow_html=True)
        
        db_collections = []
        try:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            response = httpx.get(f"{API_BASE_URL}/api/token/collections", headers=headers, timeout=5.0)
            if response.status_code == 200:
                db_collections = response.json()
        except Exception:
            pass

        if not db_collections:
            st.info("No collections found in the database. Please ingest content first to populate collections.")

        options_list = ["All Collections (*)"] + db_collections + ["Custom Collection..."]
        collection_sel = st.selectbox("Select Target Collection Scope", options=options_list)
        
        if collection_sel == "Custom Collection...":
            collection_name = st.text_input("Enter Custom Collection Name", placeholder="e.g. my_custom_docs").strip()
        elif collection_sel == "All Collections (*)":
            collection_name = "*"
        else:
            collection_name = collection_sel
            
        duration_days = st.radio(
            "Token Validity Duration",
            options=[30, 60, 90],
            format_func=lambda x: f"{x} Days",
            horizontal=True
        )
        
        generate_btn = st.button("Generate Token", type="primary", use_container_width=True)
        
        if generate_btn:
            if not collection_name:
                st.error("Please specify a valid collection name.")
            else:
                try:
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    payload = {"collection_name": collection_name, "expires_days": duration_days}
                    
                    with st.spinner("Generating secure token and writing to DB..."):
                        response = httpx.post(
                            f"{API_BASE_URL}/api/token/generate",
                            json=payload,
                            headers=headers,
                            timeout=10.0
                        )
                        
                    if response.status_code == 200:
                        res_data = response.json()
                        st.success(f"Success! Generated token for collection '{collection_name}' valid for {duration_days} days.")
                        
                        st.markdown("#### 🔑 Your Generated Bearer Token:")
                        st.info("⚠️ Make sure to copy this token. Any existing token for this collection has been invalidated.")
                        st.text_area("Bearer Token Value", value=res_data["token"], height=120)
                        
                        st.markdown(
                            f"""
                            **Token Details:**
                            - **Collection Scope:** `{res_data['collection_name']}`
                            - **Validity:** `{res_data['duration_days']} days`
                            - **Created At:** `{res_data['created_at']}`
                            - **Expires At:** `{res_data['expires_at']}`
                            """
                        )
                    else:
                        st.error(f"Generation failed: {response.json().get('detail', 'Unknown error')}")
                except Exception as exc:
                    st.error(f"Error during API call: {exc}")
                    
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_info:
        st.markdown('<div class="card"><h3>💡 Token Usage Guide</h3>', unsafe_allow_html=True)
        st.markdown(
            """
            **How it works:**
            1. **Scope Restriction**: Each token grants access *only* to its designated collection name.
            2. **Single Valid Token Constraint**: Generating a new token for a specific collection automatically marks any previous token for that collection **invalid** in the database.
            3. **Database Obfuscation**: Tokens are securely encoded inside the database (not hashed), meaning the console can reversibly retrieve and list the history for tracking.
            4. **Authentication Header**:
               ```http
               Authorization: Bearer <TOKEN>
               ```
               Pass the generated token in your API queries or MCP server authorization headers.
            """
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### 📋 Generated Tokens Log")
    
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    try:
        response = httpx.get(f"{API_BASE_URL}/api/token/list", headers=headers, timeout=10.0)
        if response.status_code == 200:
            tokens_list = response.json()
            
            if not tokens_list:
                st.info("No tokens generated yet.")
            else:
                reveal_tokens = st.checkbox("Reveal plain JWT tokens in table")
                
                formatted_data = []
                for idx, t in enumerate(tokens_list):
                    token_val = t["token"]
                    if not reveal_tokens:
                        token_val = token_val[:12] + "..." + token_val[-12:] if len(token_val) > 24 else token_val
                        
                    formatted_data.append({
                        "ID": t["id"],
                        "Collection": t["collection_name"],
                        "Duration (Days)": t["duration_days"],
                        "Status": "✅ Valid" if t["is_valid"] else "❌ Invalid",
                        "Created At (UTC)": datetime.datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S"),
                        "Expires At (UTC)": datetime.datetime.fromisoformat(t["expires_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S"),
                        "Token": token_val
                    })
                
                df = pd.DataFrame(formatted_data)
                
                st.dataframe(
                    df,
                    use_container_width=True,
                    column_config={
                        "ID": st.column_config.NumberColumn(width=50),
                        "Collection": st.column_config.TextColumn(width=200),
                        "Duration (Days)": st.column_config.NumberColumn(width=120),
                        "Status": st.column_config.TextColumn(width=100),
                        "Created At (UTC)": st.column_config.TextColumn(width=160),
                        "Expires At (UTC)": st.column_config.TextColumn(width=160),
                        "Token": st.column_config.TextColumn(width=400),
                    },
                    hide_index=True
                )
        else:
            st.error("Failed to load tokens log from API.")
    except Exception as exc:
        st.error(f"Could not connect to list tokens: {exc}")
        
    # Footer
    st.markdown('<div class="footer">🔑 Notion Ingestion MCP Token Server Dashboard • Built with Streamlit</div>', unsafe_allow_html=True)
