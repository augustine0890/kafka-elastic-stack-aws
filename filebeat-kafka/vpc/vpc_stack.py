from aws_cdk import (
    core,
    aws_ec2 as ec2,
)
from helpers.constants import constants


class VpcStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        self.vpc = ec2.Vpc(self, "fk-vpc", max_azs=3,)
        core.Tag.add(self.vpc, "project", constants["PROJECT_TAG"])
        # Tags.of(self.vpc).add("project", constants["PROJECT_TAG"])
    @property
    def get_vpc(self):
        return self.vpc
    
    @property
    def get_vpc_public_subnet_ids(self):
        return self.vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnet_ids
    
    @property
    def get_vpc_private_subnet_ids(self):
        return self.vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE).subnet_ids