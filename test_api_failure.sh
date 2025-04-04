#!/bin/bash
POD_NAME=$(kubectl get pods -n dev -l app=fastapi-app -o jsonpath='{.items[0].metadata.name}')
echo "Temporarily shutting down pod $POD_NAME to simulate failure"
kubectl delete pod $POD_NAME -n dev
echo "Pod deleted, Kubernetes will automatically create a new one"
echo "Check the monitoring logs to see the detected failure"
