import os
import yaml
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file"""
    config_path = os.environ.get('CONFIG_PATH', 'config/config.yaml')
    
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    
    # Override with environment variables if provided
    if os.environ.get('API_BASE_URL'):
        config['api']['base_url'] = os.environ.get('API_BASE_URL')
    
    if os.environ.get('API_EXTERNAL_URL'):
        config['api']['external_url'] = os.environ.get('API_EXTERNAL_URL')
    
    if os.environ.get('K8S_NAMESPACE'):
        config['kubernetes']['namespace'] = os.environ.get('K8S_NAMESPACE')
    
    return config
