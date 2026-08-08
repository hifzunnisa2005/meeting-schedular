from datetime import datetime, timedelta, date, time
from typing import List, Tuple, Dict, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


class AdvancedAIMeetingScheduler:
    def __init__(self, work_start_hour: int = 9, work_end_hour: int = 17):
        self.work_start_hour = work_start_hour
        self.work_end_hour = work_end_hour

    def _get_working_window(self, date_obj: date) -> Tuple[datetime, datetime]:
        """Generates the daily working hours boundaries."""
        start = datetime(date_obj.year, date_obj.month, date_obj.day, self.work_start_hour, 0)
        end = datetime(date_obj.year, date_obj.month, date_obj.day, self.work_end_hour, 0)
        return start, end

    def calculate_free_intervals(
        self, busy_blocks: List[Tuple[datetime, datetime]], day_start: datetime, day_end: datetime
    ) -> List[Tuple[datetime, datetime]]:
        """Inverts busy blocks into available free intervals within working hours."""
        sorted_busy = sorted(busy_blocks, key=lambda x: x[0])
        free_intervals = []
        current_time = day_start

        for busy_start, busy_end in sorted_busy:
            if busy_start > current_time:
                free_intervals.append((current_time, min(busy_start, day_end)))
            current_time = max(current_time, busy_end)
            if current_time >= day_end:
                break

        if current_time < day_end:
            free_intervals.append((current_time, day_end))

        return free_intervals

    def intersect_free_intervals(
        self, list1: List[Tuple[datetime, datetime]], list2: List[Tuple[datetime, datetime]]
    ) -> List[Tuple[datetime, datetime]]:
        """Finds overlapping free time windows between two schedule lists."""
        intersection = []
        i, j = 0, 0

        while i < len(list1) and j < len(list2):
            start = max(list1[i][0], list2[j][0])
            end = min(list1[i][1], list2[j][1])

            if start < end:
                intersection.append((start, end))

            if list1[i][1] < list2[j][1]:
                i += 1
            else:
                j += 1

        return intersection

    def score_slot(self, slot_start: datetime, duration_minutes: int) -> float:
        """Higher level scoring model: penalizes edge hours and lunch times."""
        score = 100.0
        hour = slot_start.hour + (slot_start.minute / 60.0)

        # Penalize early mornings and late afternoons
        if hour < 10:
            score -= (10 - hour) * 15
        elif hour > 15:
            score -= (hour - 15) * 15

        # Avoid lunch hour (12:00 - 13:00)
        if 12.0 <= hour < 13.0:
            score -= 25.0

        return max(score, 0.0)

    def find_best_slots(
        self,
        attendee_busy_schedules: Dict[str, List[Tuple[datetime, datetime]]],
        target_date: date,
        duration_minutes: int,
        buffer_minutes: int = 15,
        top_n: int = 3
    ) -> Dict:
        """Finds top candidates and returns scheduling details along with mutual availability."""
        day_start, day_end = self._get_working_window(target_date)
        mutual_free = None

        for attendee, busy_blocks in attendee_busy_schedules.items():
            free = self.calculate_free_intervals(busy_blocks, day_start, day_end)
            if mutual_free is None:
                mutual_free = free
            else:
                mutual_free = self.intersect_free_intervals(mutual_free, free)

        if not mutual_free:
            return {"top_slots": [], "mutual_free": []}

        candidates = []
        for free_start, free_end in mutual_free:
            curr = free_start
            while curr + timedelta(minutes=duration_minutes) <= free_end:
                slot_end = curr + timedelta(minutes=duration_minutes)
                score = self.score_slot(curr, duration_minutes)

                candidates.append({
                    "start_dt": curr,
                    "end_dt": slot_end,
                    "start": curr.strftime("%H:%M"),
                    "end": slot_end.strftime("%H:%M"),
                    "score": round(score, 1)
                })
                curr += timedelta(minutes=15)

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return {
            "top_slots": candidates[:top_n],
            "mutual_free": mutual_free
        }


def visualize_schedules(
    schedules: Dict[str, List[Tuple[datetime, datetime]]],
    mutual_free: List[Tuple[datetime, datetime]],
    recommended_slots: List[Dict],
    target_date: date,
    work_start_hour: int = 9,
    work_end_hour: int = 17
):
    """Generates a Gantt-style schedule visualization comparing attendee schedules and AI recommendations."""
    fig, ax = plt.subplots(figsize=(12, 6))

    attendees = list(schedules.keys())
    y_labels = attendees + ["Mutual Free Time", "Recommended Slots"]
    y_positions = list(range(len(y_labels)))

    # Plot attendee busy blocks (Red)
    for i, attendee in enumerate(attendees):
        for start, end in schedules[attendee]:
            ax.barh(
                y=i,
                width=(end - start).total_seconds() / 3600,
                left=start,
                color="#e74c3c",
                edgecolor="black",
                height=0.4,
                label="Busy Block" if i == 0 and start == schedules[attendee][0][0] else ""
            )

    # Plot Mutual Free Intervals (Green)
    mutual_y = len(attendees)
    for start, end in mutual_free:
        ax.barh(
            y=mutual_y,
            width=(end - start).total_seconds() / 3600,
            left=start,
            color="#2ecc71",
            edgecolor="black",
            height=0.4,
            label="Mutual Free Window"
        )

    # Plot Top Recommended Slots (Blue)
    rec_y = len(attendees) + 1
    for slot in recommended_slots:
        start = slot["start_dt"]
        end = slot["end_dt"]
        ax.barh(
            y=rec_y,
            width=(end - start).total_seconds() / 3600,
            left=start,
            color="#3498db",
            edgecolor="black",
            height=0.4,
            label="Recommended Slot" if slot == recommended_slots[0] else ""
        )
        # Annotate score above the recommendation
        ax.text(
            start + (end - start) / 2,
            rec_y + 0.25,
            f"Score: {slot['score']}",
            ha="center",
            va="bottom",
            fontsize=9,
            weight="bold"
        )

    # Formatting axes and view bounds
    day_start = datetime(target_date.year, target_date.month, target_date.day, work_start_hour, 0)
    day_end = datetime(target_date.year, target_date.month, target_date.day, work_end_hour, 0)

    ax.set_xlim(day_start - timedelta(minutes=15), day_end + timedelta(minutes=15))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, fontsize=10, weight="bold")
    ax.set_xlabel("Time of Day", fontsize=11, weight="bold")
    ax.set_title(f"AI Meeting Scheduler - Schedule Breakdown ({target_date.strftime('%Y-%m-%d')})", fontsize=13, weight="bold")
    ax.grid(axis='x', linestyle='--', alpha=0.6)

    # Remove duplicate legend entries
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc='lower right')

    plt.tight_layout()
    plt.show()


# --- Execution Pipeline ---
if __name__ == "__main__":
    scheduler = AdvancedAIMeetingScheduler(work_start_hour=9, work_end_hour=17)
    today = datetime.now().date()

    # Simulated busy blocks for User A and User B
    busy_user_a = [
        (datetime(today.year, today.month, today.day, 9, 30), datetime(today.year, today.month, today.day, 10, 30)),
        (datetime(today.year, today.month, today.day, 12, 0), datetime(today.year, today.month, today.day, 13, 0))
    ]

    busy_user_b = [
        (datetime(today.year, today.month, today.day, 10, 0), datetime(today.year, today.month, today.day, 11, 30)),
        (datetime(today.year, today.month, today.day, 14, 30), datetime(today.year, today.month, today.day, 15, 30))
    ]

    schedules = {"User A": busy_user_a, "User B": busy_user_b}

    # Find candidate slots
    result = scheduler.find_best_slots(
        attendee_busy_schedules=schedules,
        target_date=today,
        duration_minutes=45
    )

    print("Top Recommended Meeting Slots:")
    for slot in result["top_slots"]:
        print(f"Time: {slot['start']} - {slot['end']} | Score: {slot['score']}")

    # Render Visual Gantt Chart
    visualize_schedules(
        schedules=schedules,
        mutual_free=result["mutual_free"],
        recommended_slots=result["top_slots"],
        target_date=today
    )