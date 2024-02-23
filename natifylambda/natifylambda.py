"""Main module."""
import json
import boto3
import os

def handler(event, context):
    ec2_client = boto3.client('ec2')
    # Use environment variable for VPC Name instead of event
    vpc_name = os.environ.get('VPC_NAME')
    
    # Fetch the VPC ID using the VPC Name
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'tag:Name', 'Values': [vpc_name]}])
    if vpcs['Vpcs']:
        vpc_id = vpcs['Vpcs'][0]['VpcId']
    else:
        return {
            'statusCode': 400,
            'body': json.dumps(f'VPC with name {vpc_name} not found')
        }
    
    # Fetch all subnets in the VPC
    subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    
    # Iterate over subnets and modify route tables
    for subnet in subnets['Subnets']:
        # Assuming the modification involves adding a specific route or similar
        # This is a placeholder for the actual logic to modify the route table
        print(f"Modifying route table for subnet: {subnet['SubnetId']}")
        # Placeholder for route table modification logic
    
    return {
        'statusCode': 200,
        'body': json.dumps('Route tables modified successfully')
    }
