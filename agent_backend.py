import boto3
import json
import uuid
import os

# === CONFIGURATION ===
REGION = "us-east-1"
USER_CONTEXT_FILE = "userProfilesAll.json"
DYNAMO_TABLE_NAME = "AgentChatSessionsFinops"

# === AGENT CONFIGURATION ===
AGENTS = [
    {
        "name": "Nova-Agent",
        "id": "0EKGDLFNFI",
        "alias_id": "ZT7BK3IAY6"
    }
]

# === Clients ===
client = boto3.client("bedrock-agent-runtime", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(DYNAMO_TABLE_NAME)

# === Load user profiles ===
def load_users():
    try:
        with open(USER_CONTEXT_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {USER_CONTEXT_FILE}: {e}")
        return []

# === Get agent info ===
def get_agent_by_name(name):
    for agent in AGENTS:
        if agent["name"] == name:
            return {"id": agent["id"], "alias_id": agent["alias_id"]}
    raise ValueError(f"Agent '{name}' not found")

# === New session ID ===
def create_session():
    return str(uuid.uuid4())

# === Save session ===
def save_session_to_dynamo(user_id, session_id, session_data):
    try:
        table.put_item(Item={
            "user_id": user_id,
            "session_id": session_id,
            "data": json.dumps(session_data)
        })
    except Exception as e:
        print(f"❌ Error saving session {session_id}: {e}")

# === Load session ===
def load_session_from_dynamo(user_id, session_id):
    try:
        response = table.get_item(Key={"user_id": user_id, "session_id": session_id})
        item = response.get("Item")
        if item:
            return json.loads(item["data"])
    except Exception as e:
        print(f"❌ Error loading session {session_id}: {e}")
    return None

# === Invoke agent ===
def invoke_agent(agent_id, agent_alias_id, session_id, user_context, prompt):
    try:
        full_prompt = (
            "You are a financial assistant with access to the following user profile:\n\n"
            f"{user_context}\n\n"
            "Based on the above, answer the user's question in a personalized and helpful manner.\n\n"
            f"User Question: {prompt}"
        )

        response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=full_prompt,
            enableTrace=True
        )

        output_text = ""
        trace_info = []
        for event in response["completion"]:
            if "chunk" in event:
                output_text += event["chunk"]["bytes"].decode("utf-8")
            elif "trace" in event:
                trace_info.append(event["trace"])

        usage = {}
        time_taken = 0
        for trace in trace_info:
            orchestration = trace.get("trace", {}).get("orchestrationTrace", {})
            if "modelInvocationOutput" in orchestration:
                usage = orchestration["modelInvocationOutput"]["metadata"]["usage"]
                time_taken = orchestration["modelInvocationOutput"]["metadata"]["totalTimeMs"]

        return output_text.strip(), trace_info, usage.get("inputTokens", "?"), usage.get("outputTokens", "?"), time_taken

    except Exception as e:
        return f"❌ Error invoking agent: {e}", None, "?", "?", "?"


