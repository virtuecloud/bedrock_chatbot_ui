### ✅ `README.md`

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

## 🚀 CI/CD Deployment to Amazon ECR (via GitHub Actions + OIDC)

This project supports secure CI/CD using GitHub OIDC (no AWS secrets).

### 📋 Prerequisites

1. **Amazon ECR Repository**: e.g., `bedrock_chatbot`

2. **IAM Role for GitHub OIDC**:

   * Create a role with:

     * **Trusted entity**: GitHub OpenID Connect
     * **Trusted provider**: `token.actions.githubusercontent.com`
     * **Audience**: `sts.amazonaws.com`
   * Add trust relationship for your repo (replace OWNER/REPO):

     ```json
     {
       "Effect": "Allow",
       "Principal": {
         "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
       },
       "Action": "sts:AssumeRoleWithWebIdentity",
       "Condition": {
         "StringLike": {
           "token.actions.githubusercontent.com:sub": "repo:OWNER/REPO:*"
         },
         "StringEquals": {
           "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
         }
       }
     }
     ```

3. **Attach Permissions**: ECR access (e.g., `AmazonEC2ContainerRegistryPowerUser`)

---

### ⚙️ GitHub Actions Workflow: `.github/workflows/deploy.yml`

```yaml
name: Build & Push to ECR

on:
  push:
    branches: [ main ]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS Credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/github-actions-oidc-role
          aws-region: us-east-1

      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build Docker Image
        run: |
          docker build -t bedrock_chatbot:latest .

      - name: Tag & Push to ECR
        env:
          ECR_REGISTRY: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
        run: |
          docker tag bedrock_chatbot:latest $ECR_REGISTRY/bedrock_chatbot:latest
          docker push $ECR_REGISTRY/bedrock_chatbot:latest
```

---

## 📦 DynamoDB Usage

Ensure you have a DynamoDB table named `AgentChatSessions`. It stores:

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
