### ✅ VirtueAI

<h1 align="center"> Virtuecloud </h1> <br>
<p align="center">
  <a href="https://virtuecloud.io/">
    <img alt="Virtuecloud" title="Virtuecloud" src="https://virtuecloud.io/assets/images/logo.png" width="450">
  </a>
</p>

````markdown
# 🤖 Bedrock Financial Chatbot UI

This is a Streamlit-based chatbot UI that connects to Amazon Bedrock Agents to answer personalized financial planning questions using user profile context.

---

## 🔧 Setup Instructions

### 📁 1. Clone the Repository

```bash
git clone https://github.com/your-org/bedrock-chatbot.git
cd bedrock-chatbot
````

---

## 🧠 2. Update Bedrock Agent Details

Edit `agent_backend.py` and update the AGENTS list:

```python
AGENTS = [
    {
        "name": "nova",
        "id": "YOUR_BEDROCK_AGENT_ID",
        "alias_id": "YOUR_BEDROCK_AGENT_ALIAS_ID"
    }
]
```

To support multiple models (e.g., Claude), add them like:

```python
AGENTS = [
    {
        "name": "nova",
        "id": "agent-id-1",
        "alias_id": "alias-id-1"
    },
    {
        "name": "claude",
        "id": "agent-id-2",
        "alias_id": "alias-id-2"
    }
]
```

---

## 💻 Run the App Locally (macOS/Linux)

### ⏬ Step 1: Create Virtual Environment & Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### ▶️ Step 2: Run the App

```bash
streamlit run ask_to_ui.py
```

Then visit "http://localhost:8501"

---

## 📦 Run with Docker (Optional)

Build and run:

```bash
docker build -t bedrock-chatbot-ui .
docker run -p 8501:8501 bedrock-chatbot-ui
```

## 📦 DynamoDB Usage

Ensure you have a DynamoDB table named that stores:

* `user_id`, `session_id`
* Chat history
* User context
* Agent info

---

## 🔍 Features

* Multi-user + multi-agent Bedrock chat support
* Session persistence using DynamoDB
* Token usage + traces visible in UI
* Fully containerized + deployable via CI/CD to ECR
