import aws_cdk as cdk
from aws_cdk import App
from cdk.natify_lambda_stack import NatifyLambdaStack
from cdk.downloader_lambda_stack import DownloaderLambdaStack

app = App()
NatifyLambdaStack(app, "NatifyLambdaStack")
DownloaderLambdaStack(app, "DownloaderLambdaStack")
app.synth()
