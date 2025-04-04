import time
import sys
import os
import schedule
from datetime import datetime

from src.config import load_config
from src.logs.logger import setup_logging
from src.api_monitor.monitor import ApiMonitor
from src.metrics.kubernetes_monitor import KubernetesMonitor

def run_monitoring_cycle(api_monitor, k8s_monitor, logger):
    """Run a complete monitoring cycle"""
    timestamp = datetime.now().isoformat()
    logger.info(f"Starting monitoring cycle at {timestamp}")
    
    # Check API endpoints
    api_results = api_monitor.check_all_endpoints()
    
    # Log API results summary
    success_count = sum(1 for r in api_results if r['success'])
    logger.info(f"API Monitoring: {success_count}/{len(api_results)} endpoints are UP")
    
    # Check for failing endpoints and collect logs if needed
    for result in api_results:
        if not result['success']:
            logger.warning(f"Failed endpoint: {result['url']} - {result['error']}")
            
            # Get pod information if endpoint is failing
            pods = k8s_monitor.get_pods()
            for pod in pods:
                if pod['phase'] != 'Running':
                    logger.warning(f"Pod {pod['name']} is in {pod['phase']} state")
                    continue
                
                # Get resource metrics
                logger.info(f"Collecting resource metrics for pod {pod['name']}")
                metrics = k8s_monitor.get_resource_metrics()
                for pod_metric in metrics:
                    if pod_metric['name'] == pod['name']:
                        for container_name, container_metrics in pod_metric['containers'].items():
                            logger.info(f"Pod {pod['name']}, Container {container_name}: CPU: {container_metrics['cpu']}, Memory: {container_metrics['memory']}")
                
                # Get logs
                logger.info(f"Collecting logs for pod {pod['name']}")
                for container in pod['containers']:
                    logs = k8s_monitor.get_pod_logs(pod['name'], container)
                    
                    # Create logs directory if it doesn't exist
                    logs_dir = f"logs/pods/{pod['name']}"
                    os.makedirs(logs_dir, exist_ok=True)
                    
                    # Save logs to file
                    log_file = f"{logs_dir}/{container}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                    with open(log_file, 'w') as f:
                        f.write(logs)
                    
                    logger.info(f"Saved logs for {pod['name']}/{container} to {log_file}")
    
    # Get resource metrics for all pods
    metrics = k8s_monitor.get_resource_metrics()
    for pod_metric in metrics:
        pod_name = pod_metric['name']
        for container_name, container_metrics in pod_metric['containers'].items():
            cpu = container_metrics['cpu']
            memory = container_metrics['memory']
            logger.info(f"Resource metrics - Pod: {pod_name}, Container: {container_name}, CPU: {cpu}, Memory: {memory}")
    
    logger.info(f"Completed monitoring cycle at {datetime.now().isoformat()}")

def main():
    """Main entry point"""
    # Load configuration
    config = load_config()
    
    # Set up logging
    logger = setup_logging(config)
    
    # Initialize monitors
    api_monitor = ApiMonitor(config)
    k8s_monitor = KubernetesMonitor(config['kubernetes'])
    
    # Log startup information
    logger.info("=== FastAPI Monitoring System Started ===")
    logger.info(f"Monitoring API at: {config['api']['base_url']}")
    logger.info(f"Kubernetes namespace: {config['kubernetes']['namespace']}")
    logger.info(f"Monitoring interval: {config['monitoring']['interval']} seconds")
    
    # Schedule regular monitoring
    interval = config['monitoring']['interval']
    logger.info(f"Scheduling monitoring every {interval} seconds")
    
    # Run the first cycle immediately
    run_monitoring_cycle(api_monitor, k8s_monitor, logger)
    
    # Schedule subsequent cycles
    schedule.every(interval).seconds.do(run_monitoring_cycle, api_monitor, k8s_monitor, logger)
    
    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
        raise
    finally:
        logger.info("=== FastAPI Monitoring System Stopped ===")

if __name__ == "__main__":
    main()
