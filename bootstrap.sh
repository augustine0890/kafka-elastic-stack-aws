#!/bin/bash

# create the virtual environment
python -m venv .env
# download requirements
.venv/bin/python -m pip install -r requirements.txt
# create the key pair
aws ec2 create-key-pair --key-name key_pair --query 'KeyMaterial' --output text > key_pair.pem --region us-east-2
# update key_pair permissions
chmod 400 key_pair.pem
# move key_pair to .ssh
mv -f key_pair.pem $HOME/.ssh/key_pair.pem
# start the ssh agent
eval `ssh-agent -s`
# add your key to keychain
ssh-add -k ~/.ssh/key_pair.pem