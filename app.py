import aws_cdk as cdk
from aws_cdk import App
from cdk.natifylambda_stack import NatifyLambdaStack

app = App()
NatifyLambdaStack(app, "NatifyLambdaStack")
app.synth()
