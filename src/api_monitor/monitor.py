import time
import requests
from datetime import datetime
from typing import Dict, List, Any
from loguru import logger

class ApiMonitor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config['api']['base_url']
        self.endpoints = config['api']['endpoints']
        self.interval = config['monitoring']['interval']
        self.timeout = config['monitoring']['timeout']
        self.retries = config['monitoring']['retries']
        
    def check_endpoint(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Check a single API endpoint and return results"""
        path = endpoint['path']
        method = endpoint['method']
        expected_status = endpoint['expected_status']
        timeout = endpoint.get('timeout', self.timeout)
        
        url = f"{self.base_url}{path}"
        
        result = {
            'url': url,
            'method': method,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'status_code': None,
            'response_time': None,
            'error': None
        }
        
        for attempt in range(self.retries):
            try:
                start_time = time.time()
                response = requests.request(
                    method=method,
                    url=url,
                    timeout=timeout
                )
                end_time = time.time()
                
                result['response_time'] = (end_time - start_time) * 1000  # Convert to ms
                result['status_code'] = response.status_code
                
                if response.status_code == expected_status:
                    result['success'] = True
                    break
                else:
                    result['error'] = f"Unexpected status code: {response.status_code}"
                    
            except requests.exceptions.Timeout:
                result['error'] = "Request timed out"
            except requests.exceptions.ConnectionError:
                result['error'] = "Connection error"
            except Exception as e:
                result['error'] = str(e)
            
            # Wait before retrying
            if attempt < self.retries - 1:
                time.sleep(1)
        
        # Log results
        if result['success']:
            logger.info(f"Endpoint {url} is UP. Response time: {result['response_time']:.2f}ms")
        else:
            logger.error(f"Endpoint {url} is DOWN. Error: {result['error']}")
            
        return result
    
    def check_all_endpoints(self) -> List[Dict[str, Any]]:
        """Check all configured endpoints"""
        results = []
        
        for endpoint in self.endpoints:
            result = self.check_endpoint(endpoint)
            results.append(result)
            
        return results
