import aws_cdk.aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import CfnOutput
from constructs import Construct

class NatInstanceConstruct(Construct):
    def __init__(self, scope: Construct, id: str, vpc: ec2.IVpc, subnet_id: str, instance_type: str = "t4g.nano", **kwargs):
        super().__init__(scope, id, **kwargs)

        # Define the IAM role for the NAT instance
        nat_instance_role = iam.Role(self, "NatInstanceRole",
                                     assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
                                     managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonEC2RoleforSSM")])

        # Define the security group for the NAT instance
        nat_instance_sg = ec2.SecurityGroup(self, "NatInstanceSG",
                                            vpc=vpc,
                                            description="Security group for NAT instance",
                                            allow_all_outbound=True)

        # Define the AMI for the NAT instance, narrowing down to only the arm64 architecture
        nat_instance_ami = ec2.MachineImage.lookup(name="fck-nat-al2023-*",
                                                   owners=["568608671756"],
                                                   filters={"architecture": ["arm64"]})

        # Specify the subnet where the NAT instance will be launched
        subnet_selection = ec2.SubnetSelection(subnets=[ec2.Subnet.from_subnet_id(self, "PublicSubnet", subnet_id)])

        # Create the NAT instance in the specified public subnet without specifying a key pair
        nat_instance = ec2.Instance(self, "NatInstance",
                                    instance_type=ec2.InstanceType(instance_type),
                                    machine_image=nat_instance_ami,
                                    vpc=vpc,
                                    role=nat_instance_role,
                                    security_group=nat_instance_sg,
                                    vpc_subnets=subnet_selection)

        # Output the NAT instance ID
        CfnOutput(self, "NatInstanceId", value=nat_instance.instance_id)
