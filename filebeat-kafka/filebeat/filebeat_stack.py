import os.path
import urllib.request

from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3_assets as assets,
)
from helpers.constants import constants
from helpers.functions import (
    file_updated,
    kafka_get_brokers,
    user_data_init,
    instance_add_log_permissions,
)

dirname = os.path.dirname(__file__)
external_ip = urllib.request.urlopen("https://ident.me").read().decode("utf8")


class FilebeatStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, vpc_stack, kafka_stack, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        log_generator_py = assets.Asset(
            self,
            "log_generator",
            path=os.path.join(dirname, "log_generator.py"),
        )
        
        log_generator_requirements_txt = assets.Asset(
            self,
            "log_generator_requirements_txt",
            path=os.path.join(dirname, "log_generator_requirements.txt"),
        )
        
        kafka_brokers = f'''"{kafka_get_brokers().replace(",", '", "')}"'''
        
        filebeat_yml_asset = file_updated(
            os.path.join(dirname, "filebeat.yml"),
            {"$kafka_brokers": kafka_brokers},
        )
        
        filebeat_yml = assets.Asset(self, "filebeat_yml", path=filebeat_yml_asset)

        fb_userdata = user_data_init(log_group_name="filebeat-kafka/filebeat/instance")

        fb_instance = ec2.Instance(
            self,
            "filebeat_client",
            instance_type=ec2.InstanceType(constants["FILEBEAT_INSTANCE"]),
            machine_image=ec2.AmazonLinuxImage(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
            ),
            vpc=vpc_stack.get_vpc,
            vpc_subnets={"subnet_type": ec2.SubnetType.PUBLIC},
            key_name=constants["KEY_PAIR"],
            security_group=kafka_stack.get_kafka_client_sercurity_group,
            user_data=fb_userdata,
        )
        core.Tag.add(fb_instance, "project", constants["PROJECT_TAG"])
        
        access_kafka_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["kafka:ListClusters", "kafka:GetBootstrapBrokers",],
            resources=["*"],
        )
        fb_instance.add_to_role_policy(statement=access_kafka_policy)
        
        instance_add_log_permissions(fb_instance)
        
        filebeat_yml.grant_read(fb_instance)
        log_generator_py.grant_read(fb_instance)
        log_generator_requirements_txt.grant_read(fb_instance)
        
        fb_userdata.add_commands(
            f"aws s3 cp s3://{filebeat_yml.s3_bucket_name}/{filebeat_yml.s3_object_key} /home/ec2-user/filebeat.yml",
            f"aws s3 cp s3://{log_generator_py.s3_bucket_name}/{log_generator_py.s3_object_key} /home/ec2-user/log_generator.py",
            f"aws s3 cp s3://{log_generator_requirements_txt.s3_bucket_name}/{log_generator_requirements_txt.s3_object_key} /home/ec2-user/requirements.txt",
            
            "yum install python3 -y",
            "yum install python-pip -y",
            
            "chmod +x /home/ec2-user/log_generator.py",
            "python3 -m pip install -r /home/ec2-user/requirements.txt",
            
            "yum install filebeat -y",
            "mv -f /home/ec2-user/filebeat.yml /etc/filebeat/filebeat.yml",
            
            "chown -R ec2-user:ec2-user /home/ec2-user",
            
            "systemctl start filebeat",
        )
        
        fb_userdata.add_signal_on_exit_command(resource=fb_instance)
        fb_instance.add_user_data(fb_userdata.render())
        fb_instance.instance.cfn_options.creation_policy = core.CfnCreationPolicy(
            resource_signal=core.CfnResourceSignal(count=1, timeout="PT10M")    
        )