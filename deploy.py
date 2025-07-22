import argparse
import boto3
import json
import time

parser = argparse.ArgumentParser(
    description="Create or update an agent runtime")
parser.add_argument("--region", default="us-east-1", help="AWS region")
parser.add_argument("--account", required=True, help="AWS account ID")
parser.add_argument("--app", required=True, help="Agent runtime name")
parser.add_argument("--image", required=True, help="Agent runtime image")
args = parser.parse_args()
account = args.account
app = args.app
image = args.image
region = args.region

# Initialize IAM and Bedrock clients
iam_client = boto3.client("iam")
client = boto3.client("bedrock-agentcore-control")

# Check if the IAM role exists
role_name = "AgentRuntimeRole"
role_arn = f"arn:aws:iam::{account}:role/{role_name}"


def create_agent_runtime_role():
    """Create the IAM role for Bedrock Agent Core Runtime if it doesn't exist"""
    try:
        # Check if role already exists
        print("checking if role exists\n")
        response = iam_client.get_role(RoleName=role_name)

    except iam_client.exceptions.NoSuchEntityException:

        # Create trust policy
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AssumeRolePolicy",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "bedrock-agentcore.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {
                            "aws:SourceAccount": account
                        },
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account}:*"
                        }
                    }
                }
            ]
        }

        # Create permission policy
        permission_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ECRImageAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer"
                    ],
                    "Resource": [
                        f"arn:aws:ecr:{region}:{account}:repository/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:DescribeLogStreams",
                        "logs:CreateLogGroup"
                    ],
                    "Resource": [
                        f"arn:aws:logs:{region}:{account}:log-group:/aws/bedrock-agentcore/runtimes/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:DescribeLogGroups"
                    ],
                    "Resource": [
                        f"arn:aws:logs:{region}:{account}:log-group:*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": [
                        f"arn:aws:logs:{region}:{account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                    ]
                },
                {
                    "Sid": "ECRTokenAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetAuthorizationToken"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets"
                    ],
                    "Resource": ["*"]
                },
                {
                    "Effect": "Allow",
                    "Resource": "*",
                    "Action": "cloudwatch:PutMetricData",
                    "Condition": {
                        "StringEquals": {
                            "cloudwatch:namespace": "bedrock-agentcore"
                        }
                    }
                },
                {
                    "Sid": "GetAgentAccessToken",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default/workload-identity/{app}-*"
                    ]
                },
                {
                    "Sid": "BedrockModelInvocation",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream"
                    ],
                    "Resource": [
                        "arn:aws:bedrock:*::foundation-model/*",
                        f"arn:aws:bedrock:{region}:{account}:*"
                    ]
                }
            ]
        }

        # Create the role with trust policy
        print("creating runtime role\n")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="IAM role for Bedrock Agent Core Runtime"
        )

        # Create and attach the inline policy
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="BedrockAgentCoreRuntimePolicy",
            PolicyDocument=json.dumps(permission_policy)
        )

        # Wait a moment for IAM role to propagate
        time.sleep(10)
        return response["Role"]["Arn"]

    except Exception as e:
        print(f"Error creating IAM role: {e}")
        raise


# Create the role if it doesn't exist
create_agent_runtime_role()


def get_agent_runtime_by_name(name):
    """Check if an agent runtime with the given name exists"""
    try:
        # List all agent runtimes and filter by name
        print("listing agent runtimes\n")
        response = client.list_agent_runtimes()
        for runtime in response.get("agentRuntimes", []):
            if runtime.get("agentRuntimeName") == name:
                return runtime

        # Handle pagination if there are more results
        while "nextToken" in response:
            response = client.list_agent_runtimes(
                nextToken=response["nextToken"])
            for runtime in response.get("agentRuntimes", []):
                if runtime.get("agentRuntimeName") == name:
                    return runtime

        return None

    except Exception as e:
        print(f"Error checking for existing agent runtime: {e}")
        return None


# Check if the agent runtime already exists
existing_runtime = get_agent_runtime_by_name(app)

if existing_runtime:

    # Update the existing agent runtime
    print(f"Updating existing agent runtime: {app}\n")
    runtime_id = existing_runtime["agentRuntimeId"]

    response = client.update_agent_runtime(
        agentRuntimeId=runtime_id,
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": image
            }
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        protocolConfiguration={"serverProtocol": "HTTP"},
        roleArn=role_arn
    )
    print(f"Updated agent runtime: {response["agentRuntimeArn"]}\n")

else:

    # Create a new agent runtime
    print(f"Creating new agent runtime: {app}\n")
    response = client.create_agent_runtime(
        agentRuntimeName=app,
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": image
            }
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        protocolConfiguration={"serverProtocol": "HTTP"},
        roleArn=role_arn
    )

    print(f"Created agent runtime: {response["agentRuntimeArn"]}\n")

# Write the ARN to a file for reference (used by client.py)
with open("agent_runtime_arn", "w") as f:
    f.write(response["agentRuntimeArn"])
