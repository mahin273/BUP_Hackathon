"""
Main Test Harness for GridWise API
Loops through test cases, POSTs to API, and validates all constraints
"""

import requests
import json
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import argparse

from test_data import PUBLIC_TEST_CASES
from validators import validate_all_constraints
from directive_validator import validate_all_directives


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")


def test_health_endpoint(base_url: str, timeout: int = 5) -> bool:
    """
    Test the /health endpoint
    
    Args:
        base_url: Base URL of the API
        timeout: Request timeout in seconds
        
    Returns:
        True if health check passes
    """
    print_header("Testing Health Endpoint")
    
    try:
        response = requests.get(f"{base_url}/health", timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                print_success(f"Health check passed: {data}")
                return True
            else:
                print_error(f"Health check returned unexpected data: {data}")
                return False
        else:
            print_error(f"Health check failed with status {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print_error(f"Health check timed out after {timeout} seconds")
        return False
    except requests.exceptions.ConnectionError:
        print_error(f"Could not connect to {base_url}")
        return False
    except Exception as e:
        print_error(f"Health check failed: {str(e)}")
        return False


def run_test_case(
    base_url: str,
    test_case: Dict[str, Any],
    timeout: int = 30,
    tolerance: float = 0.01
) -> Dict[str, Any]:
    """
    Run a single test case against the API
    
    Args:
        base_url: Base URL of the API
        test_case: Test case data
        timeout: Request timeout in seconds
        tolerance: Floating point comparison tolerance
        
    Returns:
        Dict with test results
    """
    scenario_id = test_case["scenario_id"]
    result = {
        "scenario_id": scenario_id,
        "passed": False,
        "response_received": False,
        "status_code": None,
        "errors": [],
        "constraint_results": None,
        "directive_results": None,
        "response_time_ms": None
    }
    
    print(f"\n{Colors.BOLD}Testing: {scenario_id}{Colors.END}")
    print(f"Notes: {test_case['operator_notes']}")
    
    try:
        # Make the POST request
        start_time = datetime.now()
        response = requests.post(
            f"{base_url}/optimize-energy",
            json=test_case,
            timeout=timeout
        )
        end_time = datetime.now()
        
        result["response_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
        result["status_code"] = response.status_code
        result["response_received"] = True
        
        print_info(f"Response time: {result['response_time_ms']}ms")
        print_info(f"Status code: {response.status_code}")
        
        # Check for successful response
        if response.status_code != 200:
            result["errors"].append(f"Expected status 200, got {response.status_code}")
            try:
                error_data = response.json()
                print_error(f"Error response: {json.dumps(error_data, indent=2)}")
            except:
                print_error(f"Response text: {response.text[:500]}")
            return result
        
        # Parse response
        try:
            api_response = response.json()
        except json.JSONDecodeError as e:
            result["errors"].append(f"Failed to parse JSON response: {str(e)}")
            print_error(f"Invalid JSON response")
            return result
        
        # Validate response has required fields
        required_fields = [
            "scenario_id", "directive_interpretation", "hourly_plan",
            "total_grid_kwh", "total_cost_bdt", "peak_grid_kwh", "plan_summary"
        ]
        missing_fields = [f for f in required_fields if f not in api_response]
        if missing_fields:
            result["errors"].append(f"Missing required fields: {missing_fields}")
            print_error(f"Missing fields: {missing_fields}")
            return result
        
        # Validate scenario_id matches
        if api_response["scenario_id"] != scenario_id:
            result["errors"].append(
                f"Scenario ID mismatch: expected {scenario_id}, got {api_response['scenario_id']}"
            )
            print_warning(f"Scenario ID mismatch")
        
        # Run constraint validations
        print_info("Running constraint validations...")
        constraints_valid, constraint_results = validate_all_constraints(
            api_response, test_case, tolerance
        )
        result["constraint_results"] = constraint_results
        
        # Run directive validations
        print_info("Running directive validations...")
        directives_valid, directive_results = validate_all_directives(
            api_response["directive_interpretation"],
            test_case,
            api_response["hourly_plan"],
            tolerance
        )
        result["directive_results"] = directive_results
        
        # Print validation results
        print(f"\n{Colors.BOLD}Validation Results:{Colors.END}")
        
        # Constraint checks
        for check_name, check_result in constraint_results["checks"].items():
            if check_result["valid"]:
                print_success(f"{check_name}: PASSED")
            else:
                print_error(f"{check_name}: FAILED")
                for error in check_result["errors"]:
                    print(f"  {Colors.RED}- {error}{Colors.END}")
                result["errors"].extend(check_result["errors"])
        
        # Directive checks
        for check_name, check_result in directive_results["checks"].items():
            if check_result["valid"]:
                print_success(f"{check_name}: PASSED")
            else:
                print_error(f"{check_name}: FAILED")
                for error in check_result["errors"]:
                    print(f"  {Colors.RED}- {error}{Colors.END}")
                result["errors"].extend(check_result["errors"])
        
        # Overall result
        result["passed"] = constraints_valid and directives_valid and len(result["errors"]) == 0
        
        if result["passed"]:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ TEST PASSED{Colors.END}")
            print_info(f"Total cost: {api_response['total_cost_bdt']:.2f} BDT")
            print_info(f"Total grid: {api_response['total_grid_kwh']:.2f} kWh")
            print_info(f"Peak grid: {api_response['peak_grid_kwh']:.2f} kWh")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ TEST FAILED{Colors.END}")
        
    except requests.exceptions.Timeout:
        result["errors"].append(f"Request timed out after {timeout} seconds")
        print_error(f"Request timeout")
    except requests.exceptions.ConnectionError:
        result["errors"].append(f"Could not connect to {base_url}")
        print_error(f"Connection error")
    except Exception as e:
        result["errors"].append(f"Unexpected error: {str(e)}")
        print_error(f"Unexpected error: {str(e)}")
    
    return result


def run_all_tests(
    base_url: str,
    test_cases: list = None,
    timeout: int = 30,
    tolerance: float = 0.01,
    stop_on_failure: bool = False
) -> Dict[str, Any]:
    """
    Run all test cases
    
    Args:
        base_url: Base URL of the API
        test_cases: List of test cases (defaults to PUBLIC_TEST_CASES)
        timeout: Request timeout in seconds
        tolerance: Floating point comparison tolerance
        stop_on_failure: Stop testing on first failure
        
    Returns:
        Dict with overall test results
    """
    if test_cases is None:
        test_cases = PUBLIC_TEST_CASES
    
    print_header(f"GridWise API Test Harness")
    print_info(f"Target URL: {base_url}")
    print_info(f"Test cases: {len(test_cases)}")
    print_info(f"Timeout: {timeout}s")
    print_info(f"Tolerance: {tolerance}")
    
    # Test health endpoint first
    if not test_health_endpoint(base_url, timeout=5):
        print_error("Health check failed. Aborting tests.")
        return {
            "total": len(test_cases),
            "passed": 0,
            "failed": len(test_cases),
            "skipped": len(test_cases),
            "results": [],
            "overall_passed": False
        }
    
    # Run test cases
    results = []
    passed_count = 0
    failed_count = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print_header(f"Test Case {i}/{len(test_cases)}")
        
        result = run_test_case(base_url, test_case, timeout, tolerance)
        results.append(result)
        
        if result["passed"]:
            passed_count += 1
        else:
            failed_count += 1
            if stop_on_failure:
                print_warning("Stopping on first failure")
                break
    
    # Print summary
    print_header("Test Summary")
    print(f"Total tests: {len(test_cases)}")
    print_success(f"Passed: {passed_count}")
    print_error(f"Failed: {failed_count}")
    
    if failed_count > 0:
        print(f"\n{Colors.BOLD}Failed Tests:{Colors.END}")
        for result in results:
            if not result["passed"]:
                print_error(f"  - {result['scenario_id']}")
                if result["errors"]:
                    for error in result["errors"][:3]:  # Show first 3 errors
                        print(f"    {Colors.RED}• {error}{Colors.END}")
                    if len(result["errors"]) > 3:
                        print(f"    {Colors.RED}... and {len(result['errors']) - 3} more errors{Colors.END}")
    
    overall_passed = failed_count == 0
    
    if overall_passed:
        print(f"\n{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'ALL TESTS PASSED!'.center(80)}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}{'SOME TESTS FAILED'.center(80)}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}{'='*80}{Colors.END}")
    
    return {
        "total": len(test_cases),
        "passed": passed_count,
        "failed": failed_count,
        "skipped": len(test_cases) - len(results),
        "results": results,
        "overall_passed": overall_passed
    }


def save_results(results: Dict[str, Any], output_file: str):
    """Save test results to JSON file"""
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print_success(f"Results saved to {output_file}")
    except Exception as e:
        print_error(f"Failed to save results: {str(e)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="GridWise API Test Harness")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Floating point comparison tolerance (default: 0.01)"
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop testing on first failure"
    )
    parser.add_argument(
        "--output",
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--case",
        type=int,
        help="Run only specific test case number (1-10)"
    )
    
    args = parser.parse_args()
    
    # Select test cases
    test_cases = PUBLIC_TEST_CASES
    if args.case:
        if 1 <= args.case <= len(PUBLIC_TEST_CASES):
            test_cases = [PUBLIC_TEST_CASES[args.case - 1]]
            print_info(f"Running only test case #{args.case}")
        else:
            print_error(f"Invalid test case number: {args.case}")
            sys.exit(1)
    
    # Run tests
    results = run_all_tests(
        args.url,
        test_cases,
        args.timeout,
        args.tolerance,
        args.stop_on_failure
    )
    
    # Save results if requested
    if args.output:
        save_results(results, args.output)
    
    # Exit with appropriate code
    sys.exit(0 if results["overall_passed"] else 1)


if __name__ == "__main__":
    main()
