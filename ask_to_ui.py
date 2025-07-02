import streamlit as st
import uuid
import json
import pandas as pd
from agent_backend import load_users, create_session, invoke_agent, get_agent_by_name
from dynamodb_backend import save_session_to_dynamodb, load_session_from_dynamodb

# === Page Setup ===
st.set_page_config(page_title="VirtueAI", layout="wide")
st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# === Load users and models ===
users = load_users()
user_names = [user["name"] for user in users]
agent_names = ["nova"]

# === Init session state ===
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
if "session_id" not in st.session_state:
    st.session_state.session_id = None

# === Get session from URL if present ===
query_params = st.query_params
current_id = query_params.get("session")
if current_id:
    st.session_state.session_id = current_id

# === Load session from DynamoDB or initialize ===
if st.session_state.session_id and st.session_state.session_id not in st.session_state.sessions:
    found = False
    for user in users:
        session_data = load_session_from_dynamodb(user["name"], st.session_state.session_id)
        if session_data:
            st.session_state.sessions[st.session_state.session_id] = {
                "session_id": st.session_state.session_id,
                "chat_history": session_data.get("chat_history", []),
                "context": session_data.get("context", ""),
                "model": session_data.get("model", ""),
                "agent_info": session_data.get("agent_info", {}),
                "user": session_data.get("user", user["name"])
            }
            found = True
            break

    if not found:
        default_user = users[0] if users else {}
        user_obj = next((u for u in users if u["name"] == default_user.get("name")), default_user)
        user_context = (
            "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
            + json.dumps(user_obj, indent=2)
        )
        st.session_state.sessions[st.session_state.session_id] = {
            "session_id": create_session(),
            "chat_history": [],
            "agent_info": get_agent_by_name(agent_names[0]),
            "context": user_context,
            "user": user_obj["name"],
            "model": agent_names[0],
        }

# === Sidebar Traces ===
with st.sidebar:
    st.markdown("## ⚙️ Options")
    show_traces = st.checkbox("📊 Show Traces", value=False)

    if show_traces and "sessions" in st.session_state and st.session_state.session_id:
        session = st.session_state.sessions.get(st.session_state.session_id, {})
        history = session.get("chat_history", [])
        st.markdown("### 🧪 Traces")
        for i, msg in enumerate(history):
            if msg.get("trace"):
                with st.expander(f"🔹 Q{i+1}: {msg['user'][:50]}..."):
                    st.json(msg["trace"], expanded=False)

# === Top Controls ===
st.title("🤖 Chat with Bedrock Agent")

top_cols = st.columns([3, 3, 2])  # changed from 4 columns to 3
session = st.session_state.sessions.get(st.session_state.session_id, {})

with top_cols[0]:
    default_user = session.get("user", user_names[0])
    selected_user = st.selectbox("👤 Select User", user_names, index=user_names.index(default_user))

with top_cols[1]:
    default_model = session.get("model", agent_names[0])
    selected_model = st.selectbox("🧠 Select Model", agent_names, index=agent_names.index(default_model))

if st.session_state.session_id and selected_user:
    session = st.session_state.sessions[st.session_state.session_id]
    if session.get("user") != selected_user:
        user_obj = next((u for u in users if u["name"] == selected_user), {})
        user_context = (
            "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
            + json.dumps(user_obj, indent=2)
        )
        session["context"] = user_context
        session["user"] = selected_user
        session["model"] = selected_model

with top_cols[2]:
    if st.button("➕ New Session"):
        new_id = str(uuid.uuid4())
        user_obj = next((u for u in users if u["name"] == selected_user), {})
        user_context = (
            "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
            + json.dumps(user_obj, indent=2)
        )
        st.session_state.sessions[new_id] = {
            "session_id": create_session(),
            "chat_history": [],
            "agent_info": get_agent_by_name(selected_model),
            "context": user_context,
            "user": selected_user,
            "model": selected_model,
        }
        st.session_state.session_id = new_id
        st.query_params["session"] = new_id
        st.rerun()

# === Final Session Check ===
if not st.session_state.session_id or st.session_state.session_id not in st.session_state.sessions:
    st.info("Click ➕ New Session to start.")
    st.stop()

# === Active Session ===
session = st.session_state.sessions[st.session_state.session_id]

with st.expander("📄 User Context", expanded=False):
    st.code(session["context"], language="json")

# === Chat History ===
st.markdown("### 💬 Conversation")
for msg in session["chat_history"]:
    with st.chat_message("user"):
        st.markdown(msg["user"])
    with st.chat_message("assistant"):
        st.markdown(msg["agent"])
        st.caption(f"🧮 Input Tokens: {msg.get('input_tokens', '?')} | 🧾 Output Tokens: {msg.get('output_tokens', '?')} | ⏱ Time Taken: {msg.get('time_taken', '?')}ms")

# === Input Box ===
question = st.chat_input("Ask something...")
if question:
    with st.spinner("Thinking..."):
        response, trace_info, input_tokens, output_tokens, time_taken = invoke_agent(
            agent_id=session["agent_info"]["id"],
            agent_alias_id=session["agent_info"]["alias_id"],
            session_id=session["session_id"],
            user_context=session["context"],
            prompt=question
        )

        session["chat_history"].append({
            "user": question,
            "agent": response,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "time_taken": time_taken,
            "trace": trace_info
        })

        save_session_to_dynamodb(session["user"], st.session_state.session_id, session)
        st.rerun()
