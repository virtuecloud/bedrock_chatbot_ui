import boto3
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("AgentChatSessions")  # Ensure this table exists

def clean_data(obj):
    """Recursively convert float → Decimal, datetime → str"""
    if isinstance(obj, dict):
        return {k: clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_data(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj

def save_session_to_dynamodb(user_id, session_id, session_data):
    try:
        item = {
            "user_id": user_id,
            "session_id": session_id,
            "chat_history": clean_data(session_data.get("chat_history", [])),
            "context": session_data.get("context", ""),
            "model": session_data.get("model", ""),
            "agent_info": clean_data(session_data.get("agent_info", {})),
            "user": session_data.get("user", "")
        }
        table.put_item(Item=item)
    except Exception as e:
        print(f"❌ Error saving to DynamoDB: {e}")

def load_session_from_dynamodb(user_id, session_id):
    try:
        response = table.get_item(Key={"user_id": user_id, "session_id": session_id})
        return response.get("Item")
    except Exception as e:
        print(f"❌ Error loading session from DynamoDB: {e}")
        return None

