""""
Bash command:
> aws ec2 describe-instances --filters Name="tag:Application",Values="logger" | jq ".Reservations[].Instances[0] | select(.PrivateIpAddress != null) | .PrivateIpAddress" -r
"""
import argparse
import sys
from typing import Optional
import textwrap

import boto3


def logger_private_ip_address() -> Optional[str]:
    ec2 = boto3.client("ec2")
    response = ec2.describe_instances(
        Filters=[
            {"Name": "tag:Application", "Values": ["logger", ]},
            {"Name": "instance-state-name", "Values": ["running", ]},
        ],
        MaxResults=6,
    )
    reservation = response.get("Reservations")
    if not reservation:
        return None
    instances = reservation[0].get("Instances")
    if not instances:
        return None

    ip_addr = instances[0].get("PrivateIpAddress")

    return ip_addr


def generate_config_file(ip_addr: Optional[str], service: str, port: int = 21514) -> str:
    if ip_addr is None:
        return ""
    template = textwrap.dedent(
        f"""
        :programname, isequal, "{service}" action(
          type="omfwd"
          target = "{ip_addr}"
          port = "{port}"
          protocol = "tcp"
          action.resumeRetryCount = "100"
          queue.type = "linkedList"
          queue.size = "10000"
        )
        """.strip("\n")
    )
    return template


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Materialize rsyslog configuration for current logger AWS server"
    )
    parser.add_argument(
        "-o", "--outfile", type=argparse.FileType("w"), default=sys.stdout
    )
    parser.add_argument(
        "-s", "--service", required=True
    )
    parser.add_argument(
        "-p", "--port", type=int, default=21514, help="Port of rsyslog server"
    )

    args = parser.parse_args()

    ip_addr = logger_private_ip_address()
    result = generate_config_file(ip_addr, service=args.service, port=args.port)

    with args.outfile as ofp:
        print(result, file=ofp)
