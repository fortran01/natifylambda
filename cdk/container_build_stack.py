from aws_cdk import (
    Stack,
    aws_codebuild as codebuild,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    SecretValue
)
from constructs import Construct


class ContainerBuildStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create an ECR repository
        ecr_repo = ecr.Repository(
            self, "NatifyLambdaECRRepo",
            repository_name="natifylambda"
        )

        # Define the source action from GitHub
        source_output = codepipeline.Artifact()
        github_source_action = codepipeline_actions.GitHubSourceAction(
            action_name="GitHub_Source",
            owner="fortran01",
            repo="natifylambda",
            oauth_token=SecretValue.secrets_manager("natifylambda/github-token"),
            output=source_output,
            branch="main",  # Optional: default is master
            trigger=codepipeline_actions.GitHubTrigger.POLL  # Optional: default is POLL
        )

        # Define the build project
        build_project = codebuild.PipelineProject(
            self, "NatifyLambdaBuild",
            project_name="NatifyLambdaBuild",
            build_spec=codebuild.BuildSpec.from_object({
                'version': '0.2',
                'phases': {
                    'pre_build': {
                        'commands': [
                            'echo Logging in to Amazon ECR...',
                            '$(aws ecr get-login --no-include-email --region $AWS_DEFAULT_REGION)'
                        ]
                    },
                    'build': {
                        'commands': [
                            'echo Build started on `date`',
                            'echo Building the Docker image...',
                            'docker build -t $REPOSITORY_URI:latest .',
                        ]
                    },
                    'post_build': {
                        'commands': [
                            'echo Build completed on `date`',
                            'echo Pushing the Docker image...',
                            'docker push $REPOSITORY_URI:latest',
                            'echo Writing image definitions file...',
                            'printf \'[{"name":"natifylambda","imageUri":"%s"}]\' $REPOSITORY_URI:latest > imagedefinitions.json'
                        ]
                    }
                },
                'artifacts': {
                    'files': [
                        'imagedefinitions.json'
                    ]
                }
            }),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                privileged=True,
            ),
            environment_variables={
                'REPOSITORY_URI': codebuild.BuildEnvironmentVariable(value=ecr_repo.repository_uri)
            }
        )

        # Define the pipeline
        pipeline = codepipeline.Pipeline(
            self, "NatifyLambdaPipeline",
            pipeline_name="NatifyLambdaPipeline",
            pipeline_type=codepipeline.PipelineType.V2,
            stages=[
                codepipeline.StageProps(
                    stage_name="Source",
                    actions=[github_source_action]
                ),
                codepipeline.StageProps(
                    stage_name="Build",
                    actions=[
                        codepipeline_actions.CodeBuildAction(
                            action_name="Build",
                            project=build_project,
                            input=source_output,
                            outputs=[codepipeline.Artifact()]  # Optional: if you need the output as input for another action
                        )
                    ]
                )
            ]
        )

        # Grant permissions to the build project to push to the ECR repository
        ecr_repo.grant_pull_push(build_project.role)

