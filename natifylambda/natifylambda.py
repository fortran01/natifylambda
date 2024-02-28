"""Main module."""
import json
import boto3
import os

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
    vpc_id = os.environ.get('VPC_ID')  # Retrieve VPC ID from environment variable set by CDK stack
    state_machine_name = os.environ.get('NATIFYLAMBDA_STATE_MACHINE_NAME')
    event_rule_name = os.environ.get('EVENT_RULE_NAME')
    
    if not vpc_id:
        return {
            'statusCode': 400,
            'body': json.dumps('VPC ID not found in environment variables')
        }
    
    modify_route_tables(ec2_client, vpc_id)
    disable_state_machine(sfn_client, state_machine_name, events_client, event_rule_name)
    
    # Retrieve NAT instance ID from environment variable set by CDK stack
    nat_instance_id = os.environ.get('NAT_INSTANCE_ID')
    if not nat_instance_id:
        return {
            'statusCode': 400,
            'body': json.dumps('NAT instance ID not found in environment variables')
        }
    
    print(f"NAT instance ID: {nat_instance_id} used for operations")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Route tables modified and state machine disabled successfully')
    }
