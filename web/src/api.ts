import type {
  ApiErrorPayload,
  ApiToken,
  ApiTokenCreated,
  AuthSession,
  Block,
  BlockInput,
  BlockPatch,
  FreeSlots,
  SessionInput,
  Settings,
  SettingsInput,
  StateResponse,
  Task,
  TaskInput,
  TaskPatch,
  User,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const payload = data as ApiErrorPayload | null;
    throw new ApiError(
      response.status,
      payload?.error?.code ?? "http_error",
      payload?.error?.message ?? `Request failed (${response.status})`,
      payload?.error?.details,
    );
  }

  return data as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, body: JSON.stringify(body) };
}

export const api = {
  getState(from: string, to: string): Promise<StateResponse> {
    const params = new URLSearchParams({ from, to });
    return request<StateResponse>(`/state?${params}`);
  },

  createTask(input: TaskInput): Promise<Task> {
    return request<Task>("/tasks", json("POST", input));
  },

  updateTask(id: string, input: TaskPatch): Promise<Task> {
    return request<Task>(`/tasks/${id}`, json("PATCH", input));
  },

  deleteTask(id: string): Promise<void> {
    return request<void>(`/tasks/${id}`, { method: "DELETE" });
  },

  scheduleSession(taskId: string, input: SessionInput): Promise<Block> {
    return request<Block>(`/tasks/${taskId}/sessions`, json("POST", input));
  },

  createBlock(input: BlockInput): Promise<Block> {
    return request<Block>("/blocks", json("POST", input));
  },

  updateBlock(id: string, input: BlockPatch): Promise<Block> {
    return request<Block>(`/blocks/${id}`, json("PATCH", input));
  },

  deleteBlock(id: string): Promise<void> {
    return request<void>(`/blocks/${id}`, { method: "DELETE" });
  },

  getFreeSlots(day: string, minMinutes = 15): Promise<FreeSlots> {
    const params = new URLSearchParams({
      from: day,
      to: day,
      min: String(minMinutes),
    });
    return request<FreeSlots>(`/free-slots?${params}`);
  },

  getSettings(): Promise<Settings> {
    return request<Settings>("/settings");
  },

  updateSettings(input: SettingsInput): Promise<Settings> {
    return request<Settings>("/settings", json("PATCH", input));
  },

  getSession(): Promise<AuthSession> {
    return request<AuthSession>("/auth/session");
  },

  setup(input: {
    email: string;
    name?: string;
    password: string;
    setup_token?: string;
  }): Promise<AuthSession> {
    return request<AuthSession>("/auth/setup", json("POST", input));
  },

  login(input: { email: string; password: string }): Promise<AuthSession> {
    return request<AuthSession>("/auth/login", json("POST", input));
  },

  logout(): Promise<void> {
    return request<void>("/auth/logout", { method: "POST" });
  },

  getMe(): Promise<User> {
    return request<User>("/auth/me");
  },

  changePassword(input: {
    current_password: string;
    new_password: string;
  }): Promise<void> {
    return request<void>("/auth/password", json("POST", input));
  },

  listTokens(): Promise<ApiToken[]> {
    return request<ApiToken[]>("/auth/tokens");
  },

  createToken(name: string): Promise<ApiTokenCreated> {
    return request<ApiTokenCreated>("/auth/tokens", json("POST", { name }));
  },

  revokeToken(id: string): Promise<void> {
    return request<void>(`/auth/tokens/${id}`, { method: "DELETE" });
  },

  listUsers(): Promise<User[]> {
    return request<User[]>("/admin/users");
  },

  createUser(input: {
    email: string;
    name?: string;
    password: string;
    is_admin?: boolean;
  }): Promise<User> {
    return request<User>("/admin/users", json("POST", input));
  },

  updateUser(
    id: string,
    input: {
      name?: string;
      is_admin?: boolean;
      is_active?: boolean;
      password?: string;
    },
  ): Promise<User> {
    return request<User>(`/admin/users/${id}`, json("PATCH", input));
  },
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

export function conflictLabels(error: ApiError): string[] {
  if (!Array.isArray(error.details)) {
    return [];
  }
  return error.details
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const block = item as Partial<Block>;
      if (!block.title) {
        return null;
      }
      const when = block.all_day
        ? "all day"
        : block.start && block.end
          ? `${block.start}–${block.end}`
          : "";
      return `${block.title}${when ? ` (${when})` : ""}`;
    })
    .filter((label): label is string => Boolean(label));
}
