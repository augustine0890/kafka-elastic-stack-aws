#!/usr/bin/env python3
import os
from aws_cdk import core

from vpc.vpc_stack import VpcStack
from kafka.kafka_stack import KafkaStack
from filebeat.filebeat_stack import FilebeatStack

app = core.App()

# Vpc stack
vpc_stack = VpcStack(
    app,
    "fk-vpc",
    env=core.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)

# Kafka stack
kafka_stack = KafkaStack(
    app,
    "kafka",
    vpc_stack,
    client=True,
    env=core.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)
kafka_stack.add_dependency(vpc_stack)

# Filebeat stack (Filebeat on EC2)
filebeat_stack = FilebeatStack(
    app,
    "filebeat",
    vpc_stack,
    kafka_stack,
    env=core.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)
filebeat_stack.add_dependency(kafka_stack)

app.synth()
