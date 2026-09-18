# GridWise Test Harness & QA Suite

**Owner: Ramim (20%)** - Complete test infrastructure for the GridWise energy optimization API.

## 📁 File Structure

```
tests/
├── README.md                      # This file
├── test_data.py                   # 10 public test cases covering all directive types
├── custom_test_scenarios.py       # 15 additional custom scenarios with paraphrased notes
├── validators.py                  # Core constraint validation functions
├── directive_validator.py         # Directive interpretation validation
├── test_harness.py               # Main test runner script
├── run_regression.py             # Regression test runner for CI/CD
├── submission_checklist.py       # Pre-submission verification script
└── test_*.py                     # pytest test files (if using pytest)
```

## 🚀 Quick Start

### Run All Public Tests
```bash
python tests/test_harness.py --url http://localhost:8000
```

### Run Single Test Case
```bash
python tests/test_harness.py --url http://localhost:8000 --case 3
```

### Run Regression Suite (Public + Custom)
```bash
python tests/run_regression.py --url http://localhost:8000
```

### Verify Deployment Before Submission
```bash
python tests/submission_checklist.py https://your-deployed-api.onrender.com
```

## 📊 Test Coverage

### Public Test Cases (10 scenarios)
1. **Solar Reduction** - Cloud cover reducing solar output
2. **Minimum Battery Reserve** - Battery level requirements during peak hours
3. **No Charge Window** - Charging prohibited during specific hours
4. **No Discharge Window** - Discharging prohibited during maintenance
5. **Max Grid Window** - Grid usage limits during specific hours
6. **No-op / Distractor** - Notes that don't require action
7. **Combined: Solar + No Charge** - Multiple directives
8. **Combined: Reserve + No Discharge** - Multiple directives
9. **Combined: Max Grid + Solar** - Multiple directives
10. **Stress Test** - All constraints combined

### Custom Test Scenarios (15 scenarios)
- Paraphrased directive notes (testing NLP robustness)
- Natural language variations
- Triple and quadruple directive combinations
- Edge cases (adjacent windows, overnight constraints)
- Percentage-based reserves
- Ambiguous wording tests
- Time format variations
- Distractor-heavy scenarios
- Very short time windows

## 🔍 Validation Checks

### Constraint Validations
- ✅ Energy balance per hour: `grid + solar + discharge = demand + charge`
- ✅ Battery bounds: `min_energy_kwh ≤ battery_energy ≤ capacity_kwh`
- ✅ Battery rate limits: charge/discharge within per-hour limits
- ✅ Battery energy continuity: correct transitions hour-to-hour
- ✅ End-of-day neutrality: `battery_energy[23] == initial_energy_kwh`
- ✅ Hourly plan completeness: exactly 24 hours, 0-23, no gaps
- ✅ Totals recomputation: verify `total_grid_kwh`, `total_cost_bdt`, `peak_grid_kwh`

### Directive Validations
- ✅ Valid directive types (6 allowed types)
- ✅ Note coverage (every note covered exactly once)
- ✅ `applies` field logic (`no_op` special handling)
- ✅ Hours arrays (unique, 0-23, ascending)
- ✅ Structured adjustment fields per type
- ✅ Directive enforcement in hourly_plan

## 📋 Command Line Options

### test_harness.py
```bash
python tests/test_harness.py [options]

Options:
  --url URL              Base URL (default: http://localhost:8000)
  --timeout SECONDS      Request timeout (default: 30)
  --tolerance FLOAT      FP comparison tolerance (default: 0.01)
  --stop-on-failure      Stop on first failure
  --output FILE          Save results to JSON file
  --case NUMBER          Run only specific test case (1-10)
```

### run_regression.py
```bash
python tests/run_regression.py [options]

Options:
  --url URL              Base URL (default: http://localhost:8000)
  --no-custom            Skip custom scenarios (public only)
  --timeout SECONDS      Request timeout (default: 30)
  --tolerance FLOAT      FP comparison tolerance (default: 0.01)
  --stop-on-failure      Stop on first failure
  --output-dir DIR       Directory for results (default: .)
  --ci-format FORMAT     CI report format (github/gitlab/text)
  --save-results         Save results to files
```

### submission_checklist.py
```bash
python tests/submission_checklist.py <URL> [--json FILE]

Example:
  python tests/submission_checklist.py https://gridwise.onrender.com
  python tests/submission_checklist.py https://gridwise.onrender.com --json results.json
```

## 🔄 CI/CD Integration

### GitHub Actions Example
```yaml
name: Regression Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Start API server
        run: |
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 5
      
      - name: Run regression tests
        run: |
          python tests/run_regression.py \
            --url http://localhost:8000 \
            --save-results \
            --ci-format github
      
      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: regression_*.json
```

### Run After Every Merge
```bash
# Add to your .git/hooks/post-merge or CI pipeline
#!/bin/bash
echo "Running regression tests..."
python tests/run_regression.py --url http://localhost:8000 --save-results
```

## 📈 Usage During Development

### Developer Workflow
1. **Start local server**: `uvicorn app.main:app --reload`
2. **Run tests continuously**: Use `--stop-on-failure` during active development
3. **Test specific case**: Use `--case N` to focus on one scenario
4. **Full validation**: Run regression suite before pushing

### Team Lead (Ramim) Responsibilities
- ✅ Run test harness after every team member's merge
- ✅ Monitor for regressions in optimization logic
- ✅ Verify all constraints are satisfied
- ✅ Test custom scenarios regularly (hidden test prep)
- ✅ Run submission checklist before final submission
- ✅ Verify deployment from mobile data/external network

## 🎯 Pre-Submission Checklist

Run these in order before final submission:

```bash
# 1. Run full regression suite locally
python tests/run_regression.py --url http://localhost:8000 --save-results

# 2. Verify deployment is live
python tests/submission_checklist.py https://your-api-url.com

# 3. Run public tests against deployed URL
python tests/test_harness.py --url https://your-api-url.com

# 4. Test from external network (use mobile hotspot or different network)
python tests/submission_checklist.py https://your-api-url.com

# 5. Verify from mobile device browser
curl https://your-api-url.com/health
```

## 🐛 Debugging Failed Tests

### Common Issues

**Energy Balance Violation**
- Check grid + solar + discharge = demand + charge for each hour
- Look for floating point precision issues (use --tolerance)

**Battery Bounds Violation**
- Verify min_energy_kwh and capacity_kwh constraints
- Check directive enforcement (e.g., minimum_battery_reserve)

**End-of-Day Neutrality Failed**
- Battery energy at hour 23 must equal initial_energy_kwh
- Check cumulative charge/discharge calculations

**Directive Not Enforced**
- LLM interpretation may have failed
- Check guardrail validator is catching LLM errors
- Verify optimizer respects directive constraints

**Totals Mismatch**
- Recompute totals from hourly_plan
- Check rounding (should round after computation, not before)

### Verbose Output
```bash
# Save full results for debugging
python tests/test_harness.py --url http://localhost:8000 --output debug.json

# Examine specific test case
python tests/test_harness.py --url http://localhost:8000 --case 7 > test7_output.txt
```

## 📞 Support

For issues or questions about the test suite:
- **Owner**: Ramim
- **Scope**: Test harness, QA, submission verification (20% of project)
- **Integration**: Works with all team member components

## 🎓 Testing Philosophy

The judge scores two things independently:
1. Correct **understanding** of notes (LLM interpretation)
2. Correct **application and optimization** of schedule

Our test suite validates BOTH:
- Directive validation ensures LLM understood correctly
- Constraint validation ensures optimizer applied correctly

**A test passing means the solution is judge-ready for that scenario.**
