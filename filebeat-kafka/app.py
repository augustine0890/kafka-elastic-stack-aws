#!/usr/bin/env python3
import os
from aws_cdk import core

from vpc.vpc_stack import VpcStack

app = core.App()

# Vpc stack
vpc_stack = VpcStack(
    app,
    "vpc",
    env=core.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"]
    ),
)
app.synth()
