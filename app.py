import aws_cdk as cdk
from aws_cdk import App
from cdk.natify_stack import NatifyStack
from cdk.downloader_lambda_stack import DownloaderLambdaStack

app = App()
NatifyStack(app, "NatifyStack")
DownloaderLambdaStack(app, "DownloaderLambdaStack")
app.synth()
