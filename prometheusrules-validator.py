#!/usr/bin/python3

from kubernetes import client, config

import argparse
import logging
import os
import time
import sys
import json
import tempfile
import subprocess
import io


PROMETHEUS_CRD_GROUP = 'monitoring.coreos.com'
PROMETHEUS_CRD_VERSION = 'v1'
PROMETHEUS_CRD_RULES_PLURAR = 'prometheusrules'

def validateRulesAllNamespaces(args, v1, customApi):
    logging.info("Validation loop started")
    namespace_list = v1.list_namespace()
    for namespace in namespace_list.items:
        validateRulesByNamespace(args, v1, customApi, namespace.metadata.name)
    logging.info("Validation loop ends")


def validateRulesByNamespace(args, v1, customApi, namespaceName):
    logging.info(f"Checking namespace: {namespaceName}")
    prometehusrules_list = customApi.list_namespaced_custom_object(PROMETHEUS_CRD_GROUP, PROMETHEUS_CRD_VERSION, namespaceName, PROMETHEUS_CRD_RULES_PLURAR)
    if len(prometehusrules_list['items']) == 0:
        logging.info(f"Not prometheus rules in namespace {namespaceName}")
    else:
        for prometheusrule in prometehusrules_list['items']:
            validatePrometheusRule(args, v1, customApi, prometheusrule)


def validatePrometheusRule(args, v1, customApi, prometheusrule):
    logging.info(f"Validating prometheusrules {prometheusrule['metadata']['name']} in namespace {prometheusrule['metadata']['namespace']}")
    with tempfile.NamedTemporaryFile(mode='w+t') as f:  # writing JSON object
        json.dump(prometheusrule['spec'], f, sort_keys=True, indent=4, separators=(',', ': '))
        f.flush()
        result = subprocess.run(['/bin/promtool', 'check', 'rules', f.name], capture_output=True)
        if result.returncode != 0:
            logging.warning(f"Validation of prometheusrule {prometheusrule['metadata']['name']} in namespace {prometheusrule['metadata']['namespace']} failed")
            logging.debug(f"####### stdout: \n{result.stdout}\n####### stderr:\n{result.stderr}")
            output = io.StringIO()
            json.dump(prometheusrule['spec'], output, sort_keys=True, indent=4, separators=(',', ': '))
            logging.debug(f"####### file:\n{output.getvalue()}")
            output.close()
            if not args.dry_run:
                try:
                    customApi.patch_namespaced_custom_object(
                        PROMETHEUS_CRD_GROUP,
                        PROMETHEUS_CRD_VERSION,
                        prometheusrule['metadata']['namespace'],
                        PROMETHEUS_CRD_RULES_PLURAR,
                        prometheusrule['metadata']['name'],
                        {"metadata": {"labels": {args.label_key: None}}}
                    )
                except:
                    logging.exception("Error trying to remove label")
            else:
                logging.info("Not removing labels due DryRun")

        else:
            if not args.dry_run:
                try:
                    customApi.patch_namespaced_custom_object(
                        PROMETHEUS_CRD_GROUP,
                        PROMETHEUS_CRD_VERSION,
                        prometheusrule['metadata']['namespace'],
                        PROMETHEUS_CRD_RULES_PLURAR,
                        prometheusrule['metadata']['name'],
                        {"metadata": {"labels": {args.label_key: "validated"}}}
                    )
                except:
                    logging.exception("Error trying to add label")
            else:
                logging.info("Not applying labels due DryRun")

# MAIN

parser = argparse.ArgumentParser(description="Validating Prometheus Rules")
parser.add_argument('--dry-run', dest='dry_run', action='store_true')
parser.add_argument('--no-dry-run', dest='dry_run', action='store_false')
parser.add_argument('--label-key', dest='label_key', required=False)
parser.add_argument('--loop-seconds', dest='loop_seconds', required=False)
parser.add_argument('--incluster-config', dest='incluster_config', action='store_true', required=False)
parser.add_argument('--config-file', dest='config_file', required=False)
parser.add_argument('--verbose', dest='verbose', action='store_true', required=False)
parser.add_argument('--insecure-skip-tls-verify', dest='skip_tls_verify', action='store_true', required=False)
parser.set_defaults(dry_run=False)
parser.set_defaults(verbose=False)
parser.set_defaults(label_key='prometheus-validator-result')
parser.set_defaults(incluster_config=True)
parser.set_defaults(loop_seconds=60)
parser.set_defaults(skip_tls_verify=False)

args = parser.parse_args()

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.DEBUG if args.verbose else logging.INFO
)
# Capture warnings into loggging for warining of tls validation
logging.captureWarnings(True)

logging.info("Starting prometheusrules validator")
logging.info(f"Dry run: {args.dry_run}")

if (args.config_file is None):
    logging.info("Loading kubernetes incluster config")
    config.load_incluster_config()
else:
    logging.info("Loading kubernetes from default config file")
    config.load_kube_config(config_file=args.config_file)

logging.info(f"SSL Verify: {not args.skip_tls_verify}")
if args.skip_tls_verify:
    conf = client.Configuration()
    conf.verify_ssl = False
    conf.debug = False
    client.Configuration.set_default(conf)

v1 = client.CoreV1Api()
customApi = client.CustomObjectsApi()

while True:
    validateRulesAllNamespaces(args, v1, customApi)
    time.sleep(args.loop_seconds)
