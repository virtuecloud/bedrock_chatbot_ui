import boto3

dynamodb = boto3.client('dynamodb', region_name='us-east-1')

dynamodb.create_table(
    TableName='AgentChatSessions',
    KeySchema=[
        {'AttributeName': 'user_id', 'KeyType': 'HASH'},
        {'AttributeName': 'session_id', 'KeyType': 'RANGE'}
    ],
    AttributeDefinitions=[
        {'AttributeName': 'user_id', 'AttributeType': 'S'},
        {'AttributeName': 'session_id', 'AttributeType': 'S'}
    ],
    BillingMode='PAY_PER_REQUEST'
)

print("✅ Table created: AgentChatSessions")

