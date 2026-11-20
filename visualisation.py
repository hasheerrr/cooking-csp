
# Top: dishes on each burner (label shows the serve time)
# Bottom: dishes in each pan (grey striped = pan being cleaned)

import os
import matplotlib.pyplot as plt
from simulation import scenarios, get_schedule


def plot_gantt(scenario, schedule, filename):
    serve = {name: s for name, time, s in scenario["dishes"]}
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(12, 6))

    for i, d in enumerate(schedule):
        colour = plt.cm.Set3(i % 12)
        length = d["end"] - d["start"]
        middle = d["start"] + length / 2

        # burner chart (label also shows when the dish should be served)
        label = f"{d['dish']} (serve {serve[d['dish']]})"
        ax1.barh(d["burner"], length, left=d["start"], color=colour, edgecolor="black")
        ax1.text(middle, d["burner"], label, ha="center", va="center", fontsize=8)

        # pan chart
        ax2.barh(d["pan"], length, left=d["start"], color=colour, edgecolor="black")
        ax2.text(middle, d["pan"], d["dish"], ha="center", va="center", fontsize=8)
        ax2.barh(d["pan"], scenario["clean_time"], left=d["end"],
                 color="lightgrey", hatch="//", edgecolor="grey")

    burners = range(1, scenario["burners"] + 1)
    pans = range(1, scenario["pans"] + 1)
    ax1.set_yticks(burners, [f"B{b}" for b in burners])
    ax2.set_yticks(pans, [f"P{p}" for p in pans])
    ax1.invert_yaxis()
    ax2.invert_yaxis()

    ax1.set_ylabel("Burner")
    ax2.set_ylabel("Pan")
    ax2.set_xlabel("Time (minutes)")
    ax1.set_title(scenario["name"])

    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()


if __name__ == "__main__":
    os.makedirs("charts", exist_ok=True)
    for key, scenario in scenarios.items():
        schedule = get_schedule(scenario)
        if schedule:
            plot_gantt(scenario, schedule, f"charts/gantt_{key}.png")
            print("Saved", f"charts/gantt_{key}.png")
