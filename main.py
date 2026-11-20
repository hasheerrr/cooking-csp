"""
main.py  -  Member 5: integration / entry point

Pipeline for one kitchen scenario:

    input (built-in scenario or CSV)
      -> csp_solver      : CSP model, generates valid candidate schedules
      -> optimisation    : validates + ranks candidates, picks the best
      -> simulation      : prints the schedule, pan cleaning and timeline
      -> visualisation   : saves a Gantt chart (burners + pans)
      -> baseline        : greedy schedule for a quick side-by-side check

Examples
    python main.py                                  # all 4 built-in scenarios
    python main.py --scenario small_dinner          # one scenario
    python main.py --csv data/example_dishes.csv --burners 2 --pans 2 --clean 5
    python main.py --mode makespan                  # stage 1 only (no serve-time stage)
    python main.py --experiments                    # full CSP vs baseline tests
    python main.py --list                           # list scenarios
"""

import argparse
import os
import sys

from csp_solver import solve_cooking_schedule, load_dishes_from_csv
from optimisation import optimise_solver_output, serving_metrics, ScheduleError
from simulation import scenarios, scenario_to_dishes, to_display_format, \
    print_schedule, print_timeline
from visualisation import plot_gantt
from baseline import baseline_greedy

CHART_DIR = "charts"


def line(char="=", width=70):
    print(char * width)


def compare_with_baseline(scenario, best_schedule):
    """Print CSP vs greedy baseline on the key metrics."""
    dishes = scenario_to_dishes(scenario)
    base = baseline_greedy(dishes, scenario["burners"], scenario["pans"],
                           scenario["clean_time"])["candidates"][0]
    serve = {name: s for name, _, s in scenario["dishes"]}
    for item in base:
        item["serve"] = serve[item["dish"]]

    rows = []
    for label, sched in (("CSP", best_schedule), ("Baseline", base)):
        m = serving_metrics(sched) or {}
        rows.append((label, max(x["end"] for x in sched),
                     m.get("average_wait"), m.get("average_late")))

    print("\nCSP vs greedy baseline:")
    print(f"  {'Method':<10}{'Makespan':>10}{'Avg wait':>10}{'Avg late':>10}")
    for label, mk, w, l in rows:
        w_txt = "-" if w is None else f"{w:.2f}"
        l_txt = "-" if l is None else f"{l:.2f}"
        print(f"  {label:<10}{mk:>10}{w_txt:>10}{l_txt:>10}")


def run_scenario(key, scenario, candidates=5, mode="hot", charts=True):
    """Full pipeline for one scenario. Returns the best schedule or None."""
    line()
    print(f"SCENARIO: {scenario['name']}")
    line()

    # 1. CSP solver -> candidate schedules
    result = solve_cooking_schedule(
        scenario_to_dishes(scenario),
        scenario["burners"], scenario["pans"], scenario["clean_time"],
        candidate_count=candidates, mode=mode,
    )
    print(f"Solver status: {result['status']} | mode: {result['mode']} | "
          f"candidates: {result['candidate_count']} | "
          f"best makespan: {result['best_makespan']}")

    if not result["candidates"]:
        print("No feasible schedule found with the given constraints.")
        return None

    # 2. Optimisation -> validate, rank, pick best
    try:
        best = optimise_solver_output(result, scenario["burners"], scenario["pans"])
    except ScheduleError as error:
        print("Optimisation failed:", error)
        return None

    m = best["best_metrics"]
    print(f"Best candidate: #{best['best_candidate']} | "
          f"burner use {m['burner_utilisation']:.1f}% | "
          f"pan use {m['pan_utilisation']:.1f}%")
    if best["rejected_candidates"]:
        print("Rejected:", best["rejected_candidates"])

    schedule = to_display_format(best["best_schedule"])

    # 3. Simulation output
    print_schedule(scenario, schedule)
    print_timeline(scenario, schedule)

    # 4. Baseline comparison
    if all(s is not None for _, _, s in scenario["dishes"]):
        compare_with_baseline(scenario, best["best_schedule"])

    # 5. Gantt chart
    if charts:
        os.makedirs(CHART_DIR, exist_ok=True)
        path = os.path.join(CHART_DIR, f"gantt_{key}.png")
        plot_gantt(scenario, schedule, path)
        print(f"\nGantt chart saved: {path}")

    return schedule


def scenario_from_csv(path, burners, pans, clean):
    dishes = load_dishes_from_csv(path)
    if not dishes:
        sys.exit(f"No dishes loaded from {path}.")
    name = os.path.splitext(os.path.basename(path))[0]
    return name, {
        "name": f"CSV input: {name}",
        "burners": burners, "pans": pans, "clean_time": clean,
        "dishes": [(d["id"], d["duration"], d.get("serve")) for d in dishes],
    }


def parse_args():
    p = argparse.ArgumentParser(description="Cooking schedule optimisation as a CSP")
    p.add_argument("--scenario", choices=list(scenarios), help="run one built-in scenario")
    p.add_argument("--csv", help="CSV with Dish_Name,Duration_Mins[,Serve_Time]")
    p.add_argument("--burners", type=int, default=2, help="burners (CSV mode)")
    p.add_argument("--pans", type=int, default=2, help="pans (CSV mode)")
    p.add_argument("--clean", type=int, default=5, help="pan cleaning minutes (CSV mode)")
    p.add_argument("--candidates", type=int, default=5, help="candidate schedules to compare")
    p.add_argument("--mode", choices=["hot", "makespan"], default="hot",
                   help="hot = makespan then serve-time stage; makespan = stage 1 only")
    p.add_argument("--no-charts", action="store_true", help="skip Gantt charts")
    p.add_argument("--experiments", action="store_true", help="run testing.py sweep")
    p.add_argument("--list", action="store_true", help="list built-in scenarios")
    return p.parse_args()


def main():
    args = parse_args()

    if args.list:
        for key, s in scenarios.items():
            print(f"{key:<16} {len(s['dishes'])} dishes, {s['burners']} burners, "
                  f"{s['pans']} pans, clean {s['clean_time']} min")
        return

    if args.experiments:
        import testing          # imported here: needs pandas
        testing.main()
        return

    if args.csv:
        jobs = [scenario_from_csv(args.csv, args.burners, args.pans, args.clean)]
    elif args.scenario:
        jobs = [(args.scenario, scenarios[args.scenario])]
    else:
        jobs = list(scenarios.items())

    for key, scenario in jobs:
        run_scenario(key, scenario, args.candidates, args.mode, not args.no_charts)
        print()


if __name__ == "__main__":
    main()
