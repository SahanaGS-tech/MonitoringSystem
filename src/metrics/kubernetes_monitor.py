from typing import Dict, List, Any, Optional
from kubernetes import client, config
from loguru import logger

class KubernetesMonitor:
    def __init__(self, k8s_config: Dict[str, Any]):
        self.namespace = k8s_config['namespace']
        self.labels = k8s_config['labels']
        
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()  # If running inside Kubernetes
        except:
            config.load_kube_config()  # If running locally
            
        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()
        self.metrics_api = None
        
        # Try to initialize metrics API if available
        try:
            self.metrics_api = client.CustomObjectsApi()
            logger.info("Metrics API initialized successfully")
        except Exception as e:
            logger.warning(f"Metrics API not available: {e}")
    
    def get_pods(self) -> List[Dict[str, Any]]:
        """Get all pods matching the configured labels"""
        label_selector = ','.join([f"{k}={v}" for k, v in self.labels.items()])
        
        try:
            pods = self.core_api.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=label_selector
            )
            
            pod_info = []
            for pod in pods.items:
                info = {
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'phase': pod.status.phase,
                    'ip': pod.status.pod_ip,
                    'node': pod.spec.node_name,
                    'start_time': pod.status.start_time.isoformat() if pod.status.start_time else None,
                    'containers': [c.name for c in pod.spec.containers]
                }
                pod_info.append(info)
            
            logger.info(f"Found {len(pod_info)} pods")
            return pod_info
            
        except Exception as e:
            logger.error(f"Error getting pods: {str(e)}")
            return []
    
    def get_pod_logs(self, pod_name: str, container: Optional[str] = None, tail_lines: int = 100) -> str:
        """Get logs from a specific pod"""
        try:
            logs = self.core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
                container=container,
                tail_lines=tail_lines
            )
            logger.info(f"Retrieved logs for pod {pod_name}")
            return logs
        except Exception as e:
            logger.error(f"Error getting logs for pod {pod_name}: {str(e)}")
            return f"Error retrieving logs: {str(e)}"
    
    def get_resource_metrics(self) -> List[Dict[str, Any]]:
        """Get resource usage metrics for pods"""
        if not self.metrics_api:
            logger.warning("Metrics API not available")
            return []
            
        try:
            metrics = self.metrics_api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=self.namespace,
                plural="pods"
            )
            
            # Process and return metrics
            pod_metrics = []
            for item in metrics.get('items', []):
                pod_name = item['metadata']['name']
                
                # Check if this pod matches our labels
                label_match = True
                for key, value in self.labels.items():
                    if item['metadata'].get('labels', {}).get(key) != value:
                        label_match = False
                        break
                
                if not label_match:
                    continue
                
                containers = {}
                for container in item.get('containers', []):
                    containers[container['name']] = {
                        'cpu': container.get('usage', {}).get('cpu', '0'),
                        'memory': container.get('usage', {}).get('memory', '0')
                    }
                
                pod_metrics.append({
                    'name': pod_name,
                    'timestamp': item['timestamp'],
                    'containers': containers
                })
                
            logger.info(f"Retrieved metrics for {len(pod_metrics)} pods")
            return pod_metrics
            
        except Exception as e:
            logger.error(f"Error getting pod metrics: {str(e)}")
            return []
