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
    aws_stepfunctions_tasks as tasks,
    aws_ec2 as ec2,
    aws_ssm as ssm,
    CfnOutput, # Added for CF output
)
from constructs import Construct
from natifylambda import __version__ as natifylambda_version
import aws_cdk.aws_lambda_event_sources as lambda_event_sources
import uuid

class NatifyStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define a CloudFormation parameter for the VPC Name
        vpc_name_param = CfnParameter(
            self, "VpcName", 
            type="String", 
            description="The name of the VPC"
        )
        vpc_name = vpc_name_param.value_as_string

        # Define a CloudFormation parameter for the NAT instance type, with a default value
        nat_instance_type_param = CfnParameter(
            self, "NatInstanceType", 
            type="String", 
            default="t4g.nano", 
            description="The instance type for the NAT instance"
        )
        nat_instance_type = nat_instance_type_param.value_as_string

        # CloudFormation parameter for VPC ID retrieval
        vpc_id_param = CfnParameter(
            self, "VpcId",
            type="AWS::SSM::Parameter::Value<String>",
            description=("The VPC ID, automatically retrieved from SSM Parameter Store. "
                         "Syntax: /accelerator/network/vpc/{vpc_name}/id")
        )
        vpc_id = vpc_id_param.value_as_string

        # CloudFormation parameter for Public Subnet ID retrieval
        public_subnet_id_param = CfnParameter(
            self, "PublicSubnetId",
            type="AWS::SSM::Parameter::Value<String>",
            description=("The Public Subnet ID, automatically retrieved from SSM Parameter Store. "
                         "Syntax: /accelerator/network/vpc/{vpc_name}/subnet/{public_subnet_name}/id")
        )
        public_subnet_id = public_subnet_id_param.value_as_string

        # Define a CloudFormation parameter for the Availability Zone
        availability_zone_param = CfnParameter(
            self, "AvailabilityZone",
            type="String",
            default="us-west-2a",
            description="The Availability Zone for the NAT instance"
        )
        availability_zone = availability_zone_param.value_as_string

        # Launch the NAT instance using CDK before defining the Lambda function
        nat_instance = self.launch_nat_instance(vpc_id, nat_instance_type, public_subnet_id, availability_zone)

        # Output the NAT instance ID as a CloudFormation output
        CfnOutput(self, "NatInstanceId", value=nat_instance.instance_id)

        # Reference the S3 bucket from the DownloaderLambdaStack
        s3_bucket = s3.Bucket.from_bucket_name(
            self, "CDKBootstrapBucket", 
            bucket_name=f"cdk-hnb659fds-assets-{self.account}-{self.region}"
        )

        lambda_execution_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            inline_policies={
                "NatifyLambdaPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "ec2:DescribeVpcs",
                                "ec2:DescribeSubnets",
                                "ec2:ModifySubnetAttribute",
                                "ec2:DescribeRouteTables",
                                "ec2:ReplaceRoute",
                                "lambda:PutFunctionConcurrency",  # Permission to update function concurrency
                                "states:UpdateStateMachine",  # Added permission to disable the state machine
                                "states:ListStateMachines",
                                "events:ListRules",
                                "events:DisableRule"
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
                "VPC_NAME": vpc_name,
                "VPC_ID": vpc_id,
                "NAT_INSTANCE_ID": nat_instance.instance_id  # Add NAT instance ID as an environment variable
            }
        )

        # Define a Step Function with a Wait state before invoking the Lambda function
        wait_state = sfn.Wait(
            self, "Wait40Seconds", 
            time=sfn.WaitTime.duration(Duration.seconds(40))
        )
        lambda_invoke_state = tasks.LambdaInvoke(
            self, "InvokeUserLambda",
            lambda_function=user_lambda,
            input_path="$",  # Modified to pass the entire input
            result_path="$.Result"
        )
        definition = sfn.DefinitionBody.from_chainable(wait_state.next(lambda_invoke_state))
        
        unique_id = str(uuid.uuid4())[:8]  # Truncate UUID to ensure length constraints
        state_machine_name = "NatifySM-" + unique_id
        state_machine_name = state_machine_name[:64]  # Ensure state machine name is within AWS limits

        state_machine = sfn.StateMachine(
            self, "StateMachine",
            state_machine_name=state_machine_name,
            definition_body=definition,
            timeout=Duration.minutes(5)
        )

        # Update the user_lambda environment to include STATE_MACHINE_ARN
        user_lambda.add_environment("NATIFYLAMBDA_STATE_MACHINE_NAME", state_machine_name)

        # Name the event rule and inject it as an environment variable to AWS Lambda
        event_rule_name = "NatifyRule-" + unique_id
        event_rule_name = event_rule_name[:64]  # Ensure event rule name is within AWS limits
        rule = events.Rule(
            self, "Rule",
            rule_name=event_rule_name,
            schedule=events.Schedule.expression("rate(1 minute)"),
            targets=[targets.SfnStateMachine(state_machine)]
        )

        # Inject the event rule name as an environment variable to the Lambda function
        user_lambda.add_environment("EVENT_RULE_NAME", event_rule_name)

    def launch_nat_instance(self, vpc_id, nat_instance_type, public_subnet_id, availability_zone):
        # Lookup the VPC using the VPC ID
        vpc = ec2.Vpc.from_vpc_attributes(
            self, "Vpc",
            vpc_id=vpc_id,
            availability_zones=[availability_zone],
            public_subnet_ids=[public_subnet_id]
        )
        
        nat_sg = ec2.SecurityGroup(
            self, "NatInstanceSG",
            vpc=vpc,
            description="Security Group for NAT instance",
            allow_all_outbound=True
        )
        
        nat_instance = ec2.Instance(
            self, "NatInstance",
            instance_type=ec2.InstanceType(nat_instance_type),
            machine_image=ec2.MachineImage.generic_linux({
                "us-west-2": "ami-0aac6113247ca0b3f"
            }),
            vpc=vpc,
            security_group=nat_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            associate_public_ip_address=True
        )

        # Disable source/destination checks on the NAT instance
        nat_instance.source_dest_check = False

        return nat_instance
