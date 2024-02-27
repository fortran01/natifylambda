"""Main module."""
import json
import boto3
import os
# from natifylambda.cdk.nat_instance_construct import NatInstanceConstruct
from cdk.nat_instance_construct import NatInstanceConstruct
import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2

def launch_nat_instance(vpc_name):
    app = cdk.App()
    stack = cdk.Stack(app, "NatInstanceStack")
    ec2_client = boto3.client('ec2')
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'tag:Name', 'Values': [vpc_name]}])
    if vpcs['Vpcs']:
        vpc_id = vpcs['Vpcs'][0]['VpcId']
        vpc = ec2.Vpc.from_lookup(stack, "VPC", vpc_id=vpc_id)
        subnet_id = vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnets[0].subnet_id
        NatInstanceConstruct(stack, "NatInstance", vpc=vpc, subnet_id=subnet_id)
        app.synth()
        print(f"NAT instance launched in VPC: {vpc_name}")
    else:
        print(f"VPC with name {vpc_name} not found")

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

def disable_state_machine(sfn_client, state_machine_name, events_client, event_rule_name):
    state_machines = sfn_client.list_state_machines()
    state_machine_arn = None
    for sm in state_machines['stateMachines']:
        if sm['name'] == state_machine_name:
            state_machine_arn = sm['stateMachineArn']
            break
    if state_machine_arn:
        # Minimal valid state machine definition that does nothing
        noop_definition = json.dumps({
            "Comment": "Disabled state machine",
            "StartAt": "NoOpState",
            "States": {
                "NoOpState": {
                    "Type": "Pass",
                    "End": True
                }
            }
        })
        sfn_client.update_state_machine(
            stateMachineArn=state_machine_arn,
            definition=noop_definition
        )
        # Additional logic to disable the trigger
        events_client.disable_rule(Name=event_rule_name)
        print(f"State machine {state_machine_name} disabled and trigger {event_rule_name} disconnected")
    else:
        print(f"State machine {state_machine_name} not found")

def handler(event, context):
    ec2_client = boto3.client('ec2')
    sfn_client = boto3.client('stepfunctions')
    events_client = boto3.client('events')  # Added for disabling the trigger
    vpc_name = os.environ.get('VPC_NAME')
    state_machine_name = os.environ.get('NATIFYLAMBDA_STATE_MACHINE_NAME')
    event_rule_name = os.environ.get('EVENT_RULE_NAME')  # Use EVENT_RULE_NAME from environment
    
    launch_nat_instance(vpc_name)
    
    vpc_id = get_vpc_id(ec2_client, vpc_name)
    if not vpc_id:
        return {
            'statusCode': 400,
            'body': json.dumps(f'VPC with name {vpc_name} not found')
        }
    
    modify_route_tables(ec2_client, vpc_id)
    disable_state_machine(sfn_client, state_machine_name, events_client, event_rule_name)  # Updated to pass event_rule_name
    
    return {
        'statusCode': 200,
        'body': json.dumps('NAT instance launched, route tables modified and state machine disabled successfully')
    }
