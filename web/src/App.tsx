import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, errorMessage } from "./api";
import { Backlog } from "./components/Backlog";
import { BlockModal } from "./components/BlockModal";
import { DayPanel } from "./components/DayPanel";
import { MonthGrid } from "./components/MonthGrid";
import { SettingsModal } from "./components/SettingsModal";
import { TaskModal } from "./components/TaskModal";
import {
  addDays,
  ceilToGrid,
  isSameMonth,
  minutesToTime,
  monthLabel,
  parseIso,
  startOfMonth,
  startOfWeek,
  timeToMinutes,
  toIso,
  todayIso,
} from "./date";
import type {
  Block,
  FilterMode,
  FreeSlots,
  Settings,
  StateResponse,
  Task,
} from "./types";

const DEFAULT_SETTINGS: Settings = {
  day_start: "08:00",
  day_end: "22:00",
  week_starts_on: 1,
  granularity_min: 30,
  buffer_min: 0,
  max_range_days: 366,
  max_chat_messages: 40,
};

type ModalState =
  | { type: "task-create"; date: string }
  | { type: "task-edit"; task: Task }
  | { type: "appointment-create"; date: string }
  | { type: "session-create"; date: string }
  | { type: "block-edit"; block: Block };

type Toast = { kind: "info" | "error"; text: string };

const FILTERS: { mode: FilterMode; label: string }[] = [
  { mode: "all", label: "All" },
  { mode: "tasks", label: "Tasks" },
  { mode: "appointments", label: "Appointments" },
];

export default function App() {
  const [state, setState] = useState<StateResponse | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [month, setMonth] = useState<Date>(() => startOfMonth(new Date()));
  const [selected, setSelected] = useState<string>(() => todayIso());
  const [filter, setFilter] = useState<FilterMode>("all");
  const [showDone, setShowDone] = useState(true);
  const [daySlots, setDaySlots] = useState<FreeSlots | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [modal, setModal] = useState<ModalState | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const busyRef = useRef(false);

  const settings = state?.settings ?? DEFAULT_SETTINGS;
  const weekStartsOn = settings.week_starts_on;

  const gridStart = useMemo(
    () => startOfWeek(startOfMonth(month), weekStartsOn),
    [month, weekStartsOn],
  );
  const days = useMemo(
    () => Array.from({ length: 42 }, (_, index) => addDays(gridStart, index)),
    [gridStart],
  );
  const rangeFrom = toIso(gridStart);
  const rangeTo = toIso(addDays(gridStart, 41));

  const loadState = useCallback(async () => {
    try {
      const data = await api.getState(rangeFrom, rangeTo);
      setState(data);
      setFatalError(null);
    } catch (caught) {
      setFatalError(errorMessage(caught));
    }
  }, [rangeFrom, rangeTo]);

  useEffect(() => {
    void loadState();
    const timer = window.setInterval(() => {
      if (!busyRef.current) {
        void loadState();
      }
    }, 5000);
    const onFocus = () => {
      if (!busyRef.current) {
        void loadState();
      }
    };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [loadState]);

  useEffect(() => {
    let cancelled = false;
    setSlotsLoading(true);
    api
      .getFreeSlots(selected, 15)
      .then((data) => {
        if (!cancelled) {
          setDaySlots(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDaySlots(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSlotsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [
    selected,
    state?.now,
    settings.day_start,
    settings.day_end,
    settings.granularity_min,
    settings.buffer_min,
  ]);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function run<T>(action: () => Promise<T>): Promise<T> {
    busyRef.current = true;
    try {
      return await action();
    } finally {
      busyRef.current = false;
    }
  }

  async function refreshWithToast(message: string) {
    setToast({ kind: "info", text: message });
    await loadState();
  }

  function handleTaskSaved(task: Task) {
    setModal(null);
    void refreshWithToast(`Saved “${task.title}”.`);
  }

  function handleTaskDeleted() {
    setModal(null);
    void refreshWithToast("Task deleted.");
  }

  function handleBlockSaved(block: Block) {
    setModal(null);
    void refreshWithToast(`Saved “${block.title}”.`);
  }

  function handleBlockDeleted() {
    setModal(null);
    void refreshWithToast("Block deleted.");
  }

  function handleSettingsSaved(next: Settings) {
    setSettingsOpen(false);
    setState((prev) => (prev ? { ...prev, settings: next } : prev));
    void refreshWithToast("Settings updated.");
  }

  async function handleToggleTask(task: Task) {
    const next = !task.done;
    setState((prev) =>
      prev
        ? {
            ...prev,
            tasks: prev.tasks.map((item) =>
              item.id === task.id ? { ...item, done: next } : item,
            ),
          }
        : prev,
    );
    try {
      await run(() => api.updateTask(task.id, { done: next }));
      await loadState();
    } catch (caught) {
      setToast({ kind: "error", text: errorMessage(caught) });
      await loadState();
    }
  }

  function shiftMonth(delta: number) {
    const next = new Date(month.getFullYear(), month.getMonth() + delta, 1);
    setMonth(next);
    setSelected(toIso(next));
  }

  function goToday() {
    const now = new Date();
    setMonth(startOfMonth(now));
    setSelected(toIso(now));
  }

  function handleSelect(iso: string) {
    setSelected(iso);
    const date = parseIso(iso);
    if (!isSameMonth(date, month)) {
      setMonth(startOfMonth(date));
    }
  }

  if (!state) {
    return (
      <div className="boot">
        <div className="boot-card">
          <div className="brand brand-boot">
            <span className="brand-mark">▦</span>
            <span className="brand-name">Time Manager</span>
          </div>
          {fatalError ? (
            <>
              <h1>Cannot reach the API</h1>
              <p>
                Start the app with <code>scripts/dev.sh</code> or <code>tm serve</code>,
                then retry.
              </p>
              <pre className="boot-error">{fatalError}</pre>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void loadState()}
              >
                Retry
              </button>
            </>
          ) : (
            <p>Loading your calendar…</p>
          )}
        </div>
      </div>
    );
  }

  const today = state.today;
  const slotsForSelected =
    daySlots && daySlots.from === selected && daySlots.to === selected
      ? daySlots.slots
      : [];
  const firstFreeSlot = slotsForSelected[0];

  function blockDefaults(): { start: string; end: string } {
    const now = new Date();
    const dayStart = timeToMinutes(settings.day_start);
    const dayEnd = timeToMinutes(settings.day_end);
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    const earliest =
      selected === today
        ? Math.max(dayStart, ceilToGrid(nowMinutes, settings.granularity_min))
        : dayStart;

    if (firstFreeSlot) {
      const slotStart = Math.max(earliest, timeToMinutes(firstFreeSlot.start));
      const slotEnd = timeToMinutes(firstFreeSlot.end);
      if (slotEnd > slotStart) {
        const endMinutes = Math.min(slotStart + 60, slotEnd);
        return { start: minutesToTime(slotStart), end: minutesToTime(endMinutes) };
      }
    }

    const startMinutes = Math.min(earliest, Math.max(dayStart, dayEnd - 30));
    const endMinutes = Math.min(startMinutes + 60, dayEnd);
    return { start: minutesToTime(startMinutes), end: minutesToTime(endMinutes) };
  }

  function openBlockCreate(kind: "appointment" | "session") {
    if (selected < today) {
      setToast({ kind: "error", text: "Cannot schedule a block on a past date." });
      return;
    }
    setModal({ type: `${kind}-create`, date: selected });
  }

  const defaultBlockTimes = blockDefaults();
  const dayBlocks = state.blocks.filter((block) => block.date === selected);
  const backlogTasks = state.tasks.filter((task) => !task.deadline);
  const openTasks = state.tasks.filter((task) => !task.done);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">▦</span>
          <span className="brand-name">Time Manager</span>
        </div>

        <div className="month-nav">
          <button
            type="button"
            className="nav-btn"
            onClick={() => shiftMonth(-1)}
            aria-label="Previous month"
          >
            ‹
          </button>
          <h1 className="month-title">{monthLabel(month)}</h1>
          <button
            type="button"
            className="nav-btn"
            onClick={() => shiftMonth(1)}
            aria-label="Next month"
          >
            ›
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={goToday}>
            Today
          </button>
        </div>

        <div className="topbar-actions">
          <div className="segmented" role="group" aria-label="Filter calendar">
            {FILTERS.map((item) => (
              <button
                key={item.mode}
                type="button"
                className={filter === item.mode ? "seg-btn active" : "seg-btn"}
                onClick={() => setFilter(item.mode)}
                aria-pressed={filter === item.mode}
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="toggle">
            <input
              type="checkbox"
              checked={showDone}
              onChange={(event) => setShowDone(event.target.checked)}
            />
            Show done
          </label>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setSettingsOpen(true)}
          >
            Settings
          </button>
        </div>
      </header>

      {fatalError && (
        <div className="banner" role="status">
          <strong>Can’t reach the API.</strong> Retrying automatically.
          <span className="banner-detail">{fatalError}</span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => void loadState()}
          >
            Retry now
          </button>
        </div>
      )}

      <main className="layout">
        <section className="calendar-card">
          <MonthGrid
            month={month}
            days={days}
            today={today}
            selected={selected}
            tasks={state.tasks}
            blocks={state.blocks}
            settings={settings}
            filter={filter}
            showDone={showDone}
            onSelect={handleSelect}
            onEditTask={(task) => setModal({ type: "task-edit", task })}
            onEditBlock={(block) => setModal({ type: "block-edit", block })}
            onToggleTask={(task) => void handleToggleTask(task)}
          />
        </section>

        <aside className="side">
          <DayPanel
            day={selected}
            today={today}
            tasks={state.tasks}
            blocks={dayBlocks}
            freeSlots={daySlots}
            slotsLoading={slotsLoading}
            showDone={showDone}
            windowStart={settings.day_start}
            windowEnd={settings.day_end}
            onEditTask={(task) => setModal({ type: "task-edit", task })}
            onEditBlock={(block) => setModal({ type: "block-edit", block })}
            onToggleTask={(task) => void handleToggleTask(task)}
            onCreateTask={() => setModal({ type: "task-create", date: selected })}
            onCreateAppointment={() => openBlockCreate("appointment")}
            onCreateSession={() => openBlockCreate("session")}
          />

          <Backlog
            tasks={backlogTasks}
            showDone={showDone}
            onToggleTask={(task) => void handleToggleTask(task)}
            onEditTask={(task) => setModal({ type: "task-edit", task })}
            onNewTask={() => setModal({ type: "task-create", date: "" })}
          />
        </aside>
      </main>

      {modal?.type === "task-create" && (
        <TaskModal
          defaultDate={modal.date}
          onClose={() => setModal(null)}
          onSaved={handleTaskSaved}
          onDeleted={handleTaskDeleted}
        />
      )}

      {modal?.type === "task-edit" && (
        <TaskModal
          task={modal.task}
          defaultDate={modal.task.deadline ?? selected}
          onClose={() => setModal(null)}
          onSaved={handleTaskSaved}
          onDeleted={handleTaskDeleted}
        />
      )}

      {modal?.type === "appointment-create" && (
        <BlockModal
          kind="appointment"
          defaultDate={modal.date}
          defaultStart={defaultBlockTimes.start}
          defaultEnd={defaultBlockTimes.end}
          tasks={openTasks}
          onClose={() => setModal(null)}
          onSaved={handleBlockSaved}
          onDeleted={handleBlockDeleted}
        />
      )}

      {modal?.type === "session-create" && (
        <BlockModal
          kind="session"
          defaultDate={modal.date}
          defaultStart={defaultBlockTimes.start}
          defaultEnd={defaultBlockTimes.end}
          tasks={openTasks}
          onClose={() => setModal(null)}
          onSaved={handleBlockSaved}
          onDeleted={handleBlockDeleted}
        />
      )}

      {modal?.type === "block-edit" && (
        <BlockModal
          kind={modal.block.kind}
          block={modal.block}
          defaultDate={modal.block.date}
          tasks={openTasks}
          onClose={() => setModal(null)}
          onSaved={handleBlockSaved}
          onDeleted={handleBlockDeleted}
        />
      )}

      {settingsOpen && (
        <SettingsModal
          settings={settings}
          onClose={() => setSettingsOpen(false)}
          onSaved={handleSettingsSaved}
        />
      )}

      {toast && (
        <div
          className={`toast toast-${toast.kind}`}
          role="status"
          aria-live="polite"
        >
          <span>{toast.text}</span>
          <button
            type="button"
            className="toast-close"
            onClick={() => setToast(null)}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
