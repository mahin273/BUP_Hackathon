"""
Submission Checklist Verification Script
Verifies deployment URL, health endpoint, and all pre-submission requirements
Run this before final submission to ensure everything is ready for judging
"""

import requests
import sys
import socket
import argparse
from typing import Dict, List, Tuple
from datetime import datetime

from test_harness import Colors, print_header, print_success, print_error, print_warning, print_info


def check_url_format(url: str) -> Tuple[bool, str]:
    """
    Check if URL is properly formatted
    
    Returns:
        (is_valid, message)
    """
    if not url:
        return False, "URL is empty"
    
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"
    
    if url.endswith("/"):
        return False, "URL should not end with trailing slash"
    
    if "localhost" in url or "127.0.0.1" in url:
        return False, "URL contains localhost/127.0.0.1 - must be publicly accessible"
    
    return True, "URL format is valid"


def check_dns_resolution(url: str) -> Tuple[bool, str]:
    """
    Check if the domain resolves to an IP address
    
    Returns:
        (is_valid, message)
    """
    try:
        # Extract hostname from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.netloc
        
        if not hostname:
            return False, "Could not extract hostname from URL"
        
        # Try to resolve DNS
        ip_address = socket.gethostbyname(hostname)
        return True, f"Domain resolves to {ip_address}"
    
    except socket.gaierror:
        return False, "Domain does not resolve (DNS lookup failed)"
    except Exception as e:
        return False, f"DNS resolution error: {str(e)}"


def check_health_endpoint(url: str, timeout: int = 10) -> Tuple[bool, str]:
    """
    Check if /health endpoint returns correct response
    
    Returns:
        (is_valid, message)
    """
    try:
        response = requests.get(f"{url}/health", timeout=timeout)
        
        if response.status_code != 200:
            return False, f"Health endpoint returned status {response.status_code} (expected 200)"
        
        try:
            data = response.json()
        except:
            return False, "Health endpoint did not return valid JSON"
        
        if data.get("status") != "ok":
            return False, f"Health endpoint returned {data} (expected {{'status': 'ok'}})"
        
        return True, "Health endpoint responding correctly"
    
    except requests.exceptions.Timeout:
        return False, f"Health endpoint timed out after {timeout} seconds"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to server (connection refused)"
    except requests.exceptions.SSLError:
        return False, "SSL certificate verification failed"
    except Exception as e:
        return False, f"Health check failed: {str(e)}"


def check_optimize_endpoint(url: str, timeout: int = 30) -> Tuple[bool, str]:
    """
    Check if /optimize-energy endpoint exists and accepts requests
    
    Returns:
        (is_valid, message)
    """
    # Simple valid test payload
    test_payload = {
        "scenario_id": "submission_check_001",
        "operator_notes": ["No special conditions"],
        "hours": [
            {"hour": h, "demand_kwh": 50.0, "solar_available_kwh": 20.0, "tariff_bdt_per_kwh": 6.0}
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 100.0,
            "initial_energy_kwh": 50.0,
            "max_charge_per_hour": 20.0,
            "max_discharge_per_hour": 20.0,
            "min_energy_kwh": 10.0
        }
    }
    
    try:
        response = requests.post(f"{url}/optimize-energy", json=test_payload, timeout=timeout)
        
        if response.status_code == 200:
            try:
                data = response.json()
                required_fields = ["scenario_id", "directive_interpretation", "hourly_plan", 
                                   "total_grid_kwh", "total_cost_bdt", "peak_grid_kwh"]
                missing = [f for f in required_fields if f not in data]
                if missing:
                    return False, f"Response missing required fields: {missing}"
                return True, "Optimize endpoint responding with valid structure"
            except:
                return False, "Optimize endpoint did not return valid JSON"
        else:
            return False, f"Optimize endpoint returned status {response.status_code} (expected 200)"
    
    except requests.exceptions.Timeout:
        return False, f"Optimize endpoint timed out after {timeout} seconds"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to optimize endpoint"
    except Exception as e:
        return False, f"Optimize endpoint check failed: {str(e)}"


def check_error_handling(url: str, timeout: int = 10) -> Tuple[bool, str]:
    """
    Check if API handles malformed requests properly (returns 400/422, not 500)
    
    Returns:
        (is_valid, message)
    """
    # Malformed payload - missing required fields
    bad_payload = {
        "scenario_id": "malformed_test"
        # Missing everything else
    }
    
    try:
        response = requests.post(f"{url}/optimize-energy", json=bad_payload, timeout=timeout)
        
        if response.status_code in (400, 422):
            return True, f"API correctly returns {response.status_code} for malformed input"
        elif response.status_code == 500:
            return False, "API returns 500 for malformed input (should be 400/422)"
        else:
            return False, f"Unexpected status code {response.status_code} for malformed input"
    
    except Exception as e:
        return False, f"Error handling check failed: {str(e)}"


def check_https_protocol(url: str) -> Tuple[bool, str]:
    """
    Check if URL uses HTTPS (recommended for production)
    
    Returns:
        (is_valid, message)
    """
    if url.startswith("https://"):
        return True, "Using secure HTTPS protocol"
    else:
        return True, "Using HTTP (HTTPS recommended but not required)"


def check_response_time(url: str, timeout: int = 30) -> Tuple[bool, str]:
    """
    Check if API responds within reasonable time
    
    Returns:
        (is_valid, message)
    """
    test_payload = {
        "scenario_id": "timing_check_001",
        "operator_notes": ["Standard test"],
        "hours": [
            {"hour": h, "demand_kwh": 50.0, "solar_available_kwh": 20.0, "tariff_bdt_per_kwh": 6.0}
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 100.0,
            "initial_energy_kwh": 50.0,
            "max_charge_per_hour": 20.0,
            "max_discharge_per_hour": 20.0,
            "min_energy_kwh": 10.0
        }
    }
    
    try:
        start = datetime.now()
        response = requests.post(f"{url}/optimize-energy", json=test_payload, timeout=timeout)
        end = datetime.now()
        
        elapsed_ms = int((end - start).total_seconds() * 1000)
        
        if response.status_code != 200:
            return False, f"Request failed with status {response.status_code}"
        
        if elapsed_ms > 10000:
            return False, f"Response time too slow: {elapsed_ms}ms (should be < 10s)"
        elif elapsed_ms > 5000:
            return True, f"Response time acceptable but slow: {elapsed_ms}ms"
        else:
            return True, f"Response time good: {elapsed_ms}ms"
    
    except requests.exceptions.Timeout:
        return False, f"Request timed out (> {timeout}s)"
    except Exception as e:
        return False, f"Response time check failed: {str(e)}"


def check_external_reachability(url: str) -> Tuple[bool, str]:
    """
    Verify the URL is externally reachable (not just from local network)
    Uses a simple heuristic - actual verification would need external probe
    
    Returns:
        (is_valid, message)
    """
    # Check for common local/private indicators
    local_indicators = ["localhost", "127.0.0.1", "192.168.", "10.", "172.16.", "172.31."]
    
    for indicator in local_indicators:
        if indicator in url:
            return False, f"URL contains '{indicator}' - likely not externally accessible"
    
    # If we got here and health check passed, it's probably reachable
    return True, "URL appears to be externally reachable (verify from mobile data if possible)"


def run_submission_checklist(url: str) -> Dict:
    """
    Run all submission checks
    
    Args:
        url: Base URL of the deployed API
        
    Returns:
        Dict with check results
    """
    print_header("GridWise Submission Checklist")
    print_info(f"Checking deployment: {url}")
    print_info(f"Timestamp: {datetime.now().isoformat()}\n")
    
    checks = [
        ("URL Format", lambda: check_url_format(url)),
        ("DNS Resolution", lambda: check_dns_resolution(url)),
        ("HTTPS Protocol", lambda: check_https_protocol(url)),
        ("Health Endpoint", lambda: check_health_endpoint(url)),
        ("Optimize Endpoint", lambda: check_optimize_endpoint(url)),
        ("Error Handling", lambda: check_error_handling(url)),
        ("Response Time", lambda: check_response_time(url)),
        ("External Reachability", lambda: check_external_reachability(url)),
    ]
    
    results = {
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "checks": [],
        "passed_count": 0,
        "failed_count": 0,
        "all_passed": False
    }
    
    print(f"{Colors.BOLD}Running Checks:{Colors.END}\n")
    
    for check_name, check_func in checks:
        try:
            passed, message = check_func()
            
            check_result = {
                "name": check_name,
                "passed": passed,
                "message": message
            }
            results["checks"].append(check_result)
            
            if passed:
                print_success(f"{check_name}: {message}")
                results["passed_count"] += 1
            else:
                print_error(f"{check_name}: {message}")
                results["failed_count"] += 1
        
        except Exception as e:
            print_error(f"{check_name}: Unexpected error - {str(e)}")
            results["checks"].append({
                "name": check_name,
                "passed": False,
                "message": f"Unexpected error: {str(e)}"
            })
            results["failed_count"] += 1
    
    results["all_passed"] = results["failed_count"] == 0
    
    # Print summary
    print_header("Checklist Summary")
    print(f"Total Checks: {len(checks)}")
    print_success(f"Passed: {results['passed_count']}")
    if results["failed_count"] > 0:
        print_error(f"Failed: {results['failed_count']}")
    
    # Print manual verification reminders
    print(f"\n{Colors.BOLD}{Colors.YELLOW}Manual Verification Reminders:{Colors.END}")
    print_warning("1. Verify URL from mobile data (not your dev network)")
    print_warning("2. Check that repo is pushed to remote")
    print_warning("3. Ensure README.md is present and up to date")
    print_warning("4. Verify all team member names are in submission")
    print_warning("5. Double-check no API keys or secrets in repo")
    
    if results["all_passed"]:
        print(f"\n{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'✓ ALL CHECKS PASSED - READY FOR SUBMISSION'.center(80)}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}{'✗ SOME CHECKS FAILED - FIX BEFORE SUBMITTING'.center(80)}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}{'='*80}{Colors.END}")
        
        print(f"\n{Colors.BOLD}Failed Checks:{Colors.END}")
        for check in results["checks"]:
            if not check["passed"]:
                print_error(f"  - {check['name']}: {check['message']}")
    
    return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="GridWise Submission Checklist - Verify deployment readiness"
    )
    parser.add_argument(
        "url",
        help="Deployed API base URL (e.g., https://gridwise.onrender.com)"
    )
    parser.add_argument(
        "--json",
        help="Save results to JSON file"
    )
    
    args = parser.parse_args()
    
    # Remove trailing slash if present
    url = args.url.rstrip("/")
    
    # Run checklist
    results = run_submission_checklist(url)
    
    # Save to JSON if requested
    if args.json:
        import json
        try:
            with open(args.json, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n{Colors.CYAN}Results saved to {args.json}{Colors.END}")
        except Exception as e:
            print_error(f"Failed to save results: {str(e)}")
    
    # Exit with appropriate code
    sys.exit(0 if results["all_passed"] else 1)


if __name__ == "__main__":
    main()
