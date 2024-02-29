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
                route.get('DestinationCidrBlock') == '0.0.0.0/0' for route in routes
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

def modify_security_group(ec2_client, nat_sg_id, vpc_id):
    """
    Modifies the specified security group to allow all inbound traffic from the VPC CIDR block.
    Handles the case where the rule already exists.
    
    :param ec2_client: The EC2 client to use for making AWS requests.
    :param nat_sg_id: The ID of the NAT instance's security group.
    :param vpc_id: The ID of the VPC.
    """
    vpc = ec2_client.describe_vpcs(VpcIds=[vpc_id])
    vpc_cidr = vpc['Vpcs'][0]['CidrBlock']
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=nat_sg_id,
            IpPermissions=[
                {
                    'IpProtocol': '-1',
                    'FromPort': -1,
                    'ToPort': -1,
                    'IpRanges': [{'CidrIp': vpc_cidr}]
                }
            ]
        )
        print(f"Inbound rule added to security group {nat_sg_id} to allow all traffic from VPC CIDR {vpc_cidr}")
    except ec2_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'InvalidPermission.Duplicate':
            print(f"Rule already exists: Inbound traffic from VPC CIDR {vpc_cidr} is already allowed for security group {nat_sg_id}")
        else:
            raise

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

def stop_nat_instance_source_dest_check(ec2_client, nat_instance_id):
    """
    Stops the source/destination check on the NAT instance to allow it to forward traffic.
    
    :param ec2_client: The EC2 client to use for making AWS requests.
    :param nat_instance_id: The ID of the NAT instance.
    """
    ec2_client.modify_instance_attribute(
        InstanceId=nat_instance_id,
        SourceDestCheck={'Value': False}
    )
    print(f"Source/destination check stopped for NAT instance ID: {nat_instance_id}")

def handler(event, context):
    ec2_client = boto3.client('ec2')
    sfn_client = boto3.client('stepfunctions')
    events_client = boto3.client('events')  # Added for disabling the trigger
    vpc_id = os.environ.get('VPC_ID')
    state_machine_name = os.environ.get('NATIFYLAMBDA_STATE_MACHINE_NAME')
    event_rule_name = os.environ.get('EVENT_RULE_NAME')
    nat_instance_id = os.environ.get('NAT_INSTANCE_ID')
    nat_sg_id = os.environ.get('NAT_SG_ID')
    
    if not vpc_id or not nat_instance_id or not nat_sg_id:
        return {
            'statusCode': 400,
            'body': json.dumps('VPC ID, NAT instance ID, or NAT security group ID not found in environment variables')
        }
    
    modify_route_tables(ec2_client, vpc_id, nat_instance_id)
    modify_security_group(ec2_client, nat_sg_id, vpc_id)
    disable_state_machine(sfn_client, state_machine_name, events_client, event_rule_name)
    stop_nat_instance_source_dest_check(ec2_client, nat_instance_id)
    
    print(f"NAT instance ID: {nat_instance_id} and security group ID: {nat_sg_id} used for operations")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Operations completed successfully',
            'details': {
                'route_tables': 'modified',
                'security_group': 'updated',
                'state_machine': 'disabled',
                'source_dest_check': 'stopped'
            }
        })
    }
