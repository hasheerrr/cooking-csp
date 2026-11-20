import copy
import os
import time
import traceback
import pandas as pd
import matplotlib.pyplot as plt

# Import the revised solver (make sure the file is named this or rename it to csp_solver)
from Revised_csp_solver import solve_cooking_schedule
from baseline import baseline_greedy

RESULTS_DIR = "results"

# ---------- Scenarios for the Sweep ----------
# We use the same tuple format as simulation.py: (name, cook_time, serve_time)
SCENARIOS = [
    {
        "name": "small_dinner", "burners": 2, "pans": 2, "clean_time": 3,
        "dishes": [("Rice", 20, 30), ("Curry", 25, 30), ("Vegetables", 10, 30), ("Omelette", 5, 35)]
    },
    {
        "name": "family_meal", "burners": 3, "pans": 3, "clean_time": 4,
        "dishes": [("Pasta", 12, 40), ("Sauce", 20, 40), ("Soup", 25, 30), ("Garlic Bread", 8, 40), ("Stir Fry", 10, 45)]
    },
    {
        "name": "pan_bottleneck", "burners": 4, "pans": 2, "clean_time": 5,
        "dishes": [("Eggs", 6, 20), ("Bacon", 10, 20), ("Hash Browns", 12, 25), ("Beans", 8, 25), ("Tomatoes", 5, 30)]
    },
    {
        "name": "big_order", "burners": 4, "pans": 4, "clean_time": 3,
        "dishes": [("Fried Rice", 10, 25), ("Noodles", 8, 25), ("Broth", 30, 35), ("Steak", 12, 30), 
                   ("Salmon", 10, 40), ("Stir Fry", 7, 40), ("Dumplings", 15, 45), ("Mushrooms", 6, 45)]
    }
]

# ---------- Metric Helpers ----------
def compute_metrics(candidate, scenario, exec_time):
    if not candidate:
        return None

    makespan = max(r["end"] for r in candidate)
    total_cook = sum(r["end"] - r["start"] for r in candidate)

    serve_times = {name: s for name, _, s in scenario["dishes"]}
    late = [max(0, r["end"] - serve_times[r["dish"]]) for r in candidate]
    wait = [max(0, serve_times[r["dish"]] - r["end"]) for r in candidate]

    nb, npn, clean = scenario["burners"], scenario["pans"], scenario["clean_time"]

    pan_util = total_cook / (npn * makespan) if makespan else 0.0
    burner_util = total_cook / (nb * makespan) if makespan else 0.0

    return {
        "makespan": makespan,
        "total_cook": total_cook,
        "avg_late": sum(late) / len(late),
        "avg_wait": sum(wait) / len(wait),
        "pan_util": pan_util,
        "burner_util": burner_util,
        "exec_time_s": exec_time
    }

# ---------- Runners ----------
def run_sweep():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    rows = []

    for scenario in SCENARIOS:
        # Format dishes for the solver
        dishes = [{"id": name, "duration": t} for name, t, _ in scenario["dishes"]]

        # 1. Run CSP Solver
        t0 = time.perf_counter()
        try:
            csp_result = solve_cooking_schedule(
                dishes, scenario["burners"], scenario["pans"], 
                scenario["clean_time"], candidate_count=1, time_limit=5
            )
            # Grab the first (best) candidate
            csp_schedule = csp_result["candidates"][0] if csp_result["candidates"] else None
        except Exception:
            traceback.print_exc()
            csp_schedule = None
        csp_time = time.perf_counter() - t0

        # 2. Run Baseline
        t0 = time.perf_counter()
        try:
            base_result = baseline_greedy(dishes, scenario["burners"], scenario["pans"], scenario["clean_time"])
            base_schedule = base_result["candidates"][0]
        except Exception:
            traceback.print_exc()
            base_schedule = None
        base_time = time.perf_counter() - t0

        # 3. Collect Metrics
        for label, schedule, exec_t in [("CSP", csp_schedule, csp_time), ("Baseline", base_schedule, base_time)]:
            metrics = compute_metrics(schedule, scenario, exec_t)
            row = {"scenario": scenario["name"], "method": label}
            if metrics:
                row.update(metrics)
                row["feasible"] = True
            else:
                row["feasible"] = False
            rows.append(row)
            
            status = f"makespan={metrics['makespan']}" if metrics else "FAILED"
            print(f"{scenario['name']:<15} | {label:<8} | {status}")

    # Save to CSV
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS_DIR, "results.csv"), index=False)
    print(f"\nSaved {RESULTS_DIR}/results.csv")
    return df

# ---------- Plotting ----------
def plot_results(df):
    metrics = ["makespan", "avg_late", "pan_util", "exec_time_s"]
    for metric in metrics:
        sub = df[df["feasible"]]
        if sub.empty: continue
        
        fig, ax = plt.subplots(figsize=(10, 5))
        scenarios = sub["scenario"].unique()
        methods = sub["method"].unique()
        width = 0.8 / len(methods)
        
        for i, m in enumerate(methods):
            vals = [sub[(sub.scenario == s) & (sub.method == m)][metric].mean() for s in scenarios]
            xs = [j + i * width for j in range(len(scenarios))]
            ax.bar(xs, vals, width=width, label=m)
            
        ax.set_xticks([j + 0.4 - width / 2 for j in range(len(scenarios))])
        ax.set_xticklabels(scenarios, rotation=20)
        ax.set_ylabel(metric)
        ax.set_title(f"{metric}: CSP vs Baseline")
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(RESULTS_DIR, f"compare_{metric}.png"), dpi=150)
        plt.close()
    print(f"Saved comparison charts to {RESULTS_DIR}/")

if __name__ == "__main__":
    df = run_sweep()
    plot_results(df)