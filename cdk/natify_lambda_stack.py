from aws_cdk import (
    Stack, 
    CfnParameter, 
    aws_s3 as s3, 
    aws_iam as iam, 
    aws_events as events, 
    aws_events_targets as targets, 
    aws_lambda as lambda_, 
    aws_lambda_destinations as destinations, 
    Duration,
    aws_cloudformation as cfn,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks
)
from constructs import Construct
from natifylambda import __version__ as natifylambda_version
import aws_cdk.aws_lambda_event_sources as lambda_event_sources
import uuid

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
                                "ec2:ModifySubnetAttribute",
                                "lambda:PutFunctionConcurrency",  # Permission to update function concurrency
                                "states:UpdateStateMachine",  # Added permission to disable the state machine
                                "states:ListStateMachines",
                                "events:ListRules"
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
            timeout=Duration.seconds(20),
            environment={
                "VPC_NAME": vpc_name
            }
        )

        # Define a Step Function with a Wait state before invoking the Lambda function
        wait_state = sfn.Wait(self, "Wait40Seconds", time=sfn.WaitTime.duration(Duration.seconds(40)))
        lambda_invoke_state = tasks.LambdaInvoke(
            self, "InvokeUserLambda",
            lambda_function=user_lambda,
            input_path="$",  # Modified to pass the entire input
            result_path="$.Result"
        )
        definition = sfn.DefinitionBody.from_chainable(wait_state.next(lambda_invoke_state))
        
        unique_id = str(uuid.uuid4())
        state_machine_name = "NatifyLambdaStateMachine-" + unique_id

        state_machine = sfn.StateMachine(
            self, "StateMachine",
            state_machine_name=state_machine_name,
            definition_body=definition,
            timeout=Duration.minutes(5)
        )

        # Update the user_lambda environment to include STATE_MACHINE_ARN
        user_lambda.add_environment("NATIFYLAMBDA_STATE_MACHINE_NAME", state_machine_name)

        # Name the event rule and inject it as an environment variable to AWS Lambda
        event_rule_name = "NatifyLambdaStateMachineRule-" + unique_id
        rule = events.Rule(
            self, "Rule",
            rule_name=event_rule_name,
            schedule=events.Schedule.expression("rate(1 minute)"),
            targets=[targets.SfnStateMachine(state_machine)]
        )

        # Inject the event rule name as an environment variable to the Lambda function
        user_lambda.add_environment("EVENT_RULE_NAME", event_rule_name)

