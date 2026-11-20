# Integration notes (Member 5)

What was changed in each module during integration, and why.

## Member 1 + 2: `csp_solver.py`
- Used **Revised_csp_solver.py** as the single solver (three versions existed before).
- CSV loader: same header-as-ID idea (`Dish_Name`, `Duration_Mins`), plus an optional **`Serve_Time`** column.
- **New stage 2 objective:** keep the best makespan, then minimise `2*late + wait`.
  - Why: the old version optimised makespan only, so the CSP lost to the greedy baseline on avg_wait in every scenario (e.g. small_dinner 12.5 vs 4.25).
  - Stage 2 searches every schedule with the optimal makespan, and that set includes the baseline's schedule whenever the baseline's makespan is equal. So the CSP's weighted delay can't be worse than the baseline's in those cases.
- `random_seed = 0`, `num_workers = 1` (reproducible), plus a check for duplicate dish names.
- `mode="makespan"` gives back the old behaviour.

## Member 2: `optimisation.py` (renamed from Optimization.py)
- Added `serving_metrics()`: per-dish wait and lateness against each dish's own serve time.
- Ranking now uses `2*late + wait` when serve times exist (otherwise the old common-deadline delay).
- Fix: pan utilisation could exceed 100% (cleaning after the end was counted). It is now capped at the serving time.

## Member 3: `simulation.py`, `visualisation.py`
- `get_schedule()` now reads the revised solver's output (`"candidates"`, `"B1"`/`"P1"` labels).
- New helpers: `scenario_to_dishes()` and `to_display_format()`, so every module uses one format.
- The scenarios dict is now the **single source of truth** (testing.py uses it too).
- Gantt: every burner/pan row is shown (empty B3/B4 rows were squashed before) and a ▼ marks each serve time.

## Member 4: `testing.py`, `baseline.py`
- `baseline.py` is unchanged.
- `testing.py` now imports `csp_solver` (not `Revised_csp_solver`) and uses the scenarios from simulation.py.
  - Note: family_meal now includes Pancakes (it was missing in testing.py's copy).
- Each method runs **10 times**, and the execution time is reported as **mean ± std** (the guidelines ask for repeated runs and summary statistics).
- avg_wait and max_late were added to the CSV and plots.
- **The experiments must be re-run** (`python main.py --experiments`), because the solver changed.
