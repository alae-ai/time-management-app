export type Settings = {
  day_start: string;
  day_end: string;
  week_starts_on: number;
  granularity_min: number;
  buffer_min: number;
  max_range_days: number;
  max_chat_messages: number;
};

export type Task = {
  id: string;
  title: string;
  project: string | null;
  notes: string;
  deadline: string | null;
  deadline_time: string | null;
  done: boolean;
  done_at: string | null;
  created_at: string;
  updated_at: string;
};

export type BlockKind = "appointment" | "session";

export type Block = {
  id: string;
  title: string;
  kind: BlockKind;
  task_id: string | null;
  task_title: string | null;
  task_project: string | null;
  date: string;
  start: string | null;
  end: string | null;
  all_day: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type StateResponse = {
  settings: Settings;
  tasks: Task[];
  blocks: Block[];
  today: string;
  now: string;
};

export type Slot = {
  date: string;
  start: string;
  end: string;
  minutes: number;
  all_day: boolean;
};

export type FreeSlots = {
  from: string;
  to: string;
  window: { start: string; end: string };
  min_minutes: number;
  slots: Slot[];
  truncated: boolean;
};

export type TaskPatch = {
  title?: string;
  project?: string | null;
  notes?: string;
  deadline?: string | null;
  deadline_time?: string | null;
  done?: boolean;
};

export type TaskInput = TaskPatch & {
  title: string;
};

export type BlockInput = {
  title: string;
  kind: BlockKind;
  date: string;
  start?: string | null;
  end?: string | null;
  notes?: string;
  allow_overlap?: boolean;
};

export type BlockPatch = {
  title?: string;
  date?: string;
  start?: string | null;
  end?: string | null;
  notes?: string;
  allow_overlap?: boolean;
};

export type SessionInput = {
  date: string;
  start?: string | null;
  end?: string | null;
  all_day?: boolean;
  notes?: string;
  allow_overlap?: boolean;
};

export type SettingsInput = Partial<
  Pick<
    Settings,
    | "day_start"
    | "day_end"
    | "week_starts_on"
    | "granularity_min"
    | "buffer_min"
    | "max_range_days"
  >
>;

export type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
};

export type FilterMode = "all" | "tasks" | "appointments";
