#!/bin/bash
cd ~/assignment3
echo "Starting Minikube..."
minikube start --driver=docker --memory=2048 --cpus=2
echo "Waiting for Minikube to be ready..."
kubectl wait --for=condition=Ready node/minikube --timeout=120s
echo "Applying Kubernetes manifests..."
kubectl apply -f k8s/namespace.yml
sleep 2
kubectl apply -f k8s/mysql-secret.yml
kubectl apply -f k8s/flask-configmap.yml
kubectl apply -f k8s/mysql-pv.yml
kubectl apply -f k8s/mysql-pvc.yml
kubectl apply -f k8s/mysql-deployment.yml
kubectl apply -f k8s/mysql-service.yml
echo "Waiting for MySQL to be ready..."
kubectl wait --for=condition=Ready pod -l app=mysql -n assignment3 --timeout=120s
kubectl apply -f k8s/flask-deployment.yml
kubectl apply -f k8s/flask-service.yml
kubectl apply -f k8s/nginx-configmap.yml
kubectl apply -f k8s/nginx-deployment.yml
kubectl apply -f k8s/nginx-service.yml
echo "Waiting for all pods to be ready..."
kubectl wait --for=condition=Ready pod --all -n assignment3 --timeout=180s
echo ""
echo "=== Deployment Status ==="
kubectl get all -n assignment3
echo ""
echo "=== Access URL ==="
minikube service nginx -n assignment3 --url
