import { useState, type FormEvent } from "react";

import { ApiError, api, conflictLabels, errorMessage } from "../api";
import { timeToMinutes } from "../date";
import type { Block, Task } from "../types";
import { Modal } from "./Modal";

type Props = {
  kind: "appointment" | "session";
  defaultDate: string;
  defaultStart?: string;
  defaultEnd?: string;
  tasks: Task[];
  block?: Block;
  onClose: () => void;
  onSaved: (block: Block) => void;
  onDeleted: (id: string) => void;
};

export function BlockModal({
  kind,
  defaultDate,
  defaultStart,
  defaultEnd,
  tasks,
  block,
  onClose,
  onSaved,
  onDeleted,
}: Props) {
  const editing = Boolean(block);
  const isSession = (block?.kind ?? kind) === "session";

  const [title, setTitle] = useState(block?.title ?? "");
  const [date, setDate] = useState(block?.date ?? defaultDate);
  const [allDay, setAllDay] = useState(block?.all_day ?? false);
  const [start, setStart] = useState(block?.start ?? defaultStart ?? "09:00");
  const [end, setEnd] = useState(block?.end ?? defaultEnd ?? "10:00");
  const [notes, setNotes] = useState(block?.notes ?? "");
  const [taskId, setTaskId] = useState(block?.task_id ?? tasks[0]?.id ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<string[]>([]);

  async function submit(force: boolean, event?: FormEvent) {
    event?.preventDefault();

    if (!date) {
      setError("Choose a date.");
      return;
    }
    if (!isSession && !title.trim()) {
      setError("Give the appointment a title.");
      return;
    }
    if (isSession && editing && !title.trim()) {
      setError("Give the session a title.");
      return;
    }
    if (isSession && !editing && !taskId) {
      setError("Choose a task for this session.");
      return;
    }
    if (!allDay) {
      if (!start || !end) {
        setError("Provide a start and end time, or mark it all day.");
        return;
      }
      if (timeToMinutes(start) >= timeToMinutes(end)) {
        setError("The end time must be after the start time.");
        return;
      }
    }

    setSaving(true);
    setError(null);

    try {
      let saved: Block;
      if (isSession && !editing) {
        saved = await api.scheduleSession(taskId, {
          date,
          start: allDay ? null : start,
          end: allDay ? null : end,
          all_day: allDay,
          notes,
          allow_overlap: force,
        });
      } else if (editing && block) {
        saved = await api.updateBlock(block.id, {
          title: title.trim(),
          date,
          start: allDay ? null : start,
          end: allDay ? null : end,
          notes,
          allow_overlap: force,
        });
      } else {
        saved = await api.createBlock({
          title: title.trim(),
          kind: "appointment",
          date,
          start: allDay ? null : start,
          end: allDay ? null : end,
          notes,
          allow_overlap: force,
        });
      }
      onSaved(saved);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setConflicts(conflictLabels(caught));
        setError("That time overlaps an existing block.");
      } else {
        setError(errorMessage(caught));
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!block) {
      return;
    }
    if (!window.confirm(`Delete "${block.title}"?`)) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.deleteBlock(block.id);
      onDeleted(block.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  const heading = editing
    ? `Edit ${isSession ? "session" : "appointment"}`
    : `New ${isSession ? "session" : "appointment"}`;

  return (
    <Modal title={heading} onClose={onClose}>
      <form className="form" onSubmit={(event) => void submit(false, event)}>
        {isSession && !editing ? (
          <label className="field">
            <span>Task</span>
            <select value={taskId} onChange={(event) => setTaskId(event.target.value)}>
              <option value="">Choose a task…</option>
              {tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                  {task.project ? ` · ${task.project}` : ""}
                </option>
              ))}
            </select>
            {tasks.length === 0 && (
              <span className="hint">Create a task first, then schedule work for it.</span>
            )}
          </label>
        ) : (
          <label className="field">
            <span>{isSession ? "Session title" : "Title"}</span>
            <input
              autoFocus
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={isSession ? "Work on TP report" : "Dentist"}
            />
          </label>
        )}

        {block?.task_title && (
          <p className="hint">
            Linked task: <strong>{block.task_title}</strong>
            {block.task_project ? ` · ${block.task_project}` : ""}
          </p>
        )}

        <div className="row-2">
          <label className="field">
            <span>Date</span>
            <input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <label className="check check-large">
            <input
              type="checkbox"
              checked={allDay}
              onChange={(event) => setAllDay(event.target.checked)}
            />
            All day
          </label>
        </div>

        {!allDay && (
          <div className="row-2">
            <label className="field">
              <span>Start</span>
              <input
                type="time"
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </label>
            <label className="field">
              <span>End</span>
              <input
                type="time"
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </label>
          </div>
        )}

        <label className="field">
          <span>Notes</span>
          <textarea
            rows={3}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Optional"
          />
        </label>

        {error && <div className="error-box">{error}</div>}
        {conflicts.length > 0 && (
          <div className="conflict-box">
            <strong>Overlaps with:</strong>
            <ul>
              {conflicts.map((label) => (
                <li key={label}>{label}</li>
              ))}
            </ul>
            <button
              type="button"
              className="btn btn-warn btn-sm"
              onClick={() => void submit(true)}
              disabled={saving}
            >
              Schedule anyway
            </button>
          </div>
        )}

        <div className="modal-actions">
          {editing && (
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
          <button
            type="submit"
            className="btn btn-primary"
            disabled={saving || (isSession && !editing && tasks.length === 0)}
          >
            {saving ? "Saving…" : editing ? "Save" : "Create"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
