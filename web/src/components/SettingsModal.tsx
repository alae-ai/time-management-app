import { useState, type FormEvent } from "react";

import { api, errorMessage } from "../api";
import { timeToMinutes } from "../date";
import type { Settings, SettingsInput } from "../types";
import { Modal } from "./Modal";

type Props = {
  settings: Settings;
  onClose: () => void;
  onSaved: (settings: Settings) => void;
};

const GRANULARITIES = [5, 10, 15, 20, 30, 60];

export function SettingsModal({ settings, onClose, onSaved }: Props) {
  const [dayStart, setDayStart] = useState(settings.day_start);
  const [dayEnd, setDayEnd] = useState(settings.day_end);
  const [weekStartsOn, setWeekStartsOn] = useState(settings.week_starts_on);
  const [granularity, setGranularity] = useState(settings.granularity_min);
  const [buffer, setBuffer] = useState(settings.buffer_min);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (timeToMinutes(dayStart) >= timeToMinutes(dayEnd)) {
      setError("The day must start before it ends.");
      return;
    }
    if (buffer < 0 || buffer > 120) {
      setError("Buffer must be between 0 and 120 minutes.");
      return;
    }

    const body: SettingsInput = {
      day_start: dayStart,
      day_end: dayEnd,
      week_starts_on: weekStartsOn,
      granularity_min: granularity,
      buffer_min: buffer,
    };

    setSaving(true);
    setError(null);
    try {
      onSaved(await api.updateSettings(body));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  function resetDefaults() {
    setDayStart("08:00");
    setDayEnd("22:00");
    setWeekStartsOn(1);
    setGranularity(30);
    setBuffer(0);
  }

  return (
    <Modal title="Settings" onClose={onClose}>
      <form className="form" onSubmit={handleSubmit}>
        <p className="hint">
          These values drive the calendar and the free-time engine. Changes apply to both
          immediately.
        </p>

        <div className="row-2">
          <label className="field">
            <span>Schedulable day starts</span>
            <input
              type="time"
              value={dayStart}
              onChange={(event) => setDayStart(event.target.value)}
            />
          </label>
          <label className="field">
            <span>…and ends</span>
            <input
              type="time"
              value={dayEnd}
              onChange={(event) => setDayEnd(event.target.value)}
            />
          </label>
        </div>

        <div className="row-2">
          <label className="field">
            <span>Week starts on</span>
            <select
              value={weekStartsOn}
              onChange={(event) => setWeekStartsOn(Number(event.target.value))}
            >
              <option value={1}>Monday</option>
              <option value={0}>Sunday</option>
            </select>
          </label>
          <label className="field">
            <span>Slot granularity</span>
            <select
              value={granularity}
              onChange={(event) => setGranularity(Number(event.target.value))}
            >
              {GRANULARITIES.map((value) => (
                <option key={value} value={value}>
                  {value} minutes
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="field">
          <span>Buffer around blocks (minutes)</span>
          <input
            type="number"
            min={0}
            max={120}
            value={buffer}
            onChange={(event) => setBuffer(Number(event.target.value))}
          />
        </label>

        {error && <div className="error-box">{error}</div>}

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={resetDefaults}>
            Reset defaults
          </button>
          <span className="spacer" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Save settings"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
