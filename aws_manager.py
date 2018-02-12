#!/usr/bin/python
# -*- coding: utf-8 -*-


import sys
import os
import boto3
import argparse
import time

REGIONS = {
    "US East": [
        "us-east-1",
        "us-east-2",
    ],
    "US West": [
        "us-west-1",
        "us-west-2",
    ]
}

NODE_PROP = {
    "Manager": {
        "type": "t2.nano",
        "imageID": "ami-97785bed",
        "disk": 20,
        "backup_disk": 10
    },
    "Peer": {
        "type": "t2.micro",
        "imageID": "ami-97785bed",
        "disk": 10
    }
}


def parse_args():
    parser = argparse.ArgumentParser(description="AWS Instance Manager")
    subparsers = parser.add_subparsers(help="Usable commands.")
    # Create options
    create_parser = subparsers.add_parser("create", help="Create an instance.")
    create_parser.add_argument("--customer-id", action="store", dest="customer_id", help="CustomerID", required=True)
    create_parser.add_argument("--node-type", action="store", dest="node_type", help="NodeType for machine that will be create.(Default: Peer)", default="Peer")
    create_parser.add_argument("--region", action="store", dest="region", help="Server location.(Default us-east-1)", default="us-east-1")
    create_parser.set_defaults(opt_name="create")
    # List nodes options
    list_nodes_parser = subparsers.add_parser("list-nodes", help="List all NodeID for specific customer.")
    list_nodes_parser.add_argument("--customer-id", action="store", dest="customer_id", help="CustomerID", required=True)
    list_nodes_parser.set_defaults(opt_name="list_nodes")
    # List all options
    list_all_parser = subparsers.add_parser("list-all", help="List all NodeID, CustomerID and IP's.")
    list_all_parser.add_argument("-a", action="store_true", dest="list_all", default=True)
    list_all_parser.set_defaults(opt_name="list_all")
    # Execute options
    execute_parser = subparsers.add_parser("execute", help="Execute script for CustomerID or NodeType.")
    execute_parser.add_argument("--customer-id", action="store", dest="customer_id", help="CustomerID")
    execute_parser.add_argument("--node-type", action="store", dest="node_type", help="NodeType for script that will be execute.")
    execute_parser.add_argument("-t", action="store", dest="script_transport", help="Transfer script to remote machines (Default path: /tmp)", default="/tmp")
    execute_parser.add_argument("--script", action="store", dest="script_path", help="Path to script that will be execute(if script located your local, please ues -t option)", required=True)
    execute_parser.set_defaults(opt_name="execute")
    # Backup options
    backup_parser = subparsers.add_parser("backup", help="Create backup for given NodeID.")
    backup_parser.add_argument("--node-id", action="store", dest="node_id", help="NodeID")
    backup_parser.set_defaults(opt_name="backup")
    # List backup options
    list_backup_parser = subparsers.add_parser("list-backup", help="List all BackupID and timestamp for given NodeID.")
    list_backup_parser.add_argument("--node-id", action="store", dest="node_id", help="NodeID")
    list_backup_parser.set_defaults(opt_name="list_backup")
    # Rollback options
    rollback_parser = subparsers.add_parser("rollback", help="Rollback to specific BackupID for given NodeID.")
    rollback_parser.add_argument("--rollback-id", action="store", dest="rollback_id", help="RollbackID")
    rollback_parser.set_defaults(opt_name="rollback")
    return parser.parse_args()


def get_ec2_session(region):
    session = boto3.session.Session(region_name=region)
    return session.client('ec2'), session.resource("ec2")


def import_key_pair(manager, key_path, customer_id):
    try:
        if key_path is not None:
            with open(key_path, "r") as k:
                manager.import_key_pair(KeyName=customer_id, PublicKeyMaterial=k.read())
            return
        print "Please create id_rsa.pub and/or export PUB_KEY environ."
        sys.exit(1)
    except:
        return


def create_instance(manager, node_type, customer_id):
    node_prop = NODE_PROP[node_type]
    block_dev = list()
    backup_disk = list()
    if "disk" in node_prop:
        block_dev.append(
            {
                "DeviceName": "/dev/xvda",
                "Ebs": {
                    "VolumeSize": node_prop["disk"],
                    "DeleteOnTermination": True
                }
            }
        )
    if "backup_disk" in node_prop:
        backup_disk.append("/dev/xvdb")
        block_dev.append(
            {
                "DeviceName": "/dev/xvdb",
                "Ebs": {
                    "VolumeSize": node_prop["backup_disk"],
                    "DeleteOnTermination": True
                }
            }
        )
    instance = manager.create_instances(
        ImageId=node_prop["imageID"],
        MinCount=1,
        MaxCount=1,
        KeyName=customer_id,
        InstanceType=node_prop["type"],
        BlockDeviceMappings=block_dev
    )
    instance_id = instance[0].id
    manager.create_tags(
        Resources=(instance_id,),
        Tags=[
            {
                "Key": "CustomerID",
                "Value": customer_id
            },
            {
                "Key": "InstanceID",
                "Value": instance_id
            }
        ]
    )
    device_list = list()
    while not device_list:
        device_list = manager.Instance(instance_id).block_device_mappings
        time.sleep(1)
    for device in device_list:
        if device["DeviceName"][5:] in backup_disk:
            name = "BackupDisk-" + device["DeviceName"][5:]
        else:
            name = "DataDisk-" + device["DeviceName"][5:]
        manager.create_tags(
            Resources=(device["Ebs"]["VolumeId"],),
            Tags=[
                {
                    "Key": "InstanceID",
                    "Value": instance_id
                },
                {
                    "Key": "VolumeName",
                    "Value": name
                }
            ]
        )
    return instance_id


def create_operation(argv):
    ec2_client, ec2_resource = get_ec2_session(argv.region)
    import_key_pair(ec2_client, os.getenv("PUB_KEY", None), argv.customer_id)
    return create_instance(ec2_resource, argv.node_type, argv.customer_id)


if __name__ == "__main__":
    opt_list = {
        "create": create_operation
    }
    args = parse_args()
    print opt_list[args.opt_name](args)
