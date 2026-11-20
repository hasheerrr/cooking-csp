"""
optimisation.py  -  Member 2: cooking time optimisation

Receives candidate schedules from csp_solver.py, evaluates their
performance (serving delay, makespan, burner/pan utilisation) and
selects the best schedule.
"""

LATE_WEIGHT = 2   # a late dish counts double compared with a cooling dish


def serving_metrics(schedule):
    """
    Per-dish serving quality (only for items that have a "serve" time).
      wait = serve - end   (dish finished early and is cooling)
      late = end - serve   (dish not ready at serving time)
    """
    timed = [item for item in schedule if item.get("serve") is not None]
    if not timed:
        return None
    waits = [max(0, item["serve"] - item["end"]) for item in timed]
    lates = [max(0, item["end"] - item["serve"]) for item in timed]
    return {
        "total_wait": sum(waits),
        "total_late": sum(lates),
        "average_wait": sum(waits) / len(timed),
        "average_late": sum(lates) / len(timed),
        "maximum_late": max(lates),
        "on_time_dishes": sum(1 for x in lates if x == 0),
    }


class ScheduleError(ValueError):
    pass

def validate_schedule(schedule):
    """Check burner and pan conflicts."""
    if not schedule:
        raise ScheduleError("Schedule is empty.")
    required = {
        "dish", "start", "end",
        "burner", "pan", "clean_time"
    }
    seen = set()

    for item in schedule:
        if not required.issubset(item):
            raise ScheduleError("Missing schedule information.")

        if item["dish"] in seen:
            raise ScheduleError("Duplicate dish.")

        seen.add(item["dish"])

        if item["start"] < 0 or item["end"] <= item["start"]:
            raise ScheduleError("Invalid cooking interval.")

        if item["clean_time"] < 0:
            raise ScheduleError("Invalid cleaning time.")

    # Check burner conflicts.
    for i, first in enumerate(schedule):
        for second in schedule[i + 1:]:

            if first["burner"] == second["burner"]:
                overlap = (
                    first["start"] < second["end"]
                    and second["start"] < first["end"]
                )

                if overlap:
                    raise ScheduleError(
                        f"Burner conflict: {first['dish']} "
                        f"and {second['dish']}"
                    )

            # Pan remains occupied until cleaning finishes.
            if first["pan"] == second["pan"]:
                first_end = first["end"] + first["clean_time"]
                second_end = second["end"] + second["clean_time"]

                overlap = (
                    first["start"] < second_end
                    and second["start"] < first_end
                )

                if overlap:
                    raise ScheduleError(
                        f"Pan cleaning conflict: {first['dish']} "
                        f"and {second['dish']}"
                    )

    return True

def evaluate_schedule(
    schedule,
    burner_count,
    pan_count,
    serving_time
):

    validate_schedule(schedule)

    makespan = max(item["end"] for item in schedule)

    # All candidates must use the same serving deadline.
    service = max(serving_time, makespan)

    delays = [
        service - item["end"]
        for item in schedule
    ]

    total_delay = sum(delays)
    average_delay = total_delay / len(schedule)
    maximum_delay = max(delays)

    cooking_time = sum(
        item["end"] - item["start"]
        for item in schedule
    )

    # Cleaning after the serving time is not counted, so utilisation
    # can never exceed 100%.
    pan_occupancy = sum(
        min(item["end"] + item["clean_time"], service) - item["start"]
        for item in schedule
    )

    burner_utilisation = (
        cooking_time / (burner_count * service)
        if service > 0 else 0
    )

    pan_utilisation = (
        pan_occupancy / (pan_count * service)
        if service > 0 else 0
    )

    metrics = {
        "makespan": makespan,
        "serving_time": service,
        "total_serving_delay": total_delay,
        "average_serving_delay": average_delay,
        "maximum_serving_delay": maximum_delay,
        "total_cooking_time": cooking_time,
        "total_pan_occupancy": pan_occupancy,
        "burner_utilisation": burner_utilisation * 100,
        "pan_utilisation": pan_utilisation * 100
    }

    # Per-dish serve times (if given) are a more realistic delay measure.
    per_dish = serving_metrics(schedule)
    if per_dish:
        metrics.update(per_dish)

    return metrics


def optimise_schedules(
    candidate_schedules,
    burner_count,
    pan_count,
    serving_time=None
):

    if not candidate_schedules:
        raise ScheduleError("No candidate schedules provided.")

    valid = []
    rejected = []

    # Validate candidates first.
    for number, schedule in enumerate(
        candidate_schedules, start=1
    ):
        try:
            validate_schedule(schedule)
            valid.append((number, schedule))

        except (ScheduleError, TypeError, KeyError) as error:
            rejected.append({
                "candidate": number,
                "reason": str(error)
            })

    if not valid:
        raise ScheduleError("No valid schedules found.")

    # Use one common deadline for every alternative.
    if serving_time is None:
        common_deadline = max(
            item["end"]
            for _, schedule in valid
            for item in schedule
        )
    else:
        common_deadline = max(
            serving_time,
            max(
                item["end"]
                for _, schedule in valid
                for item in schedule
            )
        )

    ranked = []

    for number, schedule in valid:

        metrics = evaluate_schedule(
            schedule,
            burner_count,
            pan_count,
            common_deadline
        )

        # Lower objective is better.
        if "total_late" in metrics:
            delay = LATE_WEIGHT * metrics["total_late"] + metrics["total_wait"]
        else:
            delay = metrics["total_serving_delay"]

        objective = (
            delay,
            metrics["makespan"],
            -metrics["burner_utilisation"],
            -metrics["pan_utilisation"]
        )

        ranked.append({
            "candidate": number,
            "schedule": schedule,
            "metrics": metrics,
            "objective": objective
        })

    ranked.sort(key=lambda item: item["objective"])

    best = ranked[0]

    return {
        "best_candidate": best["candidate"],
        "best_schedule": best["schedule"],
        "best_metrics": best["metrics"],
        "ranking": ranked,
        "rejected_candidates": rejected
    }


def optimise_solver_output(
    solver_result,
    burner_count,
    pan_count,
    serving_time=None
):
    """Connect directly to the output of csp_solver.py."""

    if not isinstance(solver_result, dict):
        raise ScheduleError("Invalid CSP solver output.")

    candidates = solver_result.get("candidates", [])

    return optimise_schedules(
        candidates,
        burner_count,
        pan_count,
        serving_time
    )


if __name__ == "__main__":

    # Example candidates for standalone testing.
    candidate_1 = [
        {
            "dish": "Rice",
            "start": 0,
            "end": 30,
            "burner": "B1",
            "pan": "P1",
            "clean_time": 5
        },
        {
            "dish": "Curry",
            "start": 0,
            "end": 25,
            "burner": "B2",
            "pan": "P2",
            "clean_time": 5
        }
    ]

    candidate_2 = [
        {
            "dish": "Rice",
            "start": 0,
            "end": 30,
            "burner": "B1",
            "pan": "P1",
            "clean_time": 5
        },
        {
            "dish": "Curry",
            "start": 5,
            "end": 30,
            "burner": "B2",
            "pan": "P2",
            "clean_time": 5
        }
    ]

    result = optimise_schedules(
        [candidate_1, candidate_2],
        burner_count=2,
        pan_count=2
    )

    print("\n=== OPTIMISATION RESULTS ===")
    print("Best candidate:", result["best_candidate"])

    print("\nPerformance measurements:")

    for name, value in result["best_metrics"].items():
        print(f"{name}: {value:.2f}")

    print("\nCandidate ranking:")

    for item in result["ranking"]:
        print(
            f"Candidate {item['candidate']}: "
            f"Total delay = "
            f"{item['metrics']['total_serving_delay']:.2f}"
        )
