
# Creates cooking scenarios, runs the CSP solver on them and prints the
# schedule: start/finish times, burner and pan for each dish and when each 
# pan is being cleaned.

import io
import contextlib
from csp_solver import solve_cooking_schedule


# Scenarios 
# each dish: (name, cooking time, serve time)

scenarios = {
    "small_dinner": {
        "name": "Small dinner",
        "burners": 2, "pans": 2, "clean_time": 3,
        "dishes": [("Rice", 20, 30), ("Curry", 25, 30),
                   ("Vegetables", 10, 30), ("Omelette", 5, 35)],
    },
    "family_meal": {
        "name": "Family meal",
        "burners": 3, "pans": 3, "clean_time": 4,
        "dishes": [("Pasta", 12, 40), ("Sauce", 20, 40), ("Soup", 25, 30),
                   ("Garlic Bread", 8, 40), ("Stir Fry", 10, 45), ("Pancakes", 15, 60)],
    },
    "pan_bottleneck": {
        "name": "Pan bottleneck (more burners than pans)",
        "burners": 4, "pans": 2, "clean_time": 5,
        "dishes": [("Eggs", 6, 20), ("Bacon", 10, 20), ("Hash Browns", 12, 25),
                   ("Beans", 8, 25), ("Tomatoes", 5, 30)],
    },
    "big_order": {
        "name": "Big order",
        "burners": 4, "pans": 4, "clean_time": 3,
        "dishes": [("Fried Rice", 10, 25), ("Noodles", 8, 25), ("Broth", 30, 35),
                   ("Steak", 12, 30), ("Salmon", 10, 40), ("Stir Fry", 7, 40),
                   ("Dumplings", 15, 45), ("Mushrooms", 6, 45)],
    },
}


# Running the solver

def get_schedule(scenario):
    dishes = [{"id": name, "duration": time} for name, time, serve in scenario["dishes"]]

    #hiding the solver output
    with contextlib.redirect_stdout(io.StringIO()):
        result = solve_cooking_schedule(dishes, scenario["burners"],
                                        scenario["pans"], scenario["clean_time"])
    if result is None:
        return None

    #the solver only limits how many dishes cook at once so we give each dish the first burner that is free
    burner_free_at = [0] * scenario["burners"]
    schedule = []
    for item in sorted(result, key=lambda x: x["Start"]):
        for b in range(scenario["burners"]):
            if burner_free_at[b] <= item["Start"]:
                burner_free_at[b] = item["End"]
                break
        schedule.append({"dish": item["Dish"], "start": item["Start"], "end": item["End"],
                         "burner": b + 1, "pan": item["Pan"] + 1})
    return schedule


# Printing 

def print_schedule(scenario, schedule):
    serve = {name: s for name, time, s in scenario["dishes"]}

    print("\n=== " + scenario["name"] + " ===")
    print(f"{scenario['burners']} burners, {scenario['pans']} pans, "
          f"{scenario['clean_time']} min to clean a pan\n")

    print(f"{'Dish':<14}{'Burner':<8}{'Pan':<6}{'Start':<7}{'Finish':<8}{'Serve':<7}Status")
    for d in schedule:
        wait = serve[d["dish"]] - d["end"]
        if wait > 0:
            status = f"waits {wait} min"
        elif wait < 0:
            status = f"{-wait} min late"
        else:
            status = "on time"
        print(f"{d['dish']:<14}{d['burner']:<8}{d['pan']:<6}{d['start']:<7}"
              f"{d['end']:<8}{serve[d['dish']]:<7}{status}")

    print("\nPan cleaning:")
    for d in sorted(schedule, key=lambda x: (x["pan"], x["end"])):
        print(f"  Pan {d['pan']}: {d['end']} - {d['end'] + scenario['clean_time']} min "
              f"(after {d['dish']})")


def print_timeline(scenario, schedule, step=5):
    # shows what is happening in the kitchen every few minutes
    print("\nTimeline:")
    last = max(d["end"] for d in schedule) + scenario["clean_time"]
    for t in range(0, last + 1, step):
        cooking = [d["dish"] for d in schedule if d["start"] <= t < d["end"]]
        cleaning = [f"Pan {d['pan']}" for d in schedule
                    if d["end"] <= t < d["end"] + scenario["clean_time"]]
        print(f"  t={t:<3} cooking: {', '.join(cooking) or '-':<35} "
              f"cleaning: {', '.join(cleaning) or '-'}")


if __name__ == "__main__":
    for scenario in scenarios.values():
        schedule = get_schedule(scenario)
        if schedule is None:
            print("No schedule found for", scenario["name"])
            continue
        print_schedule(scenario, schedule)
        print_timeline(scenario, schedule)
