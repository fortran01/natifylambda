from aws_cdk import Stack, CfnParameter, aws_s3 as s3, aws_iam as iam, aws_events as events, aws_events_targets as targets, aws_lambda as lambda_, aws_lambda_destinations as destinations
from constructs import Construct
from natifylambda import __version__ as natifylambda_version

class NatifyLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define a CloudFormation parameter for the VPC Name
        vpc_name_param = CfnParameter(self, "VpcName", type="String", description="The name of the VPC")
        vpc_name = vpc_name_param.value_as_string

        # Reference the S3 bucket from the DownloaderLambdaStack
        s3_bucket = s3.Bucket.from_bucket_name(self, "CDKBootstrapBucket", 
                                               bucket_name=f"cdk-hnb659fds-assets-{self.account}-{self.region}")

        lambda_execution_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "NatifyLambdaPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "ec2:DescribeVpcs",
                                "ec2:DescribeSubnets",
                                "ec2:ModifySubnetAttribute"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # Define the Lambda function that uses the uploaded zip file as the code
        user_lambda = lambda_.Function(
            self, "UserLambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="natifylambda.natifylambda.handler",
            # The final stack will eventually use the uploaded zip file as the code
#            code=lambda_.S3Code(bucket=s3_bucket, key=f"natifylambda-{natifylambda_version}.zip"),
            # The following is for generating the assets
            code=lambda_.Code.from_asset("natifylambda"),
            role=lambda_execution_role,  # Assign the created IAM role to the Lambda function
            environment={
                "VPC_NAME": vpc_name
            }
        )