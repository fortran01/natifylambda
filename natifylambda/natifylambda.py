"""Main module."""
import json
import boto3
import os

def get_private_subnets(ec2_client, vpc_id):
    """
    Retrieves all private subnets for a given VPC ID along with their names, 
    lowercases the subnet name, and matches "private".
    
    :param ec2_client: The EC2 client to use for making AWS requests.
    :param vpc_id: The ID of the VPC for which to retrieve private subnets.
    :return: A list of tuples containing subnet IDs and their names that are private within the specified VPC.
    """
    subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    private_subnets_info = []
    for subnet in subnets['Subnets']:
        for tag in subnet['Tags']:
            if tag['Key'].lower() == 'name' and 'private' in tag['Value'].lower():
                private_subnets_info.append((subnet['SubnetId'], tag['Value']))
                break
    return private_subnets_info

def modify_route_tables(ec2_client, vpc_id, nat_instance_id):
    private_subnets_info = get_private_subnets(ec2_client, vpc_id)
    for subnet_id, subnet_name in private_subnets_info:
        print(f"Modifying route table for private subnet: {subnet_id} - {subnet_name}")
        # Retrieve the route table associated with the private subnet
        route_tables = ec2_client.describe_route_tables(
            Filters=[{'Name': 'association.subnet-id', 'Values': [subnet_id]}]
        )
        for rt in route_tables['RouteTables']:
            # Retrieve route table name
            rt_name = next(
                (tag['Value'] for tag in rt['Tags'] if tag['Key'] == 'Name'), 
                'Unnamed'
            )
            # Check if a route to 0.0.0.0/0 exists
            routes = rt['Routes']
            default_route_exists = any(
                route['DestinationCidrBlock'] == '0.0.0.0/0' for route in routes
            )
            if default_route_exists:
                # Modify the existing default route to point to the NAT instance
                ec2_client.replace_route(
                    RouteTableId=rt['RouteTableId'], 
                    DestinationCidrBlock='0.0.0.0/0', 
                    InstanceId=nat_instance_id
                )
                action = "modified"
            else:
                # Create a new default route that points to the NAT instance
                ec2_client.create_route(
                    RouteTableId=rt['RouteTableId'], 
                    DestinationCidrBlock='0.0.0.0/0', 
                    InstanceId=nat_instance_id
                )
                action = "added"
            print(
                f"Default route {action} for subnet: {subnet_id} to point to NAT instance: "
                f"{nat_instance_id} in route table: {rt['RouteTableId']} ({rt_name})"
            )

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
    nat_instance_id = os.environ.get('NAT_INSTANCE_ID')  # Retrieve NAT instance ID from environment variable set by CDK stack
    
    if not vpc_id or not nat_instance_id:
        return {
            'statusCode': 400,
            'body': json.dumps('VPC ID or NAT instance ID not found in environment variables')
        }
    
    modify_route_tables(ec2_client, vpc_id, nat_instance_id)
    disable_state_machine(sfn_client, state_machine_name, events_client, event_rule_name)
    
    print(f"NAT instance ID: {nat_instance_id} used for operations")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Route tables modified and state machine disabled successfully')
    }
