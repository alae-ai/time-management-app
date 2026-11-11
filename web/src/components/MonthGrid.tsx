import { isSameMonth, dayNumber, dayLabel, toIso, weekdayLabels } from "../date";
import type { Block, FilterMode, Settings, Task } from "../types";

type Props = {
  month: Date;
  days: Date[];
  today: string;
  selected: string;
  tasks: Task[];
  blocks: Block[];
  settings: Settings;
  filter: FilterMode;
  showDone: boolean;
  onSelect: (iso: string) => void;
  onEditTask: (task: Task) => void;
  onEditBlock: (block: Block) => void;
  onToggleTask: (task: Task) => void;
};

type DeadlineStatus = "upcoming" | "today" | "overdue" | "done";

export function MonthGrid({
  month,
  days,
  today,
  selected,
  tasks,
  blocks,
  settings,
  filter,
  showDone,
  onSelect,
  onEditTask,
  onEditBlock,
  onToggleTask,
}: Props) {
  const weekdays = weekdayLabels(settings.week_starts_on);
  const taskById = new Map(tasks.map((task) => [task.id, task]));

  return (
    <div className="calendar">
      <div className="weekdays">
        {weekdays.map((label) => (
          <div className="weekday" key={label}>
            {label}
          </div>
        ))}
      </div>
      <div className="month-grid">
        {days.map((date) => {
          const iso = toIso(date);
          const inMonth = isSameMonth(date, month);
          const taskChips = tasks.filter((task) => task.deadline === iso);
          const allDue = taskChips;
          const openDue = allDue.filter((task) => !task.done);
          let deadlineStatus: DeadlineStatus | null = null;
          if (allDue.length > 0) {
            if (openDue.length === 0) {
              deadlineStatus = "done";
            } else if (iso < today) {
              deadlineStatus = "overdue";
            } else if (iso === today) {
              deadlineStatus = "today";
            } else {
              deadlineStatus = "upcoming";
            }
          }

          const visibleTasks =
            filter === "appointments"
              ? []
              : taskChips.filter((task) => showDone || !task.done);

          const visibleBlocks = blocks
            .filter((block) => block.date === iso)
            .filter((block) =>
              filter === "tasks"
                ? block.kind === "session"
                : filter === "appointments"
                  ? block.kind === "appointment"
                  : true,
            )
            .filter((block) => {
              if (showDone) {
                return true;
              }
              const task = block.task_id ? taskById.get(block.task_id) : undefined;
              return !task?.done;
            })
            .sort((left, right) => {
              if (left.all_day !== right.all_day) {
                return left.all_day ? -1 : 1;
              }
              return (left.start ?? "").localeCompare(right.start ?? "");
            });

          const total = visibleTasks.length + visibleBlocks.length;
          const shownTasks = visibleTasks.slice(0, 3);
          const remaining = 3 - shownTasks.length;
          const shownBlocks = visibleBlocks.slice(0, Math.max(remaining, 0));
          const hidden = total - shownTasks.length - shownBlocks.length;

          const classes = ["day"];
          if (!inMonth) {
            classes.push("outside");
          }
          if (iso === today) {
            classes.push("today");
          }
          if (iso === selected) {
            classes.push("selected");
          }
          if (deadlineStatus) {
            classes.push(`deadline-${deadlineStatus}`);
          }

          return (
            <div
              className={classes.join(" ")}
              key={iso}
              onClick={() => onSelect(iso)}
            >
              <div className="day-head">
                <button
                  type="button"
                  className="day-number"
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelect(iso);
                  }}
                  aria-label={`Select ${dayLabel(iso)}`}
                >
                  {dayNumber(iso)}
                </button>
                {allDue.length > 0 && openDue.length > 0 && (
                  <span className="day-due-count" title={`${openDue.length} due`}>
                    {openDue.length}
                  </span>
                )}
              </div>

              <div className="chips">
                {shownTasks.map((task) => (
                  <div
                    className={task.done ? "chip chip-task done" : "chip chip-task"}
                    key={task.id}
                  >
                    <input
                      type="checkbox"
                      className="chip-check"
                      checked={task.done}
                      onClick={(event) => event.stopPropagation()}
                      onChange={() => onToggleTask(task)}
                      aria-label={`Mark ${task.title} ${task.done ? "open" : "done"}`}
                    />
                    <button
                      type="button"
                      className="chip-text"
                      onClick={(event) => {
                        event.stopPropagation();
                        onEditTask(task);
                      }}
                      title={task.title}
                    >
                      {task.deadline_time && (
                        <span className="chip-time">{task.deadline_time}</span>
                      )}
                      <span className="chip-title">{task.title}</span>
                    </button>
                  </div>
                ))}

                {shownBlocks.map((block) => {
                  const task = block.task_id ? taskById.get(block.task_id) : undefined;
                  return (
                    <button
                      type="button"
                      className={`chip chip-block chip-${block.kind}${task?.done ? " done" : ""}`}
                      key={block.id}
                      onClick={(event) => {
                        event.stopPropagation();
                        onEditBlock(block);
                      }}
                      title={block.title}
                    >
                      <span className="chip-time">
                        {block.all_day ? "all day" : block.start}
                      </span>
                      <span className="chip-title">{block.title}</span>
                    </button>
                  );
                })}

                {hidden > 0 && (
                  <button
                    type="button"
                    className="chip-more"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(iso);
                    }}
                  >
                    +{hidden} more
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
