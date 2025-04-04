import os
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple
from loguru import logger

class ResourceAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        # Mock thresholds - we'd adjust these based on actual pod requirements
        self.thresholds = {
            'cpu': {
                'high': 20000000,        # 20m
                'low': 5000000,          # 5m
                'request': 12000000,     # 12m
                'limit': 25000000        # 25m
            },
            'memory': {
                'high': 25 * 1024 * 1024,    # 25Mi (below actual 30.9Mi)
                'low': 10 * 1024 * 1024,     # 10Mi
                'request': 20 * 1024 * 1024, # 20Mi
                'limit': 40 * 1024 * 1024    # 40Mi
            }
        }
        
        # Create directory for analysis logs
        os.makedirs('logs/analysis', exist_ok=True)
        
    def _parse_cpu_value(self, cpu_str: str) -> int:
        """Parse Kubernetes CPU metric value to nanocores integer"""
        if not cpu_str:
            return 0
            
        if cpu_str.endswith('n'):
            return int(cpu_str[:-1])
        elif cpu_str.endswith('u'):
            return int(cpu_str[:-1]) * 1000
        elif cpu_str.endswith('m'):
            return int(cpu_str[:-1]) * 1000000
        else:
            return int(float(cpu_str) * 1000000000)  # Convert cores to nanocores
    
    def _parse_memory_value(self, memory_str: str) -> int:
        """Parse Kubernetes memory metric value to bytes integer"""
        if not memory_str:
            return 0
            
        if memory_str.endswith('Ki'):
            return int(memory_str[:-2]) * 1024
        elif memory_str.endswith('Mi'):
            return int(memory_str[:-2]) * 1024 * 1024
        elif memory_str.endswith('Gi'):
            return int(memory_str[:-2]) * 1024 * 1024 * 1024
        elif memory_str.endswith('K') or memory_str.endswith('k'):
            return int(memory_str[:-1]) * 1000
        elif memory_str.endswith('M') or memory_str.endswith('m'):
            return int(memory_str[:-1]) * 1000 * 1000
        elif memory_str.endswith('G') or memory_str.endswith('g'):
            return int(memory_str[:-1]) * 1000 * 1000 * 1000
        else:
            return int(memory_str)  # Assume bytes
    
    def analyze_resource_usage(self, pod_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze resource usage and generate LLM-style responses"""
        results = {}
        
        for pod_metric in pod_metrics:
            pod_name = pod_metric['name']
            pod_results = {'containers': {}}
            
            for container_name, container_metrics in pod_metric.get('containers', {}).items():
                # Parse CPU and memory values
                cpu_usage = self._parse_cpu_value(container_metrics.get('cpu', '0'))
                memory_usage = self._parse_memory_value(container_metrics.get('memory', '0'))
                
                # Check for CPU overflow/underflow
                cpu_status = self._check_resource_status(
                    'cpu', 
                    cpu_usage, 
                    self.thresholds['cpu']['high'], 
                    self.thresholds['cpu']['low'],
                    self.thresholds['cpu']['request'],
                    self.thresholds['cpu']['limit']
                )
                
                # Check for memory overflow/underflow
                memory_status = self._check_resource_status(
                    'memory', 
                    memory_usage, 
                    self.thresholds['memory']['high'], 
                    self.thresholds['memory']['low'],
                    self.thresholds['memory']['request'],
                    self.thresholds['memory']['limit']
                )
                
                # Store container analysis
                container_analysis = {
                    'cpu': {
                        'usage': cpu_usage,
                        'status': cpu_status[0],
                        'utilization_percentage': cpu_status[1],
                        'analysis': cpu_status[2]
                    },
                    'memory': {
                        'usage': memory_usage,
                        'status': memory_status[0],
                        'utilization_percentage': memory_status[1],
                        'analysis': memory_status[2]
                    }
                }
                
                pod_results['containers'][container_name] = container_analysis
            
            results[pod_name] = pod_results
            
            # Generate LLM response for each container
            for container_name, container_analysis in pod_results['containers'].items():
                llm_response = self._generate_llm_response(
                    pod_name, 
                    container_name, 
                    container_analysis
                )
                
                # Log LLM response to file
                self._log_llm_response(
                    pod_name, 
                    container_name, 
                    container_analysis, 
                    llm_response
                )
        
        return results
    
    def _check_resource_status(
        self, 
        resource_type: str, 
        usage: int, 
        high_threshold: int, 
        low_threshold: int,
        request: int,
        limit: int
    ) -> Tuple[str, float, str]:
        """Check resource status and return (status, utilization_percentage, analysis)"""
        # Calculate utilization percentage based on request
        utilization_percentage = (usage / request) * 100 if request > 0 else 0
        
        if usage >= high_threshold:
            status = "OVERFLOW"
            analysis = (
                f"HIGH {resource_type.upper()} USAGE DETECTED: "
                f"The container is using {utilization_percentage:.1f}% of its requested {resource_type} "
                f"({usage/1000000 if resource_type == 'cpu' else usage/1024/1024:.1f}"
                f"{'m' if resource_type == 'cpu' else 'Mi'}). "
                f"This exceeds the high threshold of {high_threshold/1000000 if resource_type == 'cpu' else high_threshold/1024/1024:.1f}"
                f"{'m' if resource_type == 'cpu' else 'Mi'} "
                f"and may indicate a {resource_type} leak or inefficient resource usage pattern. "
                f"Consider investigating application behavior or increasing the resource limits."
            )
        elif usage <= low_threshold:
            status = "UNDERFLOW"
            analysis = (
                f"LOW {resource_type.upper()} USAGE DETECTED: "
                f"The container is only using {utilization_percentage:.1f}% of its requested {resource_type} "
                f"({usage/1000000 if resource_type == 'cpu' else usage/1024/1024:.1f}"
                f"{'m' if resource_type == 'cpu' else 'Mi'}). "
                f"This is below the low threshold of {low_threshold/1000000 if resource_type == 'cpu' else low_threshold/1024/1024:.1f}"
                f"{'m' if resource_type == 'cpu' else 'Mi'} "
                f"and may indicate over-provisioning. Consider reducing resource requests to "
                f"improve cluster utilization efficiency."
            )
        else:
            status = "NORMAL"
            analysis = (
                f"NORMAL {resource_type.upper()} USAGE: "
                f"The container is using {utilization_percentage:.1f}% of its requested {resource_type} "
                f"({usage/1000000 if resource_type == 'cpu' else usage/1024/1024:.1f}"
                f"{'m' if resource_type == 'cpu' else 'Mi'}), "
                f"which is within expected parameters."
            )
        
        return status, utilization_percentage, analysis
    
    def _generate_llm_response(
        self, 
        pod_name: str, 
        container_name: str, 
        container_analysis: Dict[str, Any]
    ) -> str:
        """Generate an LLM-style response based on resource analysis"""
        cpu_status = container_analysis['cpu']['status']
        memory_status = container_analysis['memory']['status']
        cpu_analysis = container_analysis['cpu']['analysis']
        memory_analysis = container_analysis['memory']['analysis']
        
        # Generate different responses based on resource status combinations
        if cpu_status == "OVERFLOW" and memory_status == "OVERFLOW":
            return (
                f"⚠️ CRITICAL RESOURCE ALERT: Pod {pod_name}, Container {container_name}\n\n"
                f"Both CPU and memory usage have exceeded high thresholds, indicating potential resource exhaustion.\n\n"
                f"{cpu_analysis}\n\n{memory_analysis}\n\n"
                f"RECOMMENDATION: This container appears to be under significant load or experiencing a resource leak. "
                f"Consider immediate investigation of application behavior, possibly scaling horizontally, "
                f"and increasing resource limits if this usage pattern is expected."
            )
        elif cpu_status == "OVERFLOW":
            return (
                f"⚠️ CPU USAGE ALERT: Pod {pod_name}, Container {container_name}\n\n"
                f"{cpu_analysis}\n\n{memory_analysis}\n\n"
                f"RECOMMENDATION: Investigate application CPU usage patterns. If this is expected behavior during peak loads, "
                f"consider increasing CPU limits or implementing autoscaling. If unexpected, check for CPU-intensive operations "
                f"or infinite loops that might be consuming excessive resources."
            )
        elif memory_status == "OVERFLOW":
            return (
                f"⚠️ MEMORY USAGE ALERT: Pod {pod_name}, Container {container_name}\n\n"
                f"{memory_analysis}\n\n{cpu_analysis}\n\n"
                f"RECOMMENDATION: Check for memory leaks or unexpected caching behavior. Consider using memory profiling tools "
                f"to identify memory usage patterns. If this is expected behavior for your workload, increase memory limits "
                f"to prevent potential OOM (Out of Memory) kills."
            )
        elif cpu_status == "UNDERFLOW" and memory_status == "UNDERFLOW":
            return (
                f"ℹ️ RESOURCE UNDERUTILIZATION NOTICE: Pod {pod_name}, Container {container_name}\n\n"
                f"Both CPU and memory usage are significantly below requested resources.\n\n"
                f"{cpu_analysis}\n\n{memory_analysis}\n\n"
                f"RECOMMENDATION: The container is overprovisioned. Consider reducing CPU and memory requests "
                f"to improve cluster resource efficiency. For cost optimization, these resources could be better "
                f"allocated to other workloads."
            )
        elif cpu_status == "UNDERFLOW":
            return (
                f"ℹ️ CPU UNDERUTILIZATION NOTICE: Pod {pod_name}, Container {container_name}\n\n"
                f"{cpu_analysis}\n\n{memory_analysis}\n\n"
                f"RECOMMENDATION: The container has excess CPU capacity. Consider reducing CPU requests "
                f"to better match actual usage patterns and improve overall cluster CPU utilization."
            )
        elif memory_status == "UNDERFLOW":
            return (
                f"ℹ️ MEMORY UNDERUTILIZATION NOTICE: Pod {pod_name}, Container {container_name}\n\n"
                f"{memory_analysis}\n\n{cpu_analysis}\n\n"
                f"RECOMMENDATION: The container has excess memory allocation. Consider reducing memory requests "
                f"to better align with actual usage patterns. This could improve cluster memory efficiency."
            )
        else:
            return (
                f"✅ HEALTHY RESOURCE UTILIZATION: Pod {pod_name}, Container {container_name}\n\n"
                f"Both CPU and memory usage are within normal operational parameters.\n\n"
                f"{cpu_analysis}\n\n{memory_analysis}\n\n"
                f"RECOMMENDATION: No action needed. Resource allocation appears to be appropriately sized "
                f"for the current workload."
            )
    
    def _log_llm_response(
        self,
        pod_name: str,
        container_name: str,
        container_analysis: Dict[str, Any],
        llm_response: str
    ):
        """Log LLM response to a file and console"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f"logs/analysis/{pod_name}_{container_name}_{timestamp}.log"
        
        with open(log_file, 'w') as f:
            # Write metadata section
            f.write("=== RESOURCE ANALYSIS METADATA ===\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Pod: {pod_name}\n")
            f.write(f"Container: {container_name}\n")
            f.write(f"CPU Status: {container_analysis['cpu']['status']}\n")
            f.write(f"CPU Usage: {container_analysis['cpu']['usage']} nanocores\n")
            f.write(f"CPU Utilization: {container_analysis['cpu']['utilization_percentage']:.1f}%\n")
            f.write(f"Memory Status: {container_analysis['memory']['status']}\n")
            f.write(f"Memory Usage: {container_analysis['memory']['usage']} bytes ({container_analysis['memory']['usage']/1024/1024:.1f} MiB)\n")
            f.write(f"Memory Utilization: {container_analysis['memory']['utilization_percentage']:.1f}%\n")
            f.write("\n=== LLM ANALYSIS RESPONSE ===\n\n")
            
            # Write LLM response
            f.write(llm_response)
        
        # Also log to console
        logger.info(f"Resource analysis for {pod_name}/{container_name} saved to {log_file}")
        
        # Print the LLM response to console with dividers for readability
        logger.info("=" * 80)
        logger.info(f"RESOURCE ANALYSIS FOR {pod_name}/{container_name}")
        logger.info("=" * 80)
        logger.info(f"Response Message:")
        logger.info(llm_response)
        logger.info("=" * 80)