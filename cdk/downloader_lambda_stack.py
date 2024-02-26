from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
)
from constructs import Construct
from natifylambda import __version__ as natifylambda_version

class DownloaderLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define the function name early on so it can be reused
        function_name = f"downloader_lambda_{natifylambda_version.replace('.', '_')}"

        # Define the IAM role for the downloader_lambda
        downloader_lambda_role = iam.Role(
            self, "DownloaderLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "DownloaderLambdaPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:PutObject"],
                            resources=["arn:aws:s3:::cdk-hnb659fds-assets-*/*"]
                        ),
                        iam.PolicyStatement(
                            actions=["lambda:PutFunctionConcurrency", "lambda:UpdateFunctionCode"],
                            resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:{function_name}"]
                        )
                    ]
                )
            },
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Define the Lambda function to download and upload the zip file
        # that contains the natifylambda code
        downloader_lambda = lambda_.Function(
            self, "DownloaderLambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.InlineCode(self.get_lambda_code()),
            environment={
                "BUCKET_NAME": f"cdk-hnb659fds-assets-{self.account}-{self.region}",
                "NATIFYLAMBDA_VERSION": natifylambda_version
            },
            role=downloader_lambda_role,
            timeout=Duration.seconds(10),
            reserved_concurrent_executions=None,  # Use the unreserved account concurrency
            # Version the lambda function
            function_name=function_name
        )

        # Trigger the downloader_lambda immediately and only once using AWS Events Rule
        rule = events.Rule(
            self, "Rule",
            schedule=events.Schedule.expression("rate(1 minute)"),
            targets=[targets.LambdaFunction(downloader_lambda)]
        )

    def get_lambda_code(self) -> str:
        return f"""
import urllib.request
import boto3
import os
import datetime

def handler(event, context):
    print(f"Download started at: {{datetime.datetime.now()}}")
    s3 = boto3.client('s3')
    version = os.environ.get("NATIFYLAMBDA_VERSION", "default-version")
    url = "https://github.com/fortran01/natifylambda/releases/latest/download/natifylambda-{{version}}.zip"
    file_name = "/tmp/downloaded.zip"
    urllib.request.urlretrieve(url.format(version=version), file_name)
    print(f"Download completed at: {{datetime.datetime.now()}}")
    bucket_name = os.environ.get("BUCKET_NAME", "default-bucket-name")
    s3.upload_file(file_name, bucket_name, f"natifylambda-{{version}}.zip")
    
    # Disable the lambda function after its first run by setting concurrency to 0
    lambda_client = boto3.client('lambda')
    lambda_client.put_function_concurrency(
        FunctionName=context.function_name,
        ReservedConcurrentExecutions=0
    )
        """

