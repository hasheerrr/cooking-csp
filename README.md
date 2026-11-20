# Cooking Schedule Optimisation as a CSP

CSCI218 Foundations of AI, Group Project (Topic 3), UOW Dubai, Autumn 2026

Plan **N dishes** on a **K-burner stove** with a **limited number of pans**.
Each dish needs a clean pan and cooks without interruption. A reused pan must be
cleaned first. The goal is to finish every dish, use burners and pans well, and
**serve every dish as hot as possible**.

---

## 1. Setup

```bash
git clone <repo-url>
cd cooking-csp
python -m venv venv
# Windows: venv\Scripts\activate     Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Requires Python 3.9+ and the packages in `requirements.txt` (OR-Tools, matplotlib, pandas).

## 2. Run

| Command | What it does |
|---|---|
| `python main.py` | Runs all 4 built-in scenarios: schedule, timeline, baseline check, Gantt charts |
| `python main.py --scenario small_dinner` | Runs one scenario |
| `python main.py --list` | Lists the scenarios |
| `python main.py --csv data/example_dishes.csv --burners 2 --pans 2 --clean 5` | Uses your own dishes |
| `python main.py --mode makespan` | Stage 1 only (no serve-time optimisation) |
| `python main.py --candidates 10` | Compares more candidate schedules |
| `python main.py --experiments` | Full CSP vs baseline tests → `results/` |
| `python tests/test_pipeline.py` | Correctness tests |

Gantt charts are saved in `charts/`, and experiment tables and graphs in `results/`.

### CSV input format
```
Dish_Name,Duration_Mins,Serve_Time
Rice,20,30
Curry,25,30
```
`Serve_Time` (minutes from the start) is optional. Without it, only the makespan is optimised.

## 3. How it works

```
 input (scenario / CSV)
        │
        ▼
 csp_solver.py      CSP model → several valid candidate schedules
        │
        ▼
 optimisation.py    validate + score + rank → best schedule
        │
        ├──► simulation.py     table, pan-cleaning times, timeline
        ├──► visualisation.py  Gantt chart (burners + pans)
        └──► baseline.py       greedy schedule for comparison
                                (testing.py runs the full comparison)
```

### CSP model (`csp_solver.py`)
| Part | Definition |
|---|---|
| Variables | `start[d]`, `end[d]`, `usePan[d][p]` |
| Domains | start/end ∈ [0, horizon], usePan ∈ {0,1} |
| C1 uninterrupted cooking | `end[d] = start[d] + duration[d]` |
| C2 one clean pan | `Σp usePan[d][p] = 1` |
| C3 burner capacity | at most K dishes cooking at any time (`AddCumulative`) |
| C4 pan reuse + cleaning | each pan is busy for `duration + clean_time`, with no overlap (`AddNoOverlap`) |

**Optimisation (two-stage, lexicographic):**
1. Minimise the **makespan** (time until the last dish is ready).
2. Keep that makespan, then minimise `2 × lateness + waiting`.
   - waiting = serve − end (the dish is cooling)
   - lateness = end − serve (the dish is not ready in time)

Solver: Google OR-Tools CP-SAT, `random_seed = 0`, 1 worker (same result every run).

### Baseline (`baseline.py`)
Greedy LPT (Longest Processing Time first): sorts dishes longest first, then
puts each on the earliest free burner and pan.

## 4. Files and owners

| File | Owner | Role |
|---|---|---|
| `csp_solver.py` | Member 1 (+ Member 2) | CSP model, candidate generation |
| `optimisation.py` | Member 2 | Validation, metrics, ranking |
| `simulation.py` | Member 3 | Scenarios, schedule table, timeline |
| `visualisation.py` | Member 3 | Gantt charts |
| `baseline.py`, `testing.py` | Member 4 | Baseline and experiments |
| `main.py`, `README.md`, `data/`, `tests/` | Member 5 | Integration, docs, report |

## 5. Folder structure
```
cooking-csp/
├── main.py
├── csp_solver.py
├── optimisation.py
├── simulation.py
├── visualisation.py
├── baseline.py
├── testing.py
├── requirements.txt
├── data/          example CSV inputs (one per scenario + example_dishes.csv)
├── tests/         test_pipeline.py
├── charts/        Gantt charts (generated)
└── results/       results.csv + comparison graphs (generated)
```
