#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test malware file execution and EDR collection functionality
"""
import requests
import time
import json
import sys
import os

# For Windows output redirection compatibility
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

def test_malware_execution():
    """Test malware file execution and EDR collection functionality"""

    # API configuration
    base_url = "http://localhost:8000"
    api_key = "edr-analysis-2025"
    headers = {"X-API-Key": api_key}

    # Sample file path
    file_path = "./tests/C9E0917FE3231A652C014AD76B55B26A.exe"
    file_path = "./tests/calc.exe"
    #file_path = "./tests/b91ce2fa41029f6955bff20079468448.dll"
   
    try:
   
        health_response = requests.get(f"{base_url}/api/health")
        if health_response.status_code == 200:
            print("[OK] API service health check passed")
        else:
            print("[ERROR] API service unavailable")
            return

        # 2. Submit sample file for analysis
        print(f"\n[SUBMIT] Submitting sample file for analysis: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path, f, 'application/octet-stream')}
            data = {'timeout': 180}  # 3 minutes timeout

            response = requests.post(
                f"{base_url}/api/analyze",
                headers=headers,
                files=files,
                data=data
            )

        if response.status_code != 200:
            print(f"[ERROR] Submission failed: {response.status_code} - {response.text}")
            return

        result = response.json()
        task_id = result['task_id']
        print(f"[OK] Submission successful, Task ID: {task_id}")

        # 3. Monitor task progress
        print(f"\n[MONITOR] Monitoring task progress...")
        start_time = time.time()
        
        while True:
            elapsed = int(time.time() - start_time)
            
            # Query task status
            status_response = requests.get(
                f"{base_url}/api/task/{task_id}",
                headers=headers
            )

            if status_response.status_code != 200:
                print(f"[ERROR] Failed to query task status: {status_response.status_code}")
                break

            status_data = status_response.json()
            task_status = status_data.get('status', 'unknown')

            # Display detailed status
            if 'vm_results' in status_data and status_data['vm_results']:
                vm_result = status_data['vm_results']
                for vm in vm_result:
                    vm_status = vm.get('status', 'unknown')
                    vm_name = vm.get('vm_name', 'unknown')
                    print(f"   [{elapsed:3d}s] {task_status} - {vm_name}: {vm_status}")

            else:
                print(f"   [{elapsed:3d}s] {task_status}")
            
            # Check if completed
            if task_status in ['completed', 'failed']:
                break

            # Timeout check
            if elapsed > 600:  # 5 minutes timeout
                print("[WARNING] Task monitoring timeout")
                break

            time.sleep(9)

        # 4. Get final results
        print(f"\n[RESULTS] Retrieving analysis results...")
        
        if task_status == 'completed':
            result_response = requests.get(
                f"{base_url}/api/result/{task_id}",
                headers=headers
            )
            
            if result_response.status_code == 200:
                result_data = result_response.json()
                
                
                # Display result summary
                print(f"\n[SUMMARY] Analysis Result Summary:")
                print(f"   - Task ID: {result_data.get('task_id', 'N/A')}")
                print(f"   - File Name: {file_path}")
                print(f"   - Status: {result_data.get('status', 'N/A')}")
                print("[OK] Analysis completed!")
                print(json.dumps(result_data, indent=2, ensure_ascii=False))

                # Display VM results
                if 'vm_results' in result_data:
                    for vm_result in result_data['vm_results']:
                        vm_name = vm_result.get('vm_name', 'unknown')
                        vm_status = vm_result.get('status', 'unknown')
                        alerts = vm_result.get('alerts', [])

                        print(f"\n[VM] Virtual Machine: {vm_name}")
                        print(f"   - Status: {vm_status}")
                        print(f"   - EDR Alert Count: {len(alerts)}")

                        if alerts:
                            print("   - Alert Details:")
                            for i, alert in enumerate(alerts, 1):
                                print(f"     {i}. Alert Name: {alert.get('alert_type', 'Unknown')}")

                        else:
                            print("   - No EDR alerts")

            else:
                print(f"[ERROR] Failed to retrieve results: {result_response.status_code}")
        else:
            print(f"[ERROR] Task not completed, status: {task_status}")

    except Exception as e:
        print(f"[ERROR] Exception occurred during testing: {str(e)}")

if __name__ == "__main__":
    test_malware_execution()
