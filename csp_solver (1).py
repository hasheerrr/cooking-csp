"""
csp_solver.py  -  Member 1 (CSP model) + Member 2 (candidate generation)

Models cooking as a Constraint Satisfaction Problem and solves it with
Google OR-Tools CP-SAT.

CSP formulation
---------------
Variables : start[d]          start minute of dish d
            end[d]            end minute of dish d
            usePan[d][p]      1 if dish d is cooked in pan p
Domains   : start, end in [0, horizon]; usePan in {0, 1}
Constraints:
  1. end[d] = start[d] + duration[d]          (uninterrupted cooking)
  2. sum_p usePan[d][p] = 1                   (exactly one clean pan per dish)
  3. at most K dishes cook at the same time   (burner capacity, Cumulative)
  4. a pan is busy for duration + cleaning    (NoOverlap per pan)

Optimisation (lexicographic, two stages)
  Stage 1: minimise makespan (finish everything as early as possible).
  Stage 2: keep makespan = best value from stage 1, then minimise
           late_weight * total_lateness + total_waiting
           where waiting = serve - end (food cools) and
                 lateness = end - serve (dish not ready on time).
  Stage 2 runs only when dishes have serve times ("hot" mode).
"""

import csv
from ortools.sat.python import cp_model


# ---------------------------------------------------------------- input data

def load_dishes_from_csv(file_path):
    """
    Load dishes from a CSV file. The column headers are used as ID tags:
        Dish_Name, Duration_Mins            (required)
        Serve_Time                          (optional, minutes from start)
    Returns a list of dicts, or None if the file is missing.
    """
    dishes = []
    try:
        with open(file_path, mode="r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
                dish = {
                    "id": row["Dish_Name"],
                    "duration": int(row["Duration_Mins"]),
                }
                if row.get("Serve_Time"):
                    dish["serve"] = int(row["Serve_Time"])
                dishes.append(dish)
        return dishes
    except FileNotFoundError:
        print(f"Could not find {file_path}. Using default dishes.")
        return None


def get_default_dishes():
    """Default cooking scenario (Member 1's test data, with serve times)."""
    return [
        {"id": "Omelette", "duration": 3, "serve": 45},
        {"id": "Pasta", "duration": 15, "serve": 40},
        {"id": "Steak", "duration": 12, "serve": 40},
        {"id": "Baked Potatoes", "duration": 40, "serve": 45},
        {"id": "Sauce", "duration": 10, "serve": 40},
    ]


# ---------------------------------------------------------- burner numbering

def assign_burners(schedule, num_burners):
    """
    The CSP only limits HOW MANY dishes cook at once (<= K).
    This gives each dish a concrete burner: a burner is reused only
    after its previous dish has finished (greedy interval colouring,
    always succeeds when the Cumulative constraint holds).
    """
    active = []
    result = []

    for dish in sorted(schedule, key=lambda x: (x["start"], x["end"])):
        start = dish["start"]
        active = [(end, burner) for end, burner in active if end > start]
        used = {burner for _, burner in active}
        available = [b for b in range(num_burners) if b not in used]

        if not available:
            raise RuntimeError("No available burner for a valid CSP schedule.")

        burner = available[0]
        item = dict(dish)
        item["burner"] = f"B{burner + 1}"
        active.append((dish["end"], burner))
        result.append(item)

    return result


# --------------------------------------------------------------- the model

def _check_inputs(dishes, num_burners, num_pans, cleaning_time, candidate_count):
    if not dishes:
        raise ValueError("At least one dish is required.")
    if num_burners < 1 or num_pans < 1:
        raise ValueError("At least one burner and one pan are required.")
    if cleaning_time < 0:
        raise ValueError("Cleaning time cannot be negative.")
    if candidate_count < 1:
        raise ValueError("candidate_count must be at least 1.")
    names = [d["id"] for d in dishes]
    if len(names) != len(set(names)):
        raise ValueError("Dish names must be unique.")
    for dish in dishes:
        if dish["duration"] <= 0:
            raise ValueError("Cooking durations must be positive.")


def _build_model(dishes, num_burners, num_pans, cleaning_time, horizon):
    """Create variables and hard constraints. Returns (model, variables)."""
    model = cp_model.CpModel()

    starts, ends, cooking = {}, {}, []
    pan_intervals = {p: [] for p in range(num_pans)}
    pan_assignments = {}

    for dish in dishes:
        d_id = dish["id"]
        dur = dish["duration"]

        # Constraint 1: uninterrupted cooking (fixed-length interval)
        start = model.NewIntVar(0, horizon, f"start_{d_id}")
        end = model.NewIntVar(0, horizon, f"end_{d_id}")
        cooking.append(model.NewIntervalVar(start, dur, end, f"cook_{d_id}"))
        starts[d_id], ends[d_id] = start, end

        # Constraint 2: exactly one pan; pan busy for cooking + cleaning
        presences = []
        for p in range(num_pans):
            used = model.NewBoolVar(f"use_{d_id}_pan{p}")
            presences.append(used)
            pan_assignments[(d_id, p)] = used

            pan_end = model.NewIntVar(0, horizon, f"pan_end_{d_id}_{p}")
            model.Add(pan_end == start + dur + cleaning_time).OnlyEnforceIf(used)
            pan_intervals[p].append(model.NewOptionalIntervalVar(
                start, dur + cleaning_time, pan_end, used, f"pan_{d_id}_{p}"))

        model.AddExactlyOne(presences)

    # Constraint 3: burner capacity
    model.AddCumulative(cooking, [1] * len(dishes), num_burners)

    # Constraint 4: one dish per pan at a time (cleaning included)
    for p in range(num_pans):
        model.AddNoOverlap(pan_intervals[p])

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, list(ends.values()))

    variables = {
        "starts": starts,
        "ends": ends,
        "pans": pan_assignments,
        "makespan": makespan,
    }
    return model, variables


def _new_solver(time_limit):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 1      # deterministic
    solver.parameters.random_seed = 0      # same schedule every run
    return solver


def _read_schedule(solver, dishes, variables, num_pans, num_burners, cleaning_time):
    schedule = []
    for dish in dishes:
        d_id = dish["id"]
        pan = next(p for p in range(num_pans)
                   if solver.Value(variables["pans"][(d_id, p)]))
        item = {
            "dish": d_id,
            "start": solver.Value(variables["starts"][d_id]),
            "end": solver.Value(variables["ends"][d_id]),
            "pan": f"P{pan + 1}",
            "clean_time": cleaning_time,
        }
        if "serve" in dish:
            item["serve"] = dish["serve"]
        schedule.append(item)

    schedule = assign_burners(schedule, num_burners)
    schedule.sort(key=lambda x: (x["start"], x["dish"]))
    return schedule


# ------------------------------------------------------------ main function

def solve_cooking_schedule(
    dishes,
    num_burners,
    num_pans,
    cleaning_time,
    candidate_count=5,
    time_limit=10,
    mode="hot",
    late_weight=2,
):
    """
    Solve the cooking CSP and return several valid candidate schedules.

    mode = "makespan" : stage 1 only (original behaviour)
    mode = "hot"      : stage 1 + stage 2 (serve dishes as hot as possible)

    Returns a dict:
        status, candidates (list of schedules), candidate_count,
        best_makespan, mode
    Each schedule item: dish, start, end, burner, pan, clean_time (+ serve)
    """
    _check_inputs(dishes, num_burners, num_pans, cleaning_time, candidate_count)

    horizon = sum(d["duration"] + cleaning_time for d in dishes)
    has_serve = any("serve" in d for d in dishes)
    use_stage2 = (mode == "hot" and has_serve)

    # ---- Stage 1: minimise makespan
    model, v = _build_model(dishes, num_burners, num_pans, cleaning_time, horizon)
    model.Minimize(v["makespan"])
    solver = _new_solver(time_limit)
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": solver.StatusName(status), "candidates": [],
                "candidate_count": 0, "best_makespan": None, "mode": mode}

    best_makespan = int(solver.Value(v["makespan"]))

    # ---- Stage 2: same makespan, minimise lateness + waiting
    if use_stage2:
        stage1_values = {d["id"]: solver.Value(v["starts"][d["id"]]) for d in dishes}

        model, v = _build_model(dishes, num_burners, num_pans, cleaning_time, horizon)
        model.Add(v["makespan"] <= best_makespan)

        bound = horizon + max(d.get("serve", 0) for d in dishes)
        penalty_terms = []
        for dish in dishes:
            if "serve" not in dish:
                continue
            d_id, serve = dish["id"], dish["serve"]
            wait = model.NewIntVar(0, bound, f"wait_{d_id}")
            late = model.NewIntVar(0, bound, f"late_{d_id}")
            model.Add(wait >= serve - v["ends"][d_id])   # finished early -> cools
            model.Add(late >= v["ends"][d_id] - serve)   # finished after serve time
            penalty_terms.append(late_weight * late + wait)
            model.AddHint(v["starts"][d_id], stage1_values[d_id])

        model.Minimize(sum(penalty_terms))

    # ---- Generate candidates: re-solve, forbidding previous solutions
    decision_vars = list(v["starts"].values()) + list(v["pans"].values())
    candidates = []
    status_name = solver.StatusName(status)

    for _ in range(candidate_count):
        solver = _new_solver(time_limit)
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        if not candidates:
            status_name = solver.StatusName(status)

        candidates.append(_read_schedule(
            solver, dishes, v, num_pans, num_burners, cleaning_time))

        previous = [solver.Value(x) for x in decision_vars]
        model.AddForbiddenAssignments(decision_vars, [previous])

    return {
        "status": status_name,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "best_makespan": best_makespan,
        "mode": "hot" if use_stage2 else "makespan",
    }


if __name__ == "__main__":
    result = solve_cooking_schedule(get_default_dishes(), 2, 2, 5, candidate_count=3)
    print("Solver status:", result["status"])
    print("Best makespan:", result["best_makespan"])
    for n, schedule in enumerate(result["candidates"], start=1):
        print(f"\nCandidate {n}")
        for item in schedule:
            print(f"  {item['dish']:<15} {item['start']:>3}-{item['end']:<3} "
                  f"{item['burner']} {item['pan']}")
