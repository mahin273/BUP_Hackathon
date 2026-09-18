# Ramim's Test Harness & QA System - Complete Handoff

**Ownership**: Ramim (20% of project)  
**Status**: ✅ Complete and Ready  
**Created**: All files implemented step-by-step per design doc Section 5.4

---

## 📦 What You Got

A complete, production-ready test infrastructure for GridWise with:

### Core Files (Must Know)
1. **test_data.py** - 10 public test cases (one per directive type + combinations)
2. **custom_test_scenarios.py** - 15 additional scenarios for robustness testing
3. **validators.py** - 7 core validation functions for all constraints
4. **directive_validator.py** - Validates LLM interpretation correctness
5. **test_harness.py** - Main test runner (use this most)
6. **run_regression.py** - Full regression suite (run after merges)
7. **submission_checklist.py** - Pre-submission verification (run before submit)

### Documentation
- **README.md** - Full technical documentation
- **QUICK_START.md** - Your day-to-day command reference
- **RAMIM_HANDOFF.md** - This file

### Bonus
- **.github/workflows/regression-tests.yml.example** - CI/CD template

---

## 🎯 Your Responsibilities (From Design Doc 5.4)

### ✅ Implemented
- [x] Script that loops 10 public cases, POSTs each to localhost
- [x] Validates directive_interpretation (type/hours/values)
- [x] Validates energy balance every hour
- [x] Validates battery bounds + rate limits
- [x] Validates end-of-day battery == initial
- [x] Recomputes and validates totals
- [x] 3-5 custom scenarios with combined directives
- [x] Submission checklist (deploy URL verification)

### 🔄 Ongoing During Hackathon
- [ ] Run after every merge (regression gate for team)
- [ ] Test with paraphrased notes (hidden cases prep)
- [ ] Verify deploy URL from mobile data
- [ ] Own submission checklist before final submit

---

## 🚀 Daily Commands (Memorize These 3)

```bash
# 1. After any team member pushes code
python tests/run_regression.py --url http://localhost:8000

# 2. Testing specific functionality
python tests/test_harness.py --url http://localhost:8000 --case 7

# 3. Before submission (THE MOST IMPORTANT)
python tests/submission_checklist.py https://your-api.onrender.com
```

---

## 📊 What Each Validation Does

| Validation | What It Checks | Who Owns Fix If It Fails |
|------------|----------------|--------------------------|
| Energy Balance | `grid + solar + discharge = demand + charge` | Mahin (Optimizer) |
| Battery Bounds | `min ≤ battery ≤ capacity` | Mahin (Optimizer) |
| Rate Limits | Charge/discharge within limits | Mahin (Optimizer) |
| End-of-Day | Battery returns to initial energy | Mahin (Optimizer) |
| Continuity | Battery energy transitions correct | Mahin (Optimizer) |
| Totals | Sum matches reported totals | Mahin (Optimizer) |
| Directive Types | Valid directive_type values | Asif (LLM) or Mahin (Guardrails) |
| Note Coverage | Every note interpreted once | Asif (LLM) |
| Hours Arrays | Valid hours (0-23, unique) | Asif (LLM) or Mahin (Guardrails) |
| Enforcement | Directives actually applied | Mahin (Optimizer) |

---

## 🎬 Your Hackathon Timeline

### Hour 0-1: Setup
```bash
# Verify your test harness works
uvicorn app.main:app &
python tests/test_harness.py --url http://localhost:8000 --case 1
```

### Hour 1-2: Integration Testing
```bash
# As others build, test what exists
# Start with simple cases, work up to complex
python tests/test_harness.py --url http://localhost:8000
```

### Hour 2-2.5: Full Regression
```bash
# Everything should integrate now
python tests/run_regression.py --url http://localhost:8000 --save-results
```

### Hour 2.5-3: Custom Scenarios
```bash
# Test paraphrased notes (hidden cases will use these)
python tests/run_regression.py --url http://localhost:8000
# Focus on custom scenarios that fail
```

### Hour 3-3.5: Deployment & Submission
```bash
# Once deployed (Tarek handles this):
python tests/submission_checklist.py https://your-url.com

# Then full test against deployed:
python tests/run_regression.py --url https://your-url.com

# CRITICAL: Test from mobile data
# Use phone hotspot or teammate on different network
```

---

## 🚨 Critical Success Criteria

Before you give the green light to submit:

### Must Pass
- [ ] All 10 public tests pass
- [ ] Health endpoint responds from external network
- [ ] At least one test case from mobile data/external network
- [ ] No 500 errors on malformed input (should be 400/422)
- [ ] Response times < 10 seconds

### Should Pass (Fix if Time Permits)
- [ ] 12+ out of 15 custom scenarios pass
- [ ] Response times < 5 seconds
- [ ] HTTPS (not just HTTP)

---

## 🐛 Debugging Guide

### Test Fails: "Energy balance violated"
```bash
# This is Mahin's domain (optimizer)
# Show them the specific hour and values
python tests/test_harness.py --url http://localhost:8000 --case X --output debug.json
# Check debug.json for the exact values
```

### Test Fails: "Directive not enforced"
```bash
# Could be Asif (LLM didn't extract) OR Mahin (optimizer didn't apply)
# Check the directive_interpretation in response:
# - If directive_type is wrong → Asif
# - If directive_type correct but not applied → Mahin
```

### Test Fails: Connection/Network Issues
```bash
# This is Tarek's domain (API/deploy)
# First check if server is even running:
curl http://localhost:8000/health
```

### All Tests Suddenly Fail
```bash
# Someone broke something major
# Find the last commit that worked:
git log
git checkout <last-good-commit>
python tests/run_regression.py --url http://localhost:8000
# Then binary search to find the breaking commit
```

---

## 💡 Pro Tips from Design Doc

1. **Don't byte-compare outputs** - Section 11.4 says judge allows equivalent solutions
2. **Custom scenarios prepare for hidden cases** - Judge will use paraphrased notes
3. **Regression after EVERY merge** - You're the team's safety net
4. **Mobile verification is non-negotiable** - Judge accesses from outside
5. **Trust your validators** - If test passes, it's judge-ready

---

## 📁 File Reference

```
tests/
├── test_data.py                    # 10 public cases - know these well
├── custom_test_scenarios.py        # 15 custom cases - stress tests
├── validators.py                   # Core constraint checks
├── directive_validator.py          # Directive interpretation checks
├── test_harness.py                 # YOUR MAIN TOOL
├── run_regression.py               # Run after merges
├── submission_checklist.py         # Run before submit
├── README.md                       # Full docs
├── QUICK_START.md                  # Command cheat sheet
└── RAMIM_HANDOFF.md               # This file
```

---

## 🎓 Understanding the Scoring (From Design Doc Section 1)

The judge scores TWO independent things:

1. **Understanding** - Did LLM interpret notes correctly?
   - Your validators check: `directive_validator.py`
   
2. **Application** - Did optimizer apply constraints correctly?
   - Your validators check: `validators.py`

**Key insight**: "Correct extraction without correct downstream application does not pass."

Your test suite validates BOTH → If your tests pass, the solution is judge-ready.

---

## 🤝 Integration Points

### With Asif (LLM Interpreter)
- You validate his `directive_interpretation` output
- If your directive validator fails → his problem
- Test cases 1-6 test individual directive types

### With Mahin (Optimizer + Guardrails)
- You validate his constraint satisfaction
- If your constraint validators fail → his problem
- Test cases 7-10 test combined scenarios

### With Tarek (API + Deploy)
- You validate the full pipeline works
- If submission checklist fails → his problem
- Your tests are the acceptance criteria

---

## 🏁 Final Checklist (Print This!)

**30 minutes before deadline:**

```bash
# 1. Full regression local
python tests/run_regression.py --url http://localhost:8000

# 2. Submission checklist on deployed URL  
python tests/submission_checklist.py https://your-url.com

# 3. Quick test from mobile (YOUR PHONE!)
# Open browser: https://your-url.com/health

# 4. One full test from deployed URL
python tests/test_harness.py --url https://your-url.com --case 1

# 5. If all pass → SUBMIT!
```

---

## 📞 Questions?

- **"Which test should I run?"** → `test_harness.py` during dev, `run_regression.py` before merge
- **"Test failed, who fixes?"** → See table in "What Each Validation Does" section above
- **"How do I debug?"** → Use `--case N` to isolate, save with `--output debug.json`
- **"Is this test enough?"** → If all pass, yes. Judge uses same validation logic.
- **"Mobile test failed?"** → This is CRITICAL. Fix before submit. Might be firewall/DNS.

---

## 🎉 You're Ready!

You have everything needed to:
- ✅ Test all team member components
- ✅ Catch regressions immediately  
- ✅ Validate for hidden judge cases
- ✅ Verify deployment readiness
- ✅ Give confident "go/no-go" for submission

**Your test suite is the last line of defense before submission. Trust it.**

Good luck! 🚀
