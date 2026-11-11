import type { Task } from "../types";

type Props = {
  tasks: Task[];
  showDone: boolean;
  onToggleTask: (task: Task) => void;
  onEditTask: (task: Task) => void;
  onNewTask: () => void;
};

export function Backlog({ tasks, showDone, onToggleTask, onEditTask, onNewTask }: Props) {
  const visible = tasks
    .filter((task) => showDone || !task.done)
    .sort((left, right) => {
      if (left.done !== right.done) {
        return left.done ? 1 : -1;
      }
      return left.title.localeCompare(right.title);
    });

  return (
    <section className="panel backlog">
      <div className="panel-head">
        <h2 className="panel-title">Backlog</h2>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onNewTask}>
          + Task
        </button>
      </div>
      {visible.length === 0 ? (
        <p className="empty">No undated tasks. Clear a deadline to send a task here.</p>
      ) : (
        <div className="backlog-list">
          {visible.map((task) => (
            <div className={task.done ? "backlog-row done" : "backlog-row"} key={task.id}>
              <input
                type="checkbox"
                checked={task.done}
                onChange={() => onToggleTask(task)}
                aria-label={`Mark ${task.title} ${task.done ? "open" : "done"}`}
              />
              <button
                type="button"
                className="backlog-main"
                onClick={() => onEditTask(task)}
              >
                <span>{task.title}</span>
                {task.project && <span className="tag">{task.project}</span>}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
