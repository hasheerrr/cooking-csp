"""
Integration tests (run from the repo root):
    python tests/test_pipeline.py

Checks, for every built-in scenario:
  1. the CSP returns at least one schedule
  2. every candidate passes the independent validator in optimisation.py
     (no burner clash, no pan clash incl. cleaning, valid intervals)
  3. CSP makespan <= greedy baseline makespan
  4. in "hot" mode, if the baseline has the same makespan, the CSP's
     weighted serving delay (2*late + wait) is <= the baseline's
Plus edge cases: invalid input is rejected, 1 burner / 1 pan still works.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csp_solver import solve_cooking_schedule
from baseline import baseline_greedy
from optimisation import validate_schedule, serving_metrics, LATE_WEIGHT
from simulation import scenarios, scenario_to_dishes


def weighted_delay(schedule, serve):
    items = [dict(x, serve=serve[x["dish"]]) for x in schedule]
    m = serving_metrics(items)
    return LATE_WEIGHT * m["total_late"] + m["total_wait"]


def test_scenarios():
    for key, sc in scenarios.items():
        dishes = scenario_to_dishes(sc)
        args = (dishes, sc["burners"], sc["pans"], sc["clean_time"])
        serve = {n: s for n, _, s in sc["dishes"]}

        result = solve_cooking_schedule(*args, candidate_count=3)
        assert result["candidates"], f"{key}: no schedule"
        for cand in result["candidates"]:
            assert validate_schedule(cand)
            assert len(cand) == len(dishes)

        csp = result["candidates"][0]
        base = baseline_greedy(*args)["candidates"][0]
        csp_mk = max(x["end"] for x in csp)
        base_mk = max(x["end"] for x in base)
        assert csp_mk <= base_mk, f"{key}: CSP makespan worse than baseline"

        if csp_mk == base_mk:
            assert weighted_delay(csp, serve) <= weighted_delay(base, serve), \
                f"{key}: CSP serving delay worse than baseline"
        print(f"PASS {key:<15} makespan CSP={csp_mk} baseline={base_mk} | "
              f"delay CSP={weighted_delay(csp, serve)} baseline={weighted_delay(base, serve)}")


def test_edge_cases():
    one = [{"id": "A", "duration": 5, "serve": 10}, {"id": "B", "duration": 3, "serve": 10}]
    r = solve_cooking_schedule(one, 1, 1, 2, candidate_count=1)
    s = r["candidates"][0]
    assert validate_schedule(s)
    assert max(x["end"] for x in s) == 5 + 2 + 3      # cook, clean, cook

    bad_inputs = [
        ([], 1, 1, 0),                                       # no dishes
        ([{"id": "A", "duration": 0}], 1, 1, 0),             # zero duration
        ([{"id": "A", "duration": 5}], 0, 1, 0),             # no burners
        ([{"id": "A", "duration": 5}], 1, 1, -1),            # negative cleaning
        ([{"id": "A", "duration": 5}, {"id": "A", "duration": 2}], 1, 1, 0),  # duplicate
    ]
    for args in bad_inputs:
        try:
            solve_cooking_schedule(*args)
            raise AssertionError(f"accepted bad input {args}")
        except ValueError:
            pass
    print("PASS edge cases")


if __name__ == "__main__":
    test_scenarios()
    test_edge_cases()
    print("\nAll tests passed.")
