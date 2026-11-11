import { dayLabel, durationLabel } from "../date";
import type { Block, FreeSlots, Task } from "../types";

type Props = {
  day: string;
  today: string;
  tasks: Task[];
  blocks: Block[];
  freeSlots: FreeSlots | null;
  slotsLoading: boolean;
  showDone: boolean;
  windowStart: string;
  windowEnd: string;
  onEditTask: (task: Task) => void;
  onEditBlock: (block: Block) => void;
  onToggleTask: (task: Task) => void;
  onCreateTask: () => void;
  onCreateAppointment: () => void;
  onCreateSession: () => void;
};

type TimelineItem =
  | { type: "block"; key: string; start: string; end: string; block: Block }
  | { type: "free"; key: string; start: string; end: string; minutes: number };

export function DayPanel({
  day,
  today,
  tasks,
  blocks,
  freeSlots,
  slotsLoading,
  showDone,
  windowStart,
  windowEnd,
  onEditTask,
  onEditBlock,
  onToggleTask,
  onCreateTask,
  onCreateAppointment,
  onCreateSession,
}: Props) {
  const dueTasks = tasks
    .filter((task) => task.deadline === day)
    .filter((task) => showDone || !task.done)
    .sort((left, right) =>
      (left.deadline_time ?? "99:99").localeCompare(right.deadline_time ?? "99:99"),
    );

  const taskById = new Map(tasks.map((task) => [task.id, task]));
  const visibleBlocks = blocks.filter((block) => {
    if (showDone) {
      return true;
    }
    const task = block.task_id ? taskById.get(block.task_id) : undefined;
    return !task?.done;
  });

  const allDayBlocks = visibleBlocks
    .filter((block) => block.all_day)
    .sort((left, right) => left.title.localeCompare(right.title));

  const timedBlocks = visibleBlocks
    .filter((block) => !block.all_day && block.start && block.end)
    .sort((left, right) => (left.start ?? "").localeCompare(right.start ?? ""));

  const slots = freeSlots?.slots ?? [];
  const allDayFree = slots.filter((slot) => slot.all_day);
  const timedFree = slots.filter((slot) => !slot.all_day);

  const timeline: TimelineItem[] = [
    ...timedBlocks.map<TimelineItem>((block) => ({
      type: "block",
      key: block.id,
      start: block.start ?? "",
      end: block.end ?? "",
      block,
    })),
    ...timedFree.map<TimelineItem>((slot) => ({
      type: "free",
      key: `free-${slot.start}-${slot.end}`,
      start: slot.start,
      end: slot.end,
      minutes: slot.minutes,
    })),
  ].sort((left, right) => left.start.localeCompare(right.start) || left.end.localeCompare(right.end));

  const isPastDay = day < today;
  const isEmpty =
    dueTasks.length === 0 &&
    allDayBlocks.length === 0 &&
    allDayFree.length === 0 &&
    timeline.length === 0;

  return (
    <section className="panel day-panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">{dayLabel(day)}</h2>
          {day === today && <span className="today-badge">Today</span>}
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCreateTask}>
            + Task
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCreateAppointment}>
            + Appointment
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCreateSession}>
            + Session
          </button>
        </div>
      </div>

      {dueTasks.length > 0 && (
        <div className="section">
          <h3 className="section-title">Due</h3>
          <div className="due-list">
            {dueTasks.map((task) => (
              <div className={task.done ? "due-row done" : "due-row"} key={task.id}>
                <input
                  type="checkbox"
                  checked={task.done}
                  onChange={() => onToggleTask(task)}
                  aria-label={`Mark ${task.title} ${task.done ? "open" : "done"}`}
                />
                <button
                  type="button"
                  className="due-main"
                  onClick={() => onEditTask(task)}
                >
                  <span className="due-title">{task.title}</span>
                  <span className="muted">
                    {task.deadline_time ? task.deadline_time : "end of day"}
                  </span>
                </button>
                {task.project && <span className="tag">{task.project}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="section">
        <h3 className="section-title">
          Schedule
          <span className="section-note">
            {windowStart}–{windowEnd}
          </span>
        </h3>

        {allDayBlocks.map((block) => (
          <button
            type="button"
            className={`all-day-block ${block.kind}${
              block.task_id && taskById.get(block.task_id)?.done ? " done" : ""
            }`}
            key={block.id}
            onClick={() => onEditBlock(block)}
          >
            <span className={`kind-dot ${block.kind}`} />
            <span className="timeline-title">{block.title}</span>
            <span className="muted">All day</span>
            {block.task_project && <span className="tag">{block.task_project}</span>}
          </button>
        ))}

        {allDayFree.map((slot) => (
          <div className="all-day-free" key={`all-day-${slot.start}-${slot.end}`}>
            <span className="free-label">Free</span>
            <span className="muted">
              All day · {slot.start}–{slot.end}
            </span>
          </div>
        ))}

        {timeline.map((item) => (
          <div
            className={item.type === "free" ? "timeline-row free" : "timeline-row"}
            key={item.key}
          >
            <div className="timeline-time">{item.start}</div>
            {item.type === "free" ? (
              <div className="timeline-free">
                <span className="free-label">Free</span>
                <span className="timeline-range">
                  {item.start}–{item.end} · {durationLabel(item.minutes)}
                </span>
              </div>
            ) : (
              <button
                type="button"
                className={`timeline-block ${item.block.kind}${
                  item.block.task_id && taskById.get(item.block.task_id)?.done
                    ? " done"
                    : ""
                }`}
                onClick={() => onEditBlock(item.block)}
              >
                <span className={`kind-dot ${item.block.kind}`} />
                <span className="timeline-title">{item.block.title}</span>
                <span className="timeline-range">
                  {item.block.start}–{item.block.end}
                </span>
                {item.block.task_project && (
                  <span className="tag">{item.block.task_project}</span>
                )}
              </button>
            )}
          </div>
        ))}

        {slotsLoading && <p className="hint">Checking free time…</p>}

        {!slotsLoading && isPastDay && (
          <p className="hint">Free time is only calculated for today and future days.</p>
        )}

        {!slotsLoading && !isPastDay && freeSlots && slots.length === 0 && (
          <p className="hint">No free time in the configured window.</p>
        )}

        {!slotsLoading && !isPastDay && !freeSlots && (
          <p className="hint">Free-time information is unavailable right now.</p>
        )}

        {isEmpty && <p className="empty">Nothing scheduled for this day.</p>}
      </div>
    </section>
  );
}
