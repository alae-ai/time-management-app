import { useState, type FormEvent } from "react";

import { api, errorMessage } from "../api";
import type { Task, TaskInput } from "../types";
import { Modal } from "./Modal";

type Props = {
  task?: Task;
  defaultDate: string;
  onClose: () => void;
  onSaved: (task: Task) => void;
  onDeleted: (id: string) => void;
};

export function TaskModal({ task, defaultDate, onClose, onSaved, onDeleted }: Props) {
  const [title, setTitle] = useState(task?.title ?? "");
  const [project, setProject] = useState(task?.project ?? "");
  const [notes, setNotes] = useState(task?.notes ?? "");
  const [deadline, setDeadline] = useState(
    task ? (task.deadline ?? "") : defaultDate,
  );
  const [deadlineTime, setDeadlineTime] = useState(task?.deadline_time ?? "");
  const [done, setDone] = useState(task?.done ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setError("Give the task a title.");
      return;
    }
    if (deadlineTime && !deadline) {
      setError("A deadline time needs a deadline date.");
      return;
    }

    const body: TaskInput = {
      title: title.trim(),
      project: project.trim() || null,
      notes,
      deadline: deadline || null,
      deadline_time: deadlineTime || null,
    };
    if (task) {
      body.done = done;
    }

    setSaving(true);
    setError(null);
    try {
      const saved = task ? await api.updateTask(task.id, body) : await api.createTask(body);
      onSaved(saved);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!task) {
      return;
    }
    if (!window.confirm(`Delete "${task.title}" and its scheduled sessions?`)) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.deleteTask(task.id);
      onDeleted(task.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={task ? "Edit task" : "New task"} onClose={onClose}>
      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Title</span>
          <input
            autoFocus
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="TP report"
          />
        </label>

        <div className="row-2">
          <label className="field">
            <span>Project</span>
            <input
              value={project}
              onChange={(event) => setProject(event.target.value)}
              placeholder="TP"
            />
          </label>
          <label className="field">
            <span>Deadline</span>
            <input
              type="date"
              value={deadline}
              onChange={(event) => {
                setDeadline(event.target.value);
                if (!event.target.value) {
                  setDeadlineTime("");
                }
              }}
            />
          </label>
        </div>

        <div className="row-2">
          <label className="field">
            <span>Deadline time (optional)</span>
            <input
              type="time"
              value={deadlineTime}
              disabled={!deadline}
              onChange={(event) => setDeadlineTime(event.target.value)}
            />
          </label>
          {task ? (
            <label className="check check-large">
              <input
                type="checkbox"
                checked={done}
                onChange={(event) => setDone(event.target.checked)}
              />
              Completed
            </label>
          ) : (
            <div className="field hint-field">
              <span>No deadline?</span>
              <span className="hint">Clear the date to keep it in the backlog.</span>
            </div>
          )}
        </div>

        <label className="field">
          <span>Notes</span>
          <textarea
            rows={3}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Anything useful for this task"
          />
        </label>

        {error && <div className="error-box">{error}</div>}

        <div className="modal-actions">
          {task && (
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => void handleDelete()}
              disabled={saving}
            >
              Delete
            </button>
          )}
          <span className="spacer" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving…" : task ? "Save task" : "Create task"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
