from aws_cdk import Stack, CfnParameter
import aws_cdk.aws_lambda as lambda_
from constructs import Construct

class NatifyLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define a CloudFormation parameter for the VPC Name
        vpc_name_param = CfnParameter(self, "VpcName", type="String", description="The name of the VPC")

        # Use the parameter value
        vpc_name = vpc_name_param.value_as_string

        # Define the Lambda function
        natify_lambda = lambda_.Function(
            self, "NatifyLambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="natifylambda.natifylambda.handler",
            code=lambda_.Code.from_asset("natifylambda"),
            environment={
                "VPC_NAME": vpc_name
            }
        )

        # No need to iterate over private subnets and modify route tables here
        # The Lambda function defined in handler.py will handle route table modifications
