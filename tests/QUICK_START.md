# GridWise Test Suite - Quick Start Guide

## 🚀 For Ramim (QA Owner)

### During Development (After Each Merge)

```bash
# 1. Make sure API is running locally
uvicorn app.main:app --reload

# 2. In another terminal, run regression tests
python tests/run_regression.py --url http://localhost:8000
```

### Testing Specific Components

```bash
# Test only public cases (quick check)
python tests/test_harness.py --url http://localhost:8000

# Test only custom scenarios (paraphrase robustness)
python tests/run_regression.py --url http://localhost:8000 --no-custom=false

# Test single case while debugging
python tests/test_harness.py --url http://localhost:8000 --case 7
```

### Before Final Submission

```bash
# 1. Verify deployment is reachable
python tests/submission_checklist.py https://your-gridwise-api.onrender.com

# 2. Run full test suite against deployed URL
python tests/run_regression.py --url https://your-gridwise-api.onrender.com --save-results

# 3. Verify from mobile data (not your dev network!)
# Use your phone's browser or hotspot to test the URL
```

## 📱 Mobile Verification (Critical!)

The submission checklist warns about this - you MUST verify from outside your network:

```bash
# Option 1: Use mobile hotspot
# Connect laptop to phone's hotspot, then:
python tests/submission_checklist.py https://your-api-url.com

# Option 2: Use phone browser
# Visit: https://your-api-url.com/health
# Should see: {"status": "ok"}

# Option 3: Ask teammate on different network
# Have them run the submission checklist
```

## 🔍 What Each Script Does

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `test_harness.py` | Run public test cases | After implementing features |
| `run_regression.py` | Full suite (public + custom) | After merges, before submission |
| `submission_checklist.py` | Verify deployment readiness | Before final submission |

## 📊 Understanding Test Output

### ✅ Good Output
```
✓ energy_balance: PASSED
✓ battery_bounds: PASSED
✓ battery_rate_limits: PASSED
✓ end_of_day_neutrality: PASSED
✓ totals_recomputation: PASSED

✓ TEST PASSED
Total cost: 1234.56 BDT
```

### ❌ Failed Output
```
✗ energy_balance: FAILED
  - Hour 15: Energy balance violated. Supply (75.00) != Consumption (73.50)
  
✗ directive_enforcement: FAILED
  - Note 0 (solar_reduction): Hour 13: Solar used exceeds reduced cap

✗ TEST FAILED
```

## 🐛 Common Failures and Fixes

### "Energy balance violated"
**Who fixes**: Mahin (Optimizer owner)
- Problem: `grid + solar + discharge ≠ demand + charge`
- Check: LP constraints in optimizer

### "Directive not enforced"
**Who fixes**: 
- If LLM didn't extract: Asif (LLM Interpreter)
- If optimizer ignored: Mahin (Optimizer)
- Check: Guardrail validator output

### "End-of-day neutrality failed"
**Who fixes**: Mahin (Optimizer owner)
- Problem: Battery energy at hour 23 ≠ initial energy
- Check: LP constraint for battery energy equality

### "Connection refused"
**Who fixes**: Tarek (API/Deploy owner)
- Problem: Server not running or wrong URL
- Check: Health endpoint first

## 📝 Integration with Team

### After Asif (LLM) makes changes:
```bash
# Test directive interpretation
python tests/test_harness.py --url http://localhost:8000 --case 1
python tests/test_harness.py --url http://localhost:8000 --case 7  # Combined directives
```

### After Mahin (Optimizer) makes changes:
```bash
# Test constraint satisfaction
python tests/run_regression.py --url http://localhost:8000
```

### After Tarek (API) makes changes:
```bash
# Test API layer
python tests/submission_checklist.py http://localhost:8000
python tests/test_harness.py --url http://localhost:8000 --case 1
```

## ⏰ Timeline During Hackathon

| Time | Action |
|------|--------|
| 0:20 | Test harness ready, start testing as others build |
| 1:00 | First integration test - basic scenario |
| 1:30 | Test all public cases |
| 2:00 | Test custom scenarios (paraphrases) |
| 2:30 | Full regression suite |
| 3:00 | Submission checklist |
| 3:15 | Final verification from mobile |
| 3:25 | Submit! |

## 🎯 Success Criteria

Before you tell the team "We're ready":
- [ ] All 10 public tests pass
- [ ] At least 12/15 custom scenarios pass
- [ ] Submission checklist shows all green
- [ ] Health endpoint verified from mobile/external network
- [ ] Response times < 5 seconds for typical requests

## 💡 Pro Tips

1. **Save test results**: Use `--output results.json` to track progress
2. **Test early**: Don't wait for "complete" - test each component ASAP
3. **Custom scenarios matter**: Hidden cases will use paraphrased notes
4. **Trust the validators**: If test says it passed, it's judge-ready
5. **External network critical**: Judge will access from outside - verify this!

## 🚨 Emergency Fallback

If tests keep failing at 2:30 and you're running out of time:

```bash
# Test ONLY the essentials
python tests/test_harness.py --url http://localhost:8000 --case 1 --case 6

# If those pass, you have a minimal viable solution
# Focus on deployment rather than perfect optimization
```

## 📞 Quick Commands Reference

```bash
# Local development
python tests/test_harness.py --url http://localhost:8000

# Single test debug
python tests/test_harness.py --url http://localhost:8000 --case 3

# Full regression
python tests/run_regression.py --url http://localhost:8000

# Pre-submission
python tests/submission_checklist.py https://your-url.com

# Save results
python tests/run_regression.py --url http://localhost:8000 --save-results

# CI format output
python tests/run_regression.py --url http://localhost:8000 --ci-format github
```

Good luck! 🎉
