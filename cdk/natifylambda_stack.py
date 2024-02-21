from aws_cdk import Stack, CfnParameter, aws_s3 as s3, aws_iam as iam, aws_events as events, aws_events_targets as targets, aws_lambda as lambda_, aws_lambda_destinations as destinations
from constructs import Construct

class NatifyLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define a CloudFormation parameter for the VPC Name
        vpc_name_param = CfnParameter(self, "VpcName", type="String", description="The name of the VPC")

        # Use the parameter value
        vpc_name = vpc_name_param.value_as_string

        # Define the S3 bucket to upload the zip file
        s3_bucket = s3.Bucket.from_bucket_name(self, "CDKBootstrapBucket", bucket_name=f"cdk-hnb659fds-assets-{self.account}-{self.region}")

        # Define the Lambda function to download and upload the zip file
        downloader_lambda = lambda_.Function(
            self, "DownloaderLambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="downloader.handler",
            code=lambda_.InlineCode("""
import urllib.request
import boto3
import os

def handler(event, context):
    s3 = boto3.client('s3')
    url = "https://x.y.z"
    file_name = "/tmp/downloaded.zip"
    urllib.request.urlretrieve(url, file_name)
    bucket_name = os.environ.get("BUCKET_NAME", "default-bucket-name")
    s3.upload_file(file_name, bucket_name, "natifylambda.zip")
    
    # Disable the lambda function after its first run
    lambda_client = boto3.client('lambda')
    lambda_client.update_function_configuration(
        FunctionName=context.function_name,
        Enabled=False
    )
            """),
            environment={
                "BUCKET_NAME": f"cdk-hnb659fds-assets-{self.account}-{self.region}"
            }
        )

        # Now that downloader_lambda is defined, attach the policy
        downloader_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:PutObject", "lambda:UpdateFunctionConfiguration"],
            resources=[s3_bucket.bucket_arn + "/*", f"arn:aws:lambda:{self.region}:{self.account}:function:{downloader_lambda.function_name}"]
        ))

        # Trigger the downloader_lambda immediately and only once using AWS Events Rule
        rule = events.Rule(
            self, "Rule",
            schedule=events.Schedule.expression("rate(1 minute)"),
            targets=[targets.LambdaFunction(downloader_lambda)]
        )

        # Define another Lambda function that uses the uploaded zip file as the code
        user_lambda = lambda_.Function(
            self, "UserLambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="userlambda.handler",
            # The final stack will eventually use the uploaded zip file as the code
#           code=lambda_.S3Code(bucket=s3_bucket, key="natifylambda.zip"),
            # The following is for generating the assets
            code=lambda_.Code.from_asset("natifylambda"),
            environment={
                "VPC_NAME": vpc_name
            }
        )

