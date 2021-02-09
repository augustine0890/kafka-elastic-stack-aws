#!/usr/bin/env python3

from aws_cdk import core

from filebeat_kafka.filebeat_kafka_stack import FilebeatKafkaStack


app = core.App()
FilebeatKafkaStack(app, "filebeat-kafka")

app.synth()
