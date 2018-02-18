#!/usr/bin/python
# -*- coding: utf-8 -*-


import sys
import os
import boto3
import argparse
import time
import paramiko

from termcolor import colored

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
        "disk": {
            "/dev/xvda": {
                "size": 20,
                "use_for_backup": False,
                "dot": True
            },
            '/dev/xvdf': {
                "size": 10,
                "use_for_backup": True,
                "dot": False
            }
        }
    },
    "Peer": {
        "type": "t2.micro",
        "imageID": "ami-97785bed",
        "disk": {
            "/dev/xvda": {
                "size": 10,
                "type": "data disk",
                "dot": True
            }
        }
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
    list_all_parser.add_argument("--region", action="store", dest="region", help="Server location.(Default us-east-1)", default="us-east-1")
    list_all_parser.set_defaults(opt_name="list_all")
    # Execute options
    execute_parser = subparsers.add_parser("execute", help="Execute script for CustomerID or NodeType.")
    execute_parser.add_argument("--customer-id", action="store", dest="customer_id", help="CustomerID")
    execute_parser.add_argument("--node-type", action="store", dest="node_type", help="NodeType for script that will be execute.")
    execute_parser.add_argument("--script", action="store", dest="script_path", help="Path to script that will be execute(if script located your local, please ues -t option)", required=True)
    execute_parser.add_argument("--region", action="store", dest="region", help="Server location.(Default us-east-1)", default="us-east-1")
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


def make_connection(**kwargs):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if "key_file_path" in kwargs:
        key_file = paramiko.RSAKey.from_private_key_file(kwargs["key_file_path"].replace(".pub", ""))
        ssh_client.connect(hostname=kwargs["host"], username=kwargs["user"], pkey=key_file)
    else:
        ssh_client.connect(hostname=kwargs["host"], username=kwargs["user"], password=kwargs["pass"])
    return ssh_client


def execute_to_command(**kwargs):
    with make_connection(host=kwargs["host"], user="ec2-user", key_file_path=os.getenv("PUB_KEY")) as conn:
        _, stdout, stderr = conn.exec_command(kwargs["command"])
        return stdout.readlines(), stderr.readlines()


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


def get_instance_details(manager, instance_id):
    return manager.Instance(instance_id)


def get_all_instance_ids():
    nodes = list()
    for region in REGIONS.values():
        for i in range(len(region)):
            ec2_client, ec2_resource = get_ec2_session(region[i])
            try:
                for node in ec2_client.describe_instances()["Reservations"][0]["Instances"]:
                    nodes.append(node["InstanceId"])
            except:
                pass
    return nodes


def create_instance(manager, node_type, customer_id):
    node_prop = NODE_PROP[node_type]
    block_dev = list()
    backup_disk = list()
    device_list = list()
    for k, v in node_prop["disk"].iteritems():
        if v["use_for_backup"]:
            backup_disk.append(k)
        block_dev.append(
            {
                "DeviceName": k,
                "Ebs": {
                    "VolumeSize": v["size"],
                    "DeleteOnTermination": v["dot"]
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
                "Key": "NodeType",
                "Value": node_type
            }
        ]
    )
    while not device_list:
        device_list = manager.Instance(instance_id).block_device_mappings
        time.sleep(1)
    for device in device_list:
        if device["DeviceName"] in backup_disk:
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
    if len(backup_disk) > 0:
        while instance[0].state["Name"] != "running":
            time.sleep(1)
        mount_command = open("build_backup_disk.sh", "r").read()
        for d in backup_disk:
            execute_to_command(host=instance[0].private_ip_address, command=mount_command.replace("$1", d))
    return instance_id


def create_operation(argv):
    ec2_client, ec2_resource = get_ec2_session(argv.region)
    import_key_pair(ec2_client, os.getenv("PUB_KEY", None), argv.customer_id)
    return create_instance(ec2_resource, argv.node_type, argv.customer_id)


def list_nodes_operation(argv):
    return "\n".join(get_all_instance_ids())


def list_all_operation(argv):
    ec2_client, ec2_resource = get_ec2_session(argv.region)
    prop = list()
    for i in get_all_instance_ids():
        ids = get_instance_details(ec2_resource, i)
        customer_id = None
        for e in ids.tags:
            if e["Key"] == "CustomerID":
                customer_id = e["Value"]
        prop.append("{0}, {1}, {2}".format(customer_id, i, ids.public_ip_address))
    return "\n".join(prop)


def execute_operation(argv):
    ec2_client, ec2_resource = get_ec2_session(argv.region)
    command = open(argv.script_path, "r").read()
    results = list()
    if argv.node_type is not None:
        filter = [{"Name": "tag:NodeType", "Values": [argv.node_type]}]
    else:
        filter = [{"Name": "tag:CustomerID", "Values": [argv.customer_id]}]
    for target in ec2_client.describe_instances(Filters=filter)["Reservations"][0]["Instances"]:
        err, out = execute_to_command(host=target["PublicIpAddress"], command=command)
        if len(err) > 0:
            results.append(colored("Error occurred when running script named %s on %s.\nError is: \n\t%s" %(argv.script_path, target["PublicIpAddress"], "\t".join(err)), "red"))
            continue
        results.append(colored("Execution successful for %s.\nOutput is: \n\t%s" %(target["PublicIpAddress"], "\t".join(out)), "green"))
    return "\n".join(results)


if __name__ == "__main__":
    opt_list = {
        "create": create_operation,
        "list_nodes": list_nodes_operation,
        "list_all": list_all_operation,
        "execute": execute_operation
    }
    args = parse_args()
    print opt_list[args.opt_name](args)
