"""Main module."""
import json
import boto3
import os

def get_vpc_id(ec2_client, vpc_name):
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'tag:Name', 'Values': [vpc_name]}])
    if vpcs['Vpcs']:
        return vpcs['Vpcs'][0]['VpcId']
    else:
        return None

def modify_route_tables(ec2_client, vpc_id):
    subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    for subnet in subnets['Subnets']:
        print(f"Modifying route table for subnet: {subnet['SubnetId']}")
        # Placeholder for route table modification logic

def disable_state_machine(sfn_client, state_machine_name):
    state_machines = sfn_client.list_state_machines()
    state_machine_arn = None
    for sm in state_machines['stateMachines']:
        if sm['name'] == state_machine_name:
            state_machine_arn = sm['stateMachineArn']
            break
    if state_machine_arn:
        sfn_client.update_state_machine(
            stateMachineArn=state_machine_arn,
            definition='{"Comment": "Disabled state machine"}',
            roleArn=''  # Assuming the role ARN is not required for disabling
        )
    else:
        print(f"State machine {state_machine_name} not found")

def handler(event, context):
    ec2_client = boto3.client('ec2')
    sfn_client = boto3.client('stepfunctions')
    vpc_name = os.environ.get('VPC_NAME')
    state_machine_name = os.environ.get('NATIFYLAMBDA_STATE_MACHINE_NAME')
    
    vpc_id = get_vpc_id(ec2_client, vpc_name)
    if not vpc_id:
        return {
            'statusCode': 400,
            'body': json.dumps(f'VPC with name {vpc_name} not found')
        }
    
    modify_route_tables(ec2_client, vpc_id)
    disable_state_machine(sfn_client, state_machine_name)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Route tables modified and state machine disabled successfully')
    }
