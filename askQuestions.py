import time
import boto3
import json
import os
import csv





# === CONFIGURATION ===
region = "us-east-1"
AGENTS = [
    # { 
    #     "claude": {
    #     "id": "LLVN2G9LS2",
    #     "alias_id": "IWQ6IYGOBY"
    #     }
    # }
    # { 
    #     "llama": {
    #     "id": "HHUSQUSYWA",
    #     "alias_id": "TKVAQ20UCR"
    #     }
    # }
    { 
        "nova": {
        "id": "EM94PK8GSP",
        "alias_id": "JP5VFNAFTY"
        }
    }
]
INPUT_CSV_FILE = "prompts.csv"
context_file = "userProfiles.json"

def get_queries(filepath):
    queries = []
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)
        query_index = header.index("Query")
        for row in reader:
            queries.append(row[query_index].strip())
    return queries

def create_session():
    try:
        # Initialize Bedrock Agent Runtime client
        client = boto3.client("bedrock-agent-runtime")
        session_id = client.create_session(
            tags={
                'Environment': 'Test',
                'Project': 'Demo'
            },
            sessionMetadata={
                "deviceType": "mobile"
            }
        )["sessionId"]
        print("Session created. Session ID: " + session_id)
        return session_id
    except ClientError as e:
        print(f"Error: {e}")

# === Load user context ===
with open(context_file, "r", encoding="utf-8") as f:
    users = json.load(f)

# # === Hardcode session IDs ===
# session_ids = {}
# for user in users:
#     user_id = str(user.get("user_id", user.get("name", "anonymous")).replace(" ", "_"))
#     session_ids[user_id] = {}
#     for agent in AGENTS:
#         for agent_name in agent:
#             session_ids[user_id][agent_name] = "0c39479c-83b3-4044-98cd-6abee65630db"


def create_session_for_users_and_agents(user_ids, agent_names):
    session_ids = {}
    for user_id in user_ids:
        for agent_name in agent_names:
            if user_id not in session_ids:
                session_ids[user_id] = {}
            if agent_name not in session_ids[user_id]:
                session_ids[user_id][agent_name] = create_session()
    return session_ids

def invoke_agent(agent_id, agent_alias_id, user_context,session_id,prompt):
    # print(json.dumps(user))
    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText = prompt,

        # sessionState={
        #     "sessionAttributes": session_context   # << this is the persistent session memory
        # },
        enableTrace=True
    )
    completion = ""
    trace_info = []

    for event in response["completion"]:
        if "chunk" in event:
            completion += event["chunk"]["bytes"].decode("utf-8")
        elif "trace" in event:
            trace_info.append(event["trace"])


    print (completion)
    print(trace_info)
    print("\n======================")
    usage = {}
    timeTaken = 0
    for trace in trace_info:
        if "modelInvocationOutput" in trace["trace"]['orchestrationTrace']:
            usage = trace["trace"]['orchestrationTrace']['modelInvocationOutput']['metadata']['usage']
            timeTaken = trace["trace"]['orchestrationTrace']['modelInvocationOutput']['metadata']['totalTimeMs']


    completion = completion + '[' + str(usage['inputTokens']) + ']' + '[' + str(usage['outputTokens']) + ']'
    return completion, trace_info , usage['inputTokens'], usage['outputTokens'],timeTaken


with open(context_file, "r", encoding="utf-8") as f:
    users = json.load(f)

# === Save context for token calculation (optional for later use) ===
with open(context_file, "w", encoding="utf-8") as f:
    json.dump(users, f, indent=2)

# === Initialize Bedrock Agent Runtime client ===
client = boto3.client("bedrock-agent-runtime", region_name=region)
session_ids = {}

# === Start session for each user with context and each agent ===
session_ids = create_session_for_users_and_agents(
    user_ids=[str(user.get("user_id", user.get("name", "anonymous")).replace(" ", "_")) for user in users],
    agent_names=[agent_name for agent in AGENTS for agent_name in agent.keys()]
)
print(f"Session IDs created: {session_ids}")



for user in users:
    session_context = {k: json.dumps(v) for k, v in user.items()}
    user_context = f"""Here is the financial profile of the user 
    {session_context}
    """# === Load Full Context JSON ===
    all_rows = []

    # print(session_context)
    user_id = str(user.get("user_id", user.get("name", "anonymous")).replace(" ", "_"))
    for agent in AGENTS:
        for agent_name, agent_info in agent.items():
            agent_id = agent_info["id"]
            agent_alias_id = agent_info["alias_id"]
            print(agent_name)
            invoke_agent(agent_id, agent_alias_id, user_context, session_ids[user_id][agent_name],user_context)
                

    queries = get_queries(os.path.join("Questions", user_id + ".csv"))

    for query in queries:
        try:
            print(f"Session started for: {user['name']} with {agent_name} (Session ID: {session_ids[user_id][agent_name]})")

            for agent in AGENTS:
                for agent_name, agent_info in agent.items():
                    agent_id = agent_info["id"]
                    agent_alias_id = agent_info["alias_id"]

                    response_text, trace_info, input_token, output_token, timeTaken = invoke_agent(agent_id, agent_alias_id, user_context, session_ids[user_id][agent_name], query)
                    print(f"Query: {query}\nResponse: {response_text}\n")
                    row = {
                        "User": user['name'],
                        "Query": query,
                        "Agent": agent_name,
                        "Response": response_text,
                        "Traces": trace_info,
                        "Input_Tokens": input_token,
                        "Output_Tokens": output_token,
                        "Time_Taken": timeTaken,
                        "Session_ID": session_ids[user_id][agent_name]
                    }
                    output_csv_path = os.path.join("user_responses_csv", user_id + ".csv")
                    file_exists = os.path.isfile(output_csv_path)
                    with open(output_csv_path, "a", newline='', encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=["User","Query", "Agent", "Response", "Input_Tokens", "Output_Tokens","Traces", "Time_Taken","Session_ID"])
                        if not file_exists:
                            writer.writeheader()
                        writer.writerow(row)

        except Exception as e:
            print(f"Error starting session for {user['name']} with agent {agent_name}: {e}")
        time.sleep(15)
