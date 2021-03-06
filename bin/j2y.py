#!/usr/bin/python

from __future__ import print_function
import json
import yaml
import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        description="Converts <source> from json to yaml and writes into <target>. Then reads it back and compares source and target data.")
    parser.add_argument('source', metavar='source',
                        help="Source file with path. Example: myfile.json")
    parser.add_argument('target', metavar='target',
                        help="Target file with path. Example: myfile.yml")
    parser.add_argument(
        '--printjson', '-p', help="Print the compared data (as json). Defaults to false.", action='store_true')
    return parser


def main():
    parser = parse_args()
    args = parser.parse_args()

    src = None
    print("Reading source...")
    with open(args.source) as src_file_obj:
        src = json.load(src_file_obj)

    print("Writing target...")
    yaml.safe_dump(src, file(args.target, 'w'), encoding='utf-8',
                   allow_unicode=True, default_flow_style=False)

    print("Reading target back...")
    tgt = None
    with open(args.target) as tgt_file_obj:
        tgt = yaml.load(tgt_file_obj)

    print("Comparing both data... ", end="")
    if src == tgt:
        print("SUCCESS")
    else:
        print("FAILED")

    print("Comparing both as json... ", end="")
    src_json = json.dumps(src, sort_keys=True, indent=2)
    tgt_json = json.dumps(tgt, sort_keys=True, indent=2)
    if src_json == tgt_json:
        print("SUCCESS")
    else:
        print("FAILED")

    if args.printjson:
        print("Source: {}".format(src_json))
        print("Target: {}".format(tgt_json))

if __name__ == "__main__":
    main()
