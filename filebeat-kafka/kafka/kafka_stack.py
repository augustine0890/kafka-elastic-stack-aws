import os
import io

import boto3
from botocore.exceptions import ClientError
import urllib.request
from aws_cdk import (
    core,
    aws_msk as msk,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3_assets as assets,
)

kafka = boto3.client("kafka")

from helpers.constants import constants
from helpers.functions import (
    file_updated,
    kafka_get_brokers,
    ensure_service_linked_role,
    update_kafka_configuration,
    user_data_init,
    instance_add_log_permissions,
)

dirname = os.path.dirname(__file__)
external_ip = urllib.request.urlopen("https://ident.me").read().decode("utf8")


class KafkaStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, vpc_stack, client: bool = True, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        ensure_service_linked_role("kafka.amazonaws.com")
        
        client_properties = assets.Asset(
            self, "client_properties", path=os.path.join(dirname, "client.properties")    
        )
        
        self.kafka_client_security_group = ec2.SecurityGroup(
            self,
            "kafka_client_security_group",
            vpc=vpc_stack.get_vpc,
            description="kafka security group",
            allow_all_outbound=True,
        )
        core.Tag.add(self.kafka_client_security_group, "project", constants["PROJECT_TAG"])
        core.Tag.add(self.kafka_client_security_group, "Name", "kafka_client_sg")
        
        self.kafka_client_security_group.add_ingress_rule(
            ec2.Peer.ipv4(f"{external_ip}/32"), ec2.Port.tcp(22), "from own public ip",    
        )
        
        self.kafka_security_group = ec2.SecurityGroup(
            self,
            "kafka_security_group",
            vpc=vpc_stack.get_vpc,
            description="kafk security group",
            allow_all_outbound=True,
        )
        core.Tag.add(self.kafka_security_group, "project", constants["PROJECT_TAG"])
        core.Tag.add(self.kafka_security_group, "Name", "kafka_sg")
        
        self.kafka_security_group.connections.allow_from(
            self.kafka_security_group,
            ec2.Port.all_traffic(),
            "within kafka",
        )
        self.kafka_security_group.connections.allow_from(
            self.kafka_client_security_group,
            ec2.Port.all_traffic(),
            "from kafka client sg"
        )
        
        self.kafka_client_security_group.connections.allow_from(
            self.kafka_security_group,
            "from kafka",
        )
        
        self.kafka_cluster = msk.CfnCluster(
            self,
            "kafka_cluster",
            broker_node_group_info={
                "clientSubnets": vpc_stack.get_vpc_public_subnet_ids,
                "instanceType": constants["KAFKA_INSTANCE_TYPE"],
                "numberOfBrokerNodes": constants["KAFKA_BROKER_NODES"],
                "securityGroups": [self.kafka_security_group.security_group_id],
            },
            encryption_info={
                "encryptionInTransit": {
                    "InCluster": "true",
                    "clientBroker": "PLAINTEXT",
                },
            },
            cluster_name=constants["PROJECT_TAG"],
            kafka_version=constants["KAFKA_VERSION"],
            number_of_broker_nodes=constants["KAFKA_BROKER_NODES"],
            enhanced_monitoring="DEFAULT",
        )
        core.Tag.add(self.kafka_cluster, "project", constants["PROJECT_TAG"])
        
        if client == True:
            kafka_client_userdata = user_data_init(log_group_name="filebeat-kafka/kafka/instance")
            
            kafka_client_instance = ec2.Instance(
                self,
                "kafka_client",
                instance_type=ec2.InstanceType(constants["KAFKA_CLIENT_INSTANCE"]),
                machine_image=ec2.AmazonLinuxImage(
                    generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2    
                ),
                vpc=vpc_stack.get_vpc,
                vpc_subnets={"subnet_type": ec2.SubnetType.PUBLIC},
                key_name=constants["KEY_PAIR"],
                security_group=self.kafka_client_security_group,
                user_data=kafka_client_userdata,
            )
            core.Tag.add(kafka_client_instance, "project", constants["PROJECT_TAG"])
            
            kafka_client_instance.node.add_dependency(self.kafka_cluster)
            
            access_kafka_policy = iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kafka:ListCluster",
                    "kafka:GetBootstrapBrokers",
                    "kafka:DescribeCluster",
                ],
                resources=["*"],
            )
            
            kafka_client_instance.add_to_role_policy(statement=access_kafka_policy)
            
            instance_add_log_permissions(kafka_client_instance)
            
            client_properties.grant_read(kafka_client_instance)
            
            kafka_client_userdata.add_commands(
                f"aws s3 cp s3://{client_properties.s3_bucket_name}/{client_properties.s3_object_key} /home/ec2-user/client.properties",
                
                "yum install java-1.8.0 -y",
                
                f'wget https://www-us.apache.org/dist/kakfa/{constants["KAFKA_DOWNLOAD_VERSION"]}/bin/client.properties',
                f"tar -xvf {constants['KAFKA_DOWNLOAD_VERSION']}.tgz",
                f"mv {constants['KAFKA_DOWNLOAD_VERSION']} /opt",
                f"rm {constants['KAFKA_DOWNLOAD_VERSION']}.tgz",
                
                f"mv -f /home/ec2-user/client.properties /opt/{constants['KAFKA_DOWNLOAD_VERSION']}/bin/client.properties",
                
                f"kafka_arn=`aws kafka list-clusters --region {core.Aws.REGION} --output text --query 'ClusterInfoList[*].ClusterArn'`",
                
                f"kafka_zookeeper=`aws kafka describe-cluster --cluster-arn $kafka_arn --region {core.Aws.REGION} --output text --query 'ClusterInfo.ZookeeperConnectString'`",
                
                f"make_topic=`/opt/{constants['KAFKA_DOWNLOAD_VERSION']}/bin/kafka-topics.sh --create --zookeeper $kafka_zookeeper --replication-factor 3 --partitions 1 --topic topic 2>&1`",
                f"make_topic=`/opt/{constants['KAFKA_DOWNLOAD_VERSION']}/bin/kafka-topics.sh --create --zookeeper $kafka_zookeeper --replication-factor 3 --partitions 1 --topic apachelog 2>&1`",
                f"make_topic=`/opt/{constants['KAFKA_DOWNLOAD_VERSION']}/bin/kafka-topics.sh --create --zookeeper $kafka_zookeeper --replication-factor 3 --partitions 1 --topic appevent 2>&1`",
                
            )
            
            kafka_client_userdata.add_signal_on_exit_command(
                resources=kafka_client_instance    
            )
            
            kafka_client_instance.add_user_data(kafka_client_userdata.render())
    
    @property
    def get_kafka_client_sercurity_group(self):
        return self.kafka_client_security_group