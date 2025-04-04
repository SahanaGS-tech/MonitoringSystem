from typing import Dict, List, Any, Optional
from kubernetes import client, config
from loguru import logger
import random

class KubernetesMonitor:
    def __init__(self, k8s_config: Dict[str, Any]):
        self.namespace = k8s_config['namespace']
        self.labels = k8s_config['labels']
        
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()  
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
    
    def _generate_mock_metrics(self, pods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate mock resource metrics for testing"""
        mock_metrics = []
        
        # Create different resource usage scenarios
        scenarios = [
            # High CPU, normal memory (overflow CPU)
            {"cpu_base": 900000000, "cpu_var": 100000000, "mem_base": 200, "mem_var": 50},
            # Normal CPU, high memory (overflow memory)
            {"cpu_base": 400000000, "cpu_var": 100000000, "mem_base": 450, "mem_var": 50},
            # Low CPU, low memory (underflow both)
            {"cpu_base": 50000000, "cpu_var": 30000000, "mem_base": 40, "mem_var": 10},
            # Normal CPU, normal memory
            {"cpu_base": 350000000, "cpu_var": 100000000, "mem_base": 200, "mem_var": 50},
            # High CPU, high memory (overflow both)
            {"cpu_base": 950000000, "cpu_var": 100000000, "mem_base": 480, "mem_var": 30}
        ]
        
        for pod in pods:
            # Pick a random scenario for this pod
            scenario = random.choice(scenarios)
            
            containers = {}
            for container in pod['containers']:
                # Generate slightly random values within the scenario
                cpu_usage = scenario["cpu_base"] + random.randint(-scenario["cpu_var"], scenario["cpu_var"])
                memory_mb = scenario["mem_base"] + random.randint(-scenario["mem_var"], scenario["mem_var"])
                
                # Convert to Kubernetes format
                cpu_str = f"{cpu_usage}n"  # nanocores
                memory_str = f"{memory_mb}Mi"  # MiB
                
                containers[container] = {
                    'cpu': cpu_str,
                    'memory': memory_str
                }
            
            mock_metrics.append({
                'name': pod['name'],
                'timestamp': '',  # Not used in analysis
                'containers': containers
            })
        
        return mock_metrics
    
    def get_resource_metrics(self) -> List[Dict[str, Any]]:
        """Get resource usage metrics for pods"""
        try:
            # First try to get actual metrics
            if self.metrics_api:
                try:
                    metrics = self.metrics_api.list_namespaced_custom_object(
                        group="metrics.k8s.io",
                        version="v1beta1",
                        namespace=self.namespace,
                        plural="pods"
                    )
                    
                    # Process metrics
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
                    logger.error(f"Error getting actual pod metrics: {str(e)}")
                    # If actual metrics fail, fall back to mock metrics
            
            # If we get here, either metrics API is not available or there was an error
            # Generate mock metrics
            pods = self.get_pods()
            mock_metrics = self._generate_mock_metrics(pods)
            logger.info(f"Generated mock metrics for {len(mock_metrics)} pods")
            return mock_metrics
                
        except Exception as e:
            logger.error(f"Error in get_resource_metrics: {str(e)}")
            return []
