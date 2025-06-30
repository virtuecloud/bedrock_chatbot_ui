import streamlit as st
import uuid
import json
import pandas as pd
from agent_backend import load_users, create_session, invoke_agent, get_agent_by_name
from dynamodb_backend import save_session_to_dynamodb, load_session_from_dynamodb
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
import io

# === Register a Unicode Font ===
pdfmetrics.registerFont(TTFont("DejaVuSans", "/System/Library/Fonts/Supplemental/DejaVuSans.ttf"))

def create_pdf(text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont("DejaVuSans", 12)
    width, height = A4
    x, y = 50, height - 50
    for line in text.split("\n"):
        c.drawString(x, y, line)
        y -= 20
        if y < 50:
            c.showPage()
            c.setFont("DejaVuSans", 12)
            y = height - 50
    c.save()
    buffer.seek(0)
    return buffer

# === Page Setup ===
st.set_page_config(page_title="ChatGPT-style Agent", layout="wide")
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

top_cols = st.columns([3, 3, 2])
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
for i, msg in enumerate(session["chat_history"]):
    with st.chat_message("user"):
        st.markdown(msg["user"])
    with st.chat_message("assistant"):
        st.markdown(msg["agent"])
        st.caption(f"🧮 Input Tokens: {msg.get('input_tokens', '?')} | 🧾 Output Tokens: {msg.get('output_tokens', '?')} | ⏱ Time Taken: {msg.get('time_taken', '?')}ms")

        # PDF download button per response
        pdf_buffer = create_pdf(msg["agent"])
        st.download_button(
            label="📄 Download PDF",
            data=pdf_buffer,
            file_name=f"response_{i+1}.pdf",
            mime="application/pdf"
        )

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


# import streamlit as st(running without export button)
# import uuid
# import json
# import pandas as pd
# from agent_backend import load_users, create_session, invoke_agent, get_agent_by_name
# from dynamodb_backend import save_session_to_dynamodb, load_session_from_dynamodb

# # === Page Setup ===
# st.set_page_config(page_title="ChatGPT-style Agent", layout="wide")
# st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# # === Load users and models ===
# users = load_users()
# user_names = [user["name"] for user in users]
# agent_names = ["nova"]

# # === Init session state ===
# if "sessions" not in st.session_state:
#     st.session_state.sessions = {}
# if "session_id" not in st.session_state:
#     st.session_state.session_id = None

# # === Get session from URL if present ===
# query_params = st.query_params
# current_id = query_params.get("session")
# if current_id:
#     st.session_state.session_id = current_id

# # === Load session from DynamoDB or initialize ===
# if st.session_state.session_id and st.session_state.session_id not in st.session_state.sessions:
#     found = False
#     for user in users:
#         session_data = load_session_from_dynamodb(user["name"], st.session_state.session_id)
#         if session_data:
#             st.session_state.sessions[st.session_state.session_id] = {
#                 "session_id": st.session_state.session_id,
#                 "chat_history": session_data.get("chat_history", []),
#                 "context": session_data.get("context", ""),
#                 "model": session_data.get("model", ""),
#                 "agent_info": session_data.get("agent_info", {}),
#                 "user": session_data.get("user", user["name"])
#             }
#             found = True
#             break

#     if not found:
#         default_user = users[0] if users else {}
#         user_obj = next((u for u in users if u["name"] == default_user.get("name")), default_user)
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[st.session_state.session_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(agent_names[0]),
#             "context": user_context,
#             "user": user_obj["name"],
#             "model": agent_names[0],
#         }

# # === Sidebar Traces ===
# with st.sidebar:
#     st.markdown("## ⚙️ Options")
#     show_traces = st.checkbox("📊 Show Traces", value=False)

#     if show_traces and "sessions" in st.session_state and st.session_state.session_id:
#         session = st.session_state.sessions.get(st.session_state.session_id, {})
#         history = session.get("chat_history", [])
#         st.markdown("### 🧪 Traces")
#         for i, msg in enumerate(history):
#             if msg.get("trace"):
#                 with st.expander(f"🔹 Q{i+1}: {msg['user'][:50]}..."):
#                     st.json(msg["trace"], expanded=False)

# # === Top Controls ===
# st.title("🤖 Chat with Bedrock Agent")

# top_cols = st.columns([3, 3, 2])  # changed from 4 columns to 3
# session = st.session_state.sessions.get(st.session_state.session_id, {})

# with top_cols[0]:
#     default_user = session.get("user", user_names[0])
#     selected_user = st.selectbox("👤 Select User", user_names, index=user_names.index(default_user))

# with top_cols[1]:
#     default_model = session.get("model", agent_names[0])
#     selected_model = st.selectbox("🧠 Select Model", agent_names, index=agent_names.index(default_model))

# if st.session_state.session_id and selected_user:
#     session = st.session_state.sessions[st.session_state.session_id]
#     if session.get("user") != selected_user:
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         session["context"] = user_context
#         session["user"] = selected_user
#         session["model"] = selected_model

# with top_cols[2]:
#     if st.button("➕ New Session"):
#         new_id = str(uuid.uuid4())
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[new_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(selected_model),
#             "context": user_context,
#             "user": selected_user,
#             "model": selected_model,
#         }
#         st.session_state.session_id = new_id
#         st.query_params["session"] = new_id
#         st.rerun()

# # === Final Session Check ===
# if not st.session_state.session_id or st.session_state.session_id not in st.session_state.sessions:
#     st.info("Click ➕ New Session to start.")
#     st.stop()

# # === Active Session ===
# session = st.session_state.sessions[st.session_state.session_id]

# with st.expander("📄 User Context", expanded=False):
#     st.code(session["context"], language="json")

# # === Chat History ===
# st.markdown("### 💬 Conversation")
# for msg in session["chat_history"]:
#     with st.chat_message("user"):
#         st.markdown(msg["user"])
#     with st.chat_message("assistant"):
#         st.markdown(msg["agent"])
#         st.caption(f"🧮 Input Tokens: {msg.get('input_tokens', '?')} | 🧾 Output Tokens: {msg.get('output_tokens', '?')} | ⏱ Time Taken: {msg.get('time_taken', '?')}ms")

# # === Input Box ===
# question = st.chat_input("Ask something...")
# if question:
#     with st.spinner("Thinking..."):
#         response, trace_info, input_tokens, output_tokens, time_taken = invoke_agent(
#             agent_id=session["agent_info"]["id"],
#             agent_alias_id=session["agent_info"]["alias_id"],
#             session_id=session["session_id"],
#             user_context=session["context"],
#             prompt=question
#         )

#         session["chat_history"].append({
#             "user": question,
#             "agent": response,
#             "input_tokens": input_tokens,
#             "output_tokens": output_tokens,
#             "time_taken": time_taken,
#             "trace": trace_info
#         })

#         save_session_to_dynamodb(session["user"], st.session_state.session_id, session)
#         st.rerun()


# import streamlit as st(running with export button)
# import uuid
# import json
# import pandas as pd
# from agent_backend import load_users, create_session, invoke_agent, get_agent_by_name
# from dynamodb_backend import save_session_to_dynamodb, load_session_from_dynamodb

# # === Page Setup ===
# st.set_page_config(page_title="ChatGPT-style Agent", layout="wide")
# st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# # === Load users and models ===
# users = load_users()
# user_names = [user["name"] for user in users]
# agent_names = ["nova"]

# # === Init session state ===
# if "sessions" not in st.session_state:
#     st.session_state.sessions = {}
# if "session_id" not in st.session_state:
#     st.session_state.session_id = None

# # === Get session from URL if present ===
# query_params = st.query_params
# current_id = query_params.get("session")  # ✅ FIXED: removed [0]
# if current_id:
#     st.session_state.session_id = current_id

# # === Load session from DynamoDB or initialize ===
# if st.session_state.session_id and st.session_state.session_id not in st.session_state.sessions:
#     found = False
#     for user in users:
#         session_data = load_session_from_dynamodb(user["name"], st.session_state.session_id)
#         if session_data:
#             st.session_state.sessions[st.session_state.session_id] = {
#                 "session_id": st.session_state.session_id,
#                 "chat_history": session_data.get("chat_history", []),
#                 "context": session_data.get("context", ""),
#                 "model": session_data.get("model", ""),
#                 "agent_info": session_data.get("agent_info", {}),
#                 "user": session_data.get("user", user["name"])
#             }
#             found = True
#             break

#     if not found:
#         default_user = users[0] if users else {}
#         user_obj = next((u for u in users if u["name"] == default_user.get("name")), default_user)
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[st.session_state.session_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(agent_names[0]),
#             "context": user_context,
#             "user": user_obj["name"],
#             "model": agent_names[0],
#         }

# # === Sidebar Traces ===
# with st.sidebar:
#     st.markdown("## ⚙️ Options")
#     show_traces = st.checkbox("📊 Show Traces", value=False)

#     if show_traces and "sessions" in st.session_state and st.session_state.session_id:
#         session = st.session_state.sessions.get(st.session_state.session_id, {})
#         history = session.get("chat_history", [])
#         st.markdown("### 🧪 Traces")
#         for i, msg in enumerate(history):
#             if msg.get("trace"):
#                 with st.expander(f"🔹 Q{i+1}: {msg['user'][:50]}..."):
#                     st.json(msg["trace"], expanded=False)

# # === Top Controls ===
# st.title("🤖 Chat with Bedrock Agent")

# top_cols = st.columns([3, 3, 2, 2])
# session = st.session_state.sessions.get(st.session_state.session_id, {})

# with top_cols[0]:
#     default_user = session.get("user", user_names[0])
#     selected_user = st.selectbox("👤 Select User", user_names, index=user_names.index(default_user))

# with top_cols[1]:
#     default_model = session.get("model", agent_names[0])
#     selected_model = st.selectbox("🧠 Select Model", agent_names, index=agent_names.index(default_model))

# if st.session_state.session_id and selected_user:
#     session = st.session_state.sessions[st.session_state.session_id]
#     if session.get("user") != selected_user:
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         session["context"] = user_context
#         session["user"] = selected_user
#         session["model"] = selected_model

# with top_cols[2]:
#     if st.button("➕ New Session"):
#         new_id = str(uuid.uuid4())
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[new_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(selected_model),
#             "context": user_context,
#             "user": selected_user,
#             "model": selected_model,
#         }
#         st.session_state.session_id = new_id
#         st.query_params["session"] = new_id
#         st.rerun()

# with top_cols[3]:
#     if st.button("⬇ Export"):
#         if st.session_state.session_id:
#             session = st.session_state.sessions[st.session_state.session_id]
#             df = pd.DataFrame(session["chat_history"])
#             json_data = json.dumps(session["chat_history"], indent=2)
#             st.download_button("Download CSV", df.to_csv(index=False), file_name="chat.csv")
#             st.download_button("Download JSON", json_data, file_name="chat.json")

# # === Final Session Check ===
# if not st.session_state.session_id or st.session_state.session_id not in st.session_state.sessions:
#     st.info("Click ➕ New Session to start.")
#     st.stop()

# # === Active Session ===
# session = st.session_state.sessions[st.session_state.session_id]

# with st.expander("📄 User Context", expanded=False):
#     st.code(session["context"], language="json")

# # === Chat History ===
# st.markdown("### 💬 Conversation")
# for msg in session["chat_history"]:
#     with st.chat_message("user"):
#         st.markdown(msg["user"])
#     with st.chat_message("assistant"):
#         st.markdown(msg["agent"])
#         st.caption(f"🧮 Input Tokens: {msg.get('input_tokens', '?')} | 🧾 Output Tokens: {msg.get('output_tokens', '?')} | ⏱ Time Taken: {msg.get('time_taken', '?')}ms")

# # === Input Box ===
# question = st.chat_input("Ask something...")
# if question:
#     with st.spinner("Thinking..."):
#         response, trace_info, input_tokens, output_tokens, time_taken = invoke_agent(
#             agent_id=session["agent_info"]["id"],
#             agent_alias_id=session["agent_info"]["alias_id"],
#             session_id=session["session_id"],
#             user_context=session["context"],
#             prompt=question
#         )

#         session["chat_history"].append({
#             "user": question,
#             "agent": response,
#             "input_tokens": input_tokens,
#             "output_tokens": output_tokens,
#             "time_taken": time_taken,
#             "trace": trace_info
#         })

#         save_session_to_dynamodb(session["user"], st.session_state.session_id, session)
#         st.rerun()


# import streamlit as st(running)
# import uuid
# import json
# import pandas as pd
# from agent_backend import load_users, create_session, invoke_agent, get_agent_by_name
# from dynamodb_backend import save_session_to_dynamodb, load_session_from_dynamodb

# # === Page Setup ===
# st.set_page_config(page_title="ChatGPT-style Agent", layout="wide")
# st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# # === Load users and models ===
# users = load_users()
# user_names = [user["name"] for user in users]
# agent_names = ["nova"]

# # === Init session state ===
# if "sessions" not in st.session_state:
#     st.session_state.sessions = {}
# if "session_id" not in st.session_state:
#     st.session_state.session_id = None

# # === Get session from URL if present ===
# query_params = st.query_params
# current_id = query_params.get("session")  # ✅ FIXED: removed [0]
# if current_id:
#     st.session_state.session_id = current_id

# # === Load session from DynamoDB or initialize ===
# if st.session_state.session_id and st.session_state.session_id not in st.session_state.sessions:
#     found = False
#     for user in users:
#         session_data = load_session_from_dynamodb(user["name"], st.session_state.session_id)
#         if session_data:
#             st.session_state.sessions[st.session_state.session_id] = {
#                 "session_id": st.session_state.session_id,
#                 "chat_history": session_data.get("chat_history", []),
#                 "context": session_data.get("context", ""),
#                 "model": session_data.get("model", ""),
#                 "agent_info": session_data.get("agent_info", {}),
#                 "user": session_data.get("user", user["name"])
#             }
#             found = True
#             break

#     if not found:
#         default_user = users[0] if users else {}
#         user_obj = next((u for u in users if u["name"] == default_user.get("name")), default_user)
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[st.session_state.session_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(agent_names[0]),
#             "context": user_context,
#             "user": user_obj["name"],
#             "model": agent_names[0],
#         }

# # === Sidebar Traces ===
# with st.sidebar:
#     st.markdown("## ⚙️ Options")
#     show_traces = st.checkbox("📊 Show Traces", value=False)

#     if show_traces and "sessions" in st.session_state and st.session_state.session_id:
#         session = st.session_state.sessions.get(st.session_state.session_id, {})
#         history = session.get("chat_history", [])
#         st.markdown("### 🧪 Traces")
#         for i, msg in enumerate(history):
#             if msg.get("trace"):
#                 with st.expander(f"🔹 Q{i+1}: {msg['user'][:50]}..."):
#                     st.json(msg["trace"], expanded=False)

# # === Top Controls ===
# st.title("🤖 Chat with Bedrock Agent")

# top_cols = st.columns([3, 3, 2, 2])
# with top_cols[0]:
#     selected_user = st.selectbox("👤 Select User", user_names)
# with top_cols[1]:
#     selected_model = st.selectbox("🧠 Select Model", agent_names)

# if st.session_state.session_id and selected_user:
#     session = st.session_state.sessions[st.session_state.session_id]
#     if session.get("user") != selected_user:
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         session["context"] = user_context
#         session["user"] = selected_user
#         session["model"] = selected_model

# with top_cols[2]:
#     if st.button("➕ New Session"):
#         new_id = str(uuid.uuid4())
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[new_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(selected_model),
#             "context": user_context,
#             "user": selected_user,
#             "model": selected_model,
#         }
#         st.session_state.session_id = new_id
#         st.query_params["session"] = new_id
#         st.rerun()

# with top_cols[3]:
#     if st.button("⬇ Export"):
#         if st.session_state.session_id:
#             session = st.session_state.sessions[st.session_state.session_id]
#             df = pd.DataFrame(session["chat_history"])
#             json_data = json.dumps(session["chat_history"], indent=2)
#             st.download_button("Download CSV", df.to_csv(index=False), file_name="chat.csv")
#             st.download_button("Download JSON", json_data, file_name="chat.json")

# # === Final Session Check ===
# if not st.session_state.session_id or st.session_state.session_id not in st.session_state.sessions:
#     st.info("Click ➕ New Session to start.")
#     st.stop()

# # === Active Session ===
# session = st.session_state.sessions[st.session_state.session_id]

# with st.expander("📄 User Context", expanded=False):
#     st.code(session["context"], language="json")

# # === Chat History ===
# st.markdown("### 💬 Conversation")
# for msg in session["chat_history"]:
#     with st.chat_message("user"):
#         st.markdown(msg["user"])
#     with st.chat_message("assistant"):
#         st.markdown(msg["agent"])
#         st.caption(f"🧮 Input Tokens: {msg.get('input_tokens', '?')} | 🧾 Output Tokens: {msg.get('output_tokens', '?')} | ⏱ Time Taken: {msg.get('time_taken', '?')}ms")

# # === Input Box ===
# question = st.chat_input("Ask something...")
# if question:
#     with st.spinner("Thinking..."):
#         response, trace_info, input_tokens, output_tokens, time_taken = invoke_agent(
#             agent_id=session["agent_info"]["id"],
#             agent_alias_id=session["agent_info"]["alias_id"],
#             session_id=session["session_id"],
#             user_context=session["context"],
#             prompt=question
#         )

#         session["chat_history"].append({
#             "user": question,
#             "agent": response,
#             "input_tokens": input_tokens,
#             "output_tokens": output_tokens,
#             "time_taken": time_taken,
#             "trace": trace_info
#         })

#         save_session_to_dynamodb(session["user"], st.session_state.session_id, session)
#         st.rerun()


# import streamlit as st
# import uuid
# import json
# import pandas as pd
# from agent_backend import load_users, create_session, invoke_agent, get_agent_by_name
# from dynamodb_backend import save_session_to_dynamodb, load_session_from_dynamodb

# # === Page Setup ===
# st.set_page_config(page_title="ChatGPT-style Agent", layout="wide")
# st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# # === Load users and models ===
# users = load_users()
# user_names = [user["name"] for user in users]
# agent_names = ["nova"]

# # === Init session state ===
# if "sessions" not in st.session_state:
#     st.session_state.sessions = {}
# if "session_id" not in st.session_state:
#     st.session_state.session_id = None

# # === Get session from URL if present ===
# query_params = st.query_params
# current_id = query_params.get("session")  # ✅ FIXED: removed [0]
# if current_id:
#     st.session_state.session_id = current_id

# # === Load session from DynamoDB or initialize ===
# if st.session_state.session_id and st.session_state.session_id not in st.session_state.sessions:
#     found = False
#     for user in users:
#         session_data = load_session_from_dynamodb(user["name"], st.session_state.session_id)
#         if session_data:
#             st.session_state.sessions[st.session_state.session_id] = {
#                 "session_id": st.session_state.session_id,
#                 "chat_history": session_data.get("chat_history", []),
#                 "context": session_data.get("context", ""),
#                 "model": session_data.get("model", ""),
#                 "agent_info": session_data.get("agent_info", {}),
#                 "user": session_data.get("user", user["name"])
#             }
#             found = True
#             break

#     if not found:
#         default_user = users[0] if users else {}
#         user_obj = next((u for u in users if u["name"] == default_user.get("name")), default_user)
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[st.session_state.session_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(agent_names[0]),
#             "context": user_context,
#             "user": user_obj["name"],
#             "model": agent_names[0],
#         }

# # === Sidebar Traces ===
# with st.sidebar:
#     st.markdown("## ⚙️ Options")
#     show_traces = st.checkbox("📊 Show Traces", value=False)

#     if show_traces and "sessions" in st.session_state and st.session_state.session_id:
#         session = st.session_state.sessions.get(st.session_state.session_id, {})
#         history = session.get("chat_history", [])
#         st.markdown("### 🧪 Traces")
#         for i, msg in enumerate(history):
#             if msg.get("trace"):
#                 with st.expander(f"🔹 Q{i+1}: {msg['user'][:50]}..."):
#                     st.json(msg["trace"], expanded=False)

# # === Top Controls ===
# st.title("🤖 Chat with Bedrock Agent")

# top_cols = st.columns([3, 3, 2, 2])
# with top_cols[0]:
#     selected_user = st.selectbox("👤 Select User", user_names)
# with top_cols[1]:
#     selected_model = st.selectbox("🧠 Select Model", agent_names)

# if st.session_state.session_id and selected_user:
#     session = st.session_state.sessions[st.session_state.session_id]
#     if session.get("user") != selected_user:
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         session["context"] = user_context
#         session["user"] = selected_user
#         session["model"] = selected_model

# with top_cols[2]:
#     if st.button("➕ New Session"):
#         new_id = str(uuid.uuid4())
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[new_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(selected_model),
#             "context": user_context,
#             "user": selected_user,
#             "model": selected_model,
#         }
#         st.session_state.session_id = new_id
#         st.query_params["session"] = new_id
#         st.rerun()

# with top_cols[3]:
#     if st.button("⬇ Export"):
#         if st.session_state.session_id:
#             session = st.session_state.sessions[st.session_state.session_id]
#             df = pd.DataFrame(session["chat_history"])
#             json_data = json.dumps(session["chat_history"], indent=2)
#             st.download_button("Download CSV", df.to_csv(index=False), file_name="chat.csv")
#             st.download_button("Download JSON", json_data, file_name="chat.json")

# # === Final Session Check ===
# if not st.session_state.session_id or st.session_state.session_id not in st.session_state.sessions:
#     st.info("Click ➕ New Session to start.")
#     st.stop()

# # === Active Session ===
# session = st.session_state.sessions[st.session_state.session_id]

# with st.expander("📄 User Context", expanded=False):
#     st.code(session["context"], language="json")

# # === Chat History ===
# st.markdown("### 💬 Conversation")
# for msg in session["chat_history"]:
#     with st.chat_message("user"):
#         st.markdown(msg["user"])
#     with st.chat_message("assistant"):
#         st.markdown(msg["agent"])
#         st.caption(f"🧮 Input Tokens: {msg.get('input_tokens', '?')} | 🧾 Output Tokens: {msg.get('output_tokens', '?')} | ⏱ Time Taken: {msg.get('time_taken', '?')}ms")

# # === Input Box ===
# question = st.chat_input("Ask something...")
# if question:
#     with st.spinner("Thinking..."):
#         response, trace_info, input_tokens, output_tokens, time_taken = invoke_agent(
#             agent_id=session["agent_info"]["id"],
#             agent_alias_id=session["agent_info"]["alias_id"],
#             session_id=session["session_id"],
#             user_context=session["context"],
#             prompt=question
#         )

#         session["chat_history"].append({
#             "user": question,
#             "agent": response,
#             "input_tokens": input_tokens,
#             "output_tokens": output_tokens,
#             "time_taken": time_taken,
#             "trace": trace_info
#         })

#         save_session_to_dynamodb(session["user"], st.session_state.session_id, session)
#         st.rerun()


# import streamlit as st(another tab issue rest is correct)
# import uuid
# import json
# import pandas as pd
# from agent_backend import load_users, create_session, invoke_agent, get_agent_by_name
# from dynamodb_backend import save_session_to_dynamodb, load_session_from_dynamodb

# # === Page Setup ===
# st.set_page_config(page_title="ChatGPT-style Agent", layout="wide")
# st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# # === Load users and models ===
# users = load_users()
# user_names = [user["name"] for user in users]
# agent_names = ["nova"]

# # === Init session state ===
# if "sessions" not in st.session_state:
#     st.session_state.sessions = {}
# if "session_id" not in st.session_state:
#     st.session_state.session_id = None

# # === Get session from URL if present ===
# query_params = st.query_params
# current_id = query_params.get("session", [None])[0]
# if current_id:
#     st.session_state.session_id = current_id

# # === Load session from DynamoDB or initialize ===
# if st.session_state.session_id and st.session_state.session_id not in st.session_state.sessions:
#     found = False
#     for user in users:
#         session_data = load_session_from_dynamodb(user["name"], st.session_state.session_id)
#         if session_data:
#             st.session_state.sessions[st.session_state.session_id] = {
#                 "session_id": st.session_state.session_id,
#                 "chat_history": session_data.get("chat_history", []),
#                 "context": session_data.get("context", ""),
#                 "model": session_data.get("model", ""),
#                 "agent_info": session_data.get("agent_info", {}),
#                 "user": session_data.get("user", user["name"])
#             }
#             found = True
#             break

#     if not found:
#         default_user = users[0] if users else {}
#         user_obj = next((u for u in users if u["name"] == default_user.get("name")), default_user)
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[st.session_state.session_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(agent_names[0]),
#             "context": user_context,
#             "user": user_obj["name"],
#             "model": agent_names[0],
#         }

# # === Sidebar Traces ===
# with st.sidebar:
#     st.markdown("## ⚙️ Options")
#     show_traces = st.checkbox("📊 Show Traces", value=False)

#     if show_traces and "sessions" in st.session_state and st.session_state.session_id:
#         session = st.session_state.sessions.get(st.session_state.session_id, {})
#         history = session.get("chat_history", [])
#         st.markdown("### 🧪 Traces")
#         for i, msg in enumerate(history):
#             if msg.get("trace"):
#                 with st.expander(f"🔹 Q{i+1}: {msg['user'][:50]}..."):
#                     st.json(msg["trace"], expanded=False)

# # === Top Controls ===
# st.title("🤖 Chat with Bedrock Agent")

# top_cols = st.columns([3, 3, 2, 2])
# with top_cols[0]:
#     selected_user = st.selectbox("👤 Select User", user_names)
# with top_cols[1]:
#     selected_model = st.selectbox("🧠 Select Model", agent_names)

# if st.session_state.session_id and selected_user:
#     session = st.session_state.sessions[st.session_state.session_id]
#     if session.get("user") != selected_user:
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         session["context"] = user_context
#         session["user"] = selected_user
#         session["model"] = selected_model

# with top_cols[2]:
#     if st.button("➕ New Session"):
#         new_id = str(uuid.uuid4())
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         st.session_state.sessions[new_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(selected_model),
#             "context": user_context,
#             "user": selected_user,
#             "model": selected_model,
#         }
#         st.session_state.session_id = new_id
#         st.query_params["session"] = new_id
#         st.rerun()

# with top_cols[3]:
#     if st.button("⬇ Export"):
#         if st.session_state.session_id:
#             session = st.session_state.sessions[st.session_state.session_id]
#             df = pd.DataFrame(session["chat_history"])
#             json_data = json.dumps(session["chat_history"], indent=2)
#             st.download_button("Download CSV", df.to_csv(index=False), file_name="chat.csv")
#             st.download_button("Download JSON", json_data, file_name="chat.json")

# # === Final Session Check ===
# if not st.session_state.session_id or st.session_state.session_id not in st.session_state.sessions:
#     st.info("Click ➕ New Session to start.")
#     st.stop()

# # === Active Session ===
# session = st.session_state.sessions[st.session_state.session_id]

# with st.expander("📄 User Context", expanded=False):
#     st.code(session["context"], language="json")

# # === Chat History ===
# st.markdown("### 💬 Conversation")
# for msg in session["chat_history"]:
#     with st.chat_message("user"):
#         st.markdown(msg["user"])
#     with st.chat_message("assistant"):
#         st.markdown(msg["agent"])
#         st.caption(f"🧮 Input Tokens: {msg.get('input_tokens', '?')} | 🧾 Output Tokens: {msg.get('output_tokens', '?')} | ⏱ Time Taken: {msg.get('time_taken', '?')}ms")

# # === Input Box ===
# question = st.chat_input("Ask something...")
# if question:
#     with st.spinner("Thinking..."):
#         response, trace_info, input_tokens, output_tokens, time_taken = invoke_agent(
#             agent_id=session["agent_info"]["id"],
#             agent_alias_id=session["agent_info"]["alias_id"],
#             session_id=session["session_id"],
#             user_context=session["context"],
#             prompt=question
#         )

#         session["chat_history"].append({
#             "user": question,
#             "agent": response,
#             "input_tokens": input_tokens,
#             "output_tokens": output_tokens,
#             "time_taken": time_taken,
#             "trace": trace_info
#         })

#         save_session_to_dynamodb(session["user"], st.session_state.session_id, session)
#         st.rerun()


# import streamlit as st(final)
# import uuid
# import json
# import pandas as pd
# from agent_backend import load_users, create_session, invoke_agent, get_agent_by_name

# # === Page Setup ===
# st.set_page_config(page_title="ChatGPT-style Agent", layout="wide")
# st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# # === Load users and models ===
# users = load_users()
# user_names = [user["name"] for user in users]
# agent_names = ["nova"]  # Extendable

# # === Init session state ===
# if "sessions" not in st.session_state:
#     st.session_state.sessions = {}
# if "session_id" not in st.session_state:
#     st.session_state.session_id = None

# # === Get session from URL if present ===
# query_params = st.query_params
# current_id = query_params.get("session", [None])[0]

# if current_id:
#     st.session_state.session_id = current_id

# # === Ensure session exists and is valid ===
# if st.session_state.session_id and st.session_state.session_id not in st.session_state.sessions:
#     default_user = users[0] if users else {}
#     selected_user = default_user.get("name", "Unknown")
#     user_obj = next((u for u in users if u["name"] == selected_user), default_user)

#     user_context = (
#         "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#         + json.dumps(user_obj, indent=2)
#     )

#     st.session_state.sessions[st.session_state.session_id] = {
#         "session_id": create_session(),
#         "chat_history": [],
#         "agent_info": get_agent_by_name(agent_names[0]),
#         "context": user_context,
#         "user": selected_user,
#         "model": agent_names[0],
#     }

# # === Sidebar Options ===
# with st.sidebar:
#     st.markdown("## ⚙️ Options")
#     show_traces = st.checkbox("📊 Show Traces", value=False)

#     if show_traces and "sessions" in st.session_state and st.session_state.session_id:
#         session = st.session_state.sessions.get(st.session_state.session_id, {})
#         history = session.get("chat_history", [])
#         st.markdown("### 🧪 Traces")

#         for i, msg in enumerate(history):
#             if msg.get("trace"):
#                 with st.expander(f"🔹 Q{i+1}: {msg['user'][:50]}..."):
#                     st.json(msg["trace"], expanded=False)

# # === Top Controls ===
# st.title("🤖 Chat with Bedrock Agent")

# top_cols = st.columns([3, 3, 2, 2])
# with top_cols[0]:
#     selected_user = st.selectbox("👤 Select User", user_names)
# with top_cols[1]:
#     selected_model = st.selectbox("🧠 Select Model", agent_names)

# if st.session_state.session_id and selected_user:
#     session = st.session_state.sessions[st.session_state.session_id]
#     if session.get("user") != selected_user:
#         user_obj = next((u for u in users if u["name"] == selected_user), {})
#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )
#         session["context"] = user_context
#         session["user"] = selected_user
#         session["model"] = selected_model

# with top_cols[2]:
#     if st.button("➕ New Session"):
#         new_id = str(uuid.uuid4())
#         user_obj = next((u for u in users if u["name"] == selected_user), {})

#         user_context = (
#             "Below is the user's financial profile. Use this information to answer financial planning questions:\n\n"
#             + json.dumps(user_obj, indent=2)
#         )

#         st.session_state.sessions[new_id] = {
#             "session_id": create_session(),
#             "chat_history": [],
#             "agent_info": get_agent_by_name(selected_model),
#             "context": user_context,
#             "user": selected_user,
#             "model": selected_model,
#         }
#         st.session_state.session_id = new_id
#         st.query_params["session"] = new_id
#         st.rerun()

# with top_cols[3]:
#     if st.button("⬇ Export"):
#         if st.session_state.session_id:
#             session = st.session_state.sessions[st.session_state.session_id]
#             df = pd.DataFrame(session["chat_history"])
#             json_data = json.dumps(session["chat_history"], indent=2)
#             st.download_button("Download CSV", df.to_csv(index=False), file_name="chat.csv")
#             st.download_button("Download JSON", json_data, file_name="chat.json")

# # === Final session check ===
# if not st.session_state.session_id or st.session_state.session_id not in st.session_state.sessions:
#     st.info("Click ➕ New Session to start.")
#     st.stop()

# # === Load active session ===
# session = st.session_state.sessions[st.session_state.session_id]

# # === Show User Context (collapsible) ===
# with st.expander("📄 User Context", expanded=False):
#     st.code(session["context"], language="json")

# # === Show Chat History ===
# st.markdown("### 💬 Conversation")
# for msg in session["chat_history"]:
#     with st.chat_message("user"):
#         st.markdown(msg["user"])
#     with st.chat_message("assistant"):
#         st.markdown(msg["agent"])
#         st.caption(f"🧮 Input Tokens: {msg.get('input_tokens', '?')} | 🧾 Output Tokens: {msg.get('output_tokens', '?')} | ⏱ Time Taken: {msg.get('time_taken', '?')}ms")

# # === Input Box ===
# question = st.chat_input("Ask something...")
# if question:
#     with st.spinner("Thinking..."):
#         response, trace_info, input_tokens, output_tokens, time_taken = invoke_agent(
#             agent_id=session["agent_info"]["id"],
#             agent_alias_id=session["agent_info"]["alias_id"],
#             session_id=session["session_id"],
#             user_context=session["context"],
#             prompt=question
#         )

#         session["chat_history"].append({
#             "user": question,
#             "agent": response,
#             "input_tokens": input_tokens,
#             "output_tokens": output_tokens,
#             "time_taken": time_taken,
#             "trace": trace_info
#         })
#         st.rerun()