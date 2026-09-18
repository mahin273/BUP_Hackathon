"""
Regression Test Runner for CI/CD Integration
Runs after every merge to catch regressions
Can be integrated with GitHub Actions, GitLab CI, or run locally
"""

import sys
import argparse
import json
from datetime import datetime
from typing import Dict, Any, List

from test_harness import run_all_tests, print_header, print_success, print_error, print_warning, print_info, Colors
from test_data import PUBLIC_TEST_CASES
from custom_test_scenarios import CUSTOM_TEST_SCENARIOS


def run_regression_suite(
    base_url: str,
    include_custom: bool = True,
    timeout: int = 30,
    tolerance: float = 0.01,
    stop_on_failure: bool = False
) -> Dict[str, Any]:
    """
    Run full regression test suite
    
    Args:
        base_url: Base URL of the API
        include_custom: Whether to include custom test scenarios
        timeout: Request timeout in seconds
        tolerance: Floating point comparison tolerance
        stop_on_failure: Stop on first failure
        
    Returns:
        Combined test results
    """
    print_header("GridWise Regression Test Suite")
    print_info(f"Target: {base_url}")
    print_info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    all_results = {
        "timestamp": datetime.now().isoformat(),
        "url": base_url,
        "test_suites": [],
        "total_passed": 0,
        "total_failed": 0,
        "total_tests": 0,
        "all_passed": False
    }
    
    # Run public test cases
    print_header("Running Public Test Cases (10 scenarios)")
    public_results = run_all_tests(base_url, PUBLIC_TEST_CASES, timeout, tolerance, stop_on_failure)
    all_results["test_suites"].append({
        "name": "Public Test Cases",
        "results": public_results
    })
    all_results["total_passed"] += public_results["passed"]
    all_results["total_failed"] += public_results["failed"]
    all_results["total_tests"] += public_results["total"]
    
    # Stop if public tests failed and stop_on_failure is set
    if not public_results["overall_passed"] and stop_on_failure:
        print_warning("Public tests failed, skipping custom scenarios")
        all_results["all_passed"] = False
        return all_results
    
    # Run custom test scenarios if requested
    if include_custom:
        print_header("Running Custom Test Scenarios (15 scenarios)")
        custom_results = run_all_tests(base_url, CUSTOM_TEST_SCENARIOS, timeout, tolerance, stop_on_failure)
        all_results["test_suites"].append({
            "name": "Custom Test Scenarios",
            "results": custom_results
        })
        all_results["total_passed"] += custom_results["passed"]
        all_results["total_failed"] += custom_results["failed"]
        all_results["total_tests"] += custom_results["total"]
    
    all_results["all_passed"] = all_results["total_failed"] == 0
    
    return all_results


def print_regression_summary(results: Dict[str, Any]):
    """Print detailed regression summary"""
    print_header("Regression Test Summary")
    
    print(f"{Colors.BOLD}Overall Results:{Colors.END}")
    print(f"  Total Tests: {results['total_tests']}")
    print_success(f"  Passed: {results['total_passed']}")
    
    if results['total_failed'] > 0:
        print_error(f"  Failed: {results['total_failed']}")
    
    print(f"\n{Colors.BOLD}Suite Breakdown:{Colors.END}")
    for suite in results["test_suites"]:
        suite_name = suite["name"]
        suite_results = suite["results"]
        
        status_icon = "✓" if suite_results["overall_passed"] else "✗"
        status_color = Colors.GREEN if suite_results["overall_passed"] else Colors.RED
        
        print(f"  {status_color}{status_icon} {suite_name}{Colors.END}")
        print(f"    Passed: {suite_results['passed']}/{suite_results['total']}")
        
        if suite_results['failed'] > 0:
            print(f"    {Colors.RED}Failed: {suite_results['failed']}{Colors.END}")
            
            # List failed test IDs
            failed_ids = [r["scenario_id"] for r in suite_results["results"] if not r["passed"]]
            if failed_ids:
                print(f"    Failed scenarios: {', '.join(failed_ids[:5])}")
                if len(failed_ids) > 5:
                    print(f"    ... and {len(failed_ids) - 5} more")
    
    # Final verdict
    print()
    if results["all_passed"]:
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'✓ REGRESSION SUITE PASSED'.center(80)}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}{'✗ REGRESSION SUITE FAILED'.center(80)}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"\n{Colors.RED}ACTION REQUIRED: Fix failing tests before merging{Colors.END}")


def generate_ci_report(results: Dict[str, Any], format: str = "github") -> str:
    """
    Generate CI-friendly report output
    
    Args:
        results: Test results
        format: Output format ('github', 'gitlab', or 'text')
        
    Returns:
        Formatted report string
    """
    if format == "github":
        # GitHub Actions format
        report = "## GridWise Regression Test Results\n\n"
        
        if results["all_passed"]:
            report += "✅ **All tests passed**\n\n"
        else:
            report += f"❌ **{results['total_failed']} tests failed**\n\n"
        
        report += f"- Total: {results['total_tests']}\n"
        report += f"- Passed: {results['total_passed']}\n"
        report += f"- Failed: {results['total_failed']}\n\n"
        
        report += "### Test Suites\n\n"
        for suite in results["test_suites"]:
            suite_name = suite["name"]
            suite_results = suite["results"]
            icon = "✅" if suite_results["overall_passed"] else "❌"
            report += f"{icon} **{suite_name}**: {suite_results['passed']}/{suite_results['total']} passed\n"
        
        return report
    
    elif format == "gitlab":
        # GitLab CI format
        report = "# GridWise Regression Test Results\n\n"
        
        status = "passed" if results["all_passed"] else "failed"
        report += f"Status: **{status}**\n\n"
        report += f"Results: {results['total_passed']}/{results['total_tests']} passed\n\n"
        
        return report
    
    else:  # text
        report = "GridWise Regression Test Results\n"
        report += "=" * 50 + "\n"
        report += f"Total: {results['total_tests']}\n"
        report += f"Passed: {results['total_passed']}\n"
        report += f"Failed: {results['total_failed']}\n"
        report += f"Status: {'PASS' if results['all_passed'] else 'FAIL'}\n"
        return report


def save_regression_results(results: Dict[str, Any], output_dir: str = "."):
    """
    Save regression results in multiple formats
    
    Args:
        results: Test results
        output_dir: Directory to save results
    """
    import os
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save JSON
    json_file = os.path.join(output_dir, f"regression_results_{timestamp}.json")
    try:
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
        print_success(f"Saved JSON results to {json_file}")
    except Exception as e:
        print_error(f"Failed to save JSON: {str(e)}")
    
    # Save GitHub-style report
    report_file = os.path.join(output_dir, f"regression_report_{timestamp}.md")
    try:
        with open(report_file, 'w') as f:
            f.write(generate_ci_report(results, "github"))
        print_success(f"Saved report to {report_file}")
    except Exception as e:
        print_error(f"Failed to save report: {str(e)}")
    
    # Save latest symlink/copy for CI
    latest_json = os.path.join(output_dir, "regression_latest.json")
    try:
        with open(latest_json, 'w') as f:
            json.dump(results, f, indent=2)
        print_success(f"Saved latest results to {latest_json}")
    except Exception as e:
        print_error(f"Failed to save latest: {str(e)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="GridWise Regression Test Runner - Run after every merge"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--no-custom",
        action="store_true",
        help="Skip custom test scenarios (only run public tests)"
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
        "--output-dir",
        default=".",
        help="Directory to save results (default: current directory)"
    )
    parser.add_argument(
        "--ci-format",
        choices=["github", "gitlab", "text"],
        help="Generate CI-specific report format"
    )
    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Save results to files"
    )
    
    args = parser.parse_args()
    
    # Run regression suite
    results = run_regression_suite(
        args.url,
        include_custom=not args.no_custom,
        timeout=args.timeout,
        tolerance=args.tolerance,
        stop_on_failure=args.stop_on_failure
    )
    
    # Print summary
    print_regression_summary(results)
    
    # Generate CI report if requested
    if args.ci_format:
        print(f"\n{Colors.CYAN}CI Report ({args.ci_format}):{Colors.END}\n")
        print(generate_ci_report(results, args.ci_format))
    
    # Save results if requested
    if args.save_results:
        save_regression_results(results, args.output_dir)
    
    # Exit with appropriate code
    sys.exit(0 if results["all_passed"] else 1)


if __name__ == "__main__":
    main()
