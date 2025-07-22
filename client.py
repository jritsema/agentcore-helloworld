import boto3
import json
import argparse

parser = argparse.ArgumentParser(description="Create an agent runtime")
parser.add_argument("--agent_runtime_arn", required=True, help="Agent runtime arn")
args = parser.parse_args()
agent_runtime_arn = args.agent_runtime_arn
if len(agent_runtime_arn) == 0:
    raise Exception("--agent_runtime_arn is missing")

# Get AWS account ID and region
sts_client = boto3.client("sts")
region = boto3.session.Session().region_name
account = sts_client.get_caller_identity()["Account"]

agent_core_client = boto3.client("bedrock-agentcore")

payload = json.dumps({
    "input": {"prompt": "Explain machine learning in simple terms"}
})

print("invoking agent")
response = agent_core_client.invoke_agent_runtime(
    agentRuntimeArn=agent_runtime_arn,
    runtimeSessionId="dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt",  # Must be 33+ chars
    qualifier="DEFAULT",
    payload=payload,
)

response_body = response["response"].read()
response_data = json.loads(response_body)
print("Agent Response:", response_data)
