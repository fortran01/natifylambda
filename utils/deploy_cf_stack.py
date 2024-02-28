import subprocess
import time
import json
import click
import requests

@click.command()
@click.option('--profile', default='default', help='AWS CLI profile to use for deployment.')
def main(profile):
    if wait_for_github_actions():
        deploy_stack("DownloaderLambdaStack", "cdk.out/0_DownloaderLambdaStack.yaml", profile)
        deploy_stack("NatifyStack", "cdk.out/1_NatifyStack.yaml", profile, parameters=[
            {"ParameterKey": "VpcName", "ParameterValue": "Production-VPC"},
            {"ParameterKey": "NatInstanceType", "ParameterValue": "t4g.nano"},
            {"ParameterKey": "AvailabilityZone", "ParameterValue": "us-west-2a"},
            {"ParameterKey": "VpcId", "ParameterValue": "/accelerator/network/vpc/Production-VPC/id"},
            {"ParameterKey": "PublicSubnetId", "ParameterValue": "	/accelerator/network/vpc/Production-VPC/subnet/Production-VPC-PublicSubnet1A/id"}
        ])
    else:
        print("GitHub Actions are not all green or OK. Aborting deployment.")

def wait_for_github_actions():
    """
    Poll GitHub Actions workflow 'release.yml' for the repository 'fortran01/natifylambda' until all runs are green or OK.
    
    :return: True if all runs are green or OK after polling, False otherwise.
    """
    url = "https://api.github.com/repos/fortran01/natifylambda/actions/workflows/release.yml/runs"
    max_attempts = 10
    attempt = 0
    while attempt < max_attempts:
        try:
            response = requests.get(url)
            response.raise_for_status()
            workflow_runs = response.json()['workflow_runs']
            all_success = all(run['conclusion'] == 'success' for run in workflow_runs)
            if all_success:
                return True
            else:
                print(f"Attempt {attempt + 1} of {max_attempts}: GitHub Actions are not all green. Retrying in 30 seconds...")
                time.sleep(10)  # Wait for 30 seconds before the next poll
                attempt += 1
        except requests.RequestException as e:
            print(f"Failed to check GitHub Actions workflow runs: {e}")
            return False
    print("GitHub Actions did not complete successfully after maximum attempts. Aborting deployment.")
    return False

def deploy_stack(stack_name, template_file, profile, parameters=None):
    """
    Deploy or update a CloudFormation stack and poll its status until completion.
    
    :param stack_name: Name of the CloudFormation stack to deploy or update.
    :param template_file: Path to the CloudFormation template file.
    :param profile: AWS CLI profile to use for deployment.
    :param parameters: A list of parameters to pass to the stack in the format [{"ParameterKey": "key", "ParameterValue": "value"}].
    """
    # Check if stack exists
    check_stack_command = [
        "aws", "cloudformation", "describe-stacks",
        "--stack-name", stack_name,
        "--profile", profile
    ]
    
    stack_exists = True
    try:
        subprocess.run(check_stack_command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        stack_exists = False
    
    # Prepare parameters for CLI command if any
    parameters_cli = []
    if parameters:
        parameters_cli = ["--parameters"] + [json.dumps(parameters)]
    
    action = "update-stack" if stack_exists else "create-stack"
    deploy_command = [
        "aws", "cloudformation", action,
        "--stack-name", stack_name,
        "--template-body", f"file://{template_file}",
        "--capabilities", "CAPABILITY_IAM",
        "--profile", profile
    ] + parameters_cli
    
    try:
        # Execute the deployment command
        result = subprocess.run(deploy_command, check=True, capture_output=True, text=True)
        if stack_exists:
            print(f"Stack {stack_name} update initiated.")
        else:
            print(f"Stack {stack_name} creation initiated.")
    except subprocess.CalledProcessError as e:
        error_message = e.stderr
        if "ValidationError" in error_message and "No updates are to be performed" in error_message:
            print(f"No updates to perform on stack {stack_name}.")
        else:
            print(f"Failed to initiate stack {stack_name} update or creation: {e}. Error: {e.stderr}")
            return
    
    # Poll stack status
    while True:
        status_command = [
            "aws", "cloudformation", "describe-stacks",
            "--stack-name", stack_name,
            "--profile", profile,
            "--query", "Stacks[0].StackStatus",
            "--output", "text"
        ]
        
        try:
            result = subprocess.run(status_command, check=True, capture_output=True, text=True)
            status = result.stdout.strip()
            print(f"Current status of stack {stack_name}: {status}")
            
            if status in ["UPDATE_COMPLETE", "CREATE_COMPLETE"]:
                print(f"Stack {stack_name} update or creation completed successfully.")
                break
            elif "FAILED" in status or "ROLLBACK" in status:
                raise Exception(f"Stack {stack_name} update or creation failed with status: {status}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to get status of stack {stack_name}: {e}")
            break
        
        time.sleep(10)

if __name__ == "__main__":
    main()
