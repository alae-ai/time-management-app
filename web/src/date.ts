const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const MONTH_FORMAT = new Intl.DateTimeFormat("en-GB", {
  month: "long",
  year: "numeric",
});

const WEEKDAY_FORMAT = new Intl.DateTimeFormat("en-GB", { weekday: "short" });

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function toIso(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function parseIso(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, (month ?? 1) - 1, day ?? 1);
}

export function todayIso(): string {
  return toIso(new Date());
}

export function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function startOfWeek(date: Date, weekStartsOn: number): Date {
  const offset = (date.getDay() - weekStartsOn + 7) % 7;
  return addDays(date, -offset);
}

export function isSameMonth(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth()
  );
}

export function monthLabel(date: Date): string {
  return MONTH_FORMAT.format(date);
}

export function dayLabel(iso: string): string {
  return DATE_FORMAT.format(parseIso(iso));
}

export function weekdayLabels(weekStartsOn: number): string[] {
  // 7 January 2024 is a Sunday.
  const sunday = new Date(2024, 0, 7);
  return Array.from({ length: 7 }, (_, index) =>
    WEEKDAY_FORMAT.format(addDays(sunday, weekStartsOn + index)),
  );
}

export function dayNumber(iso: string): number {
  return parseIso(iso).getDate();
}

export function timeToMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

export function durationLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours && rest) {
    return `${hours}h${pad(rest)}`;
  }
  if (hours) {
    return `${hours}h`;
  }
  return `${rest}m`;
}

export function isPast(iso: string, today: string): boolean {
  return iso < today;
}
