# This Repository is Public

# prometheusrules-validator
Docker image to validate prometheus rules in kubernetes.

## Description

A simple python script to validate the prometheus rules that exists in Kubernetes
using `promtool check rules` command line. When the validation is success,
then a label is applied in the rule.

## Example Deployment

An example of a deployment can be found in the file `example-deployment.yaml` 
