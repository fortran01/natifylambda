"""Main module."""
import json
import boto3

def handler(event, context):
    ec2_client = boto3.client('ec2')
    vpc_id = event['VPC_ID']
    
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
