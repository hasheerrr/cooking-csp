"""
Baseline schedulers for comparison against the Revised CSP solver.
Returns a dictionary matching the Revised_csp_solver output format.
"""

def baseline_greedy(dishes, num_burners, num_pans, cleaning_time):
    # Sort dishes by duration (Longest Processing Time first)
    ordered = sorted(dishes, key=lambda d: -d["duration"])
    
    burner_free = [0] * num_burners
    pan_free = [0] * num_pans
    schedule = []

    for dish in ordered:
        # Find earliest free burner and pan
        b = min(range(num_burners), key=lambda i: burner_free[i])
        p = min(range(num_pans), key=lambda i: pan_free[i])

        start = max(burner_free[b], pan_free[p])
        end = start + dish["duration"]

        burner_free[b] = end
        # Pan is busy until cooking finishes + cleaning time
        pan_free[p] = end + cleaning_time 

        schedule.append({
            "dish": dish["id"],
            "start": start,
            "end": end,
            "burner": f"B{b + 1}",
            "pan": f"P{p + 1}",
            "clean_time": cleaning_time
        })

    schedule.sort(key=lambda x: (x["start"], x["dish"]))
    
    # We wrap the baseline in the exact same dict structure as the CSP solver
    makespan = max([item["end"] for item in schedule]) if schedule else 0
    
    return {
        "status": "OPTIMAL",
        "candidates": [schedule],
        "candidate_count": 1,
        "best_makespan": makespan
    }