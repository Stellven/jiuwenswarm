import type { JsonRecord, StoryEvent } from '../api';

export const logLevels = ['plain', 'debug', 'info', 'success', 'warning', 'error'] as const;
export type LogLevel = (typeof logLevels)[number];

export type LogRow = {
  id: string;
  timestamp?: string;
  dateTime?: string;
  level: LogLevel;
  source?: string;
  message: string;
  raw?: string;
  cursor?: number;
};

const levelPattern = 'TRACE|DEBUG|INFO|NOTICE|SUCCESS|WARN(?:ING)?|ERR(?:OR)?|CRITICAL|FATAL';
const timestampPattern = '\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}:\\d{2}(?:[.,]\\d+)?(?:Z|[+-]\\d{2}:?\\d{2})?';
const leadingTimestamp = new RegExp(`^\\[?(${timestampPattern}|\\d{2}:\\d{2}:\\d{2}(?:[.,]\\d+)?)\\]?(?=\\s|$)\\s*`);
const launchLine = new RegExp(
  `^(${timestampPattern})\\s+\\|\\s+([^|]+)\\|\\s+[^|]+\\|\\s+(${levelPattern})\\s+\\|\\s?(.*)$`,
  'i',
);
const leadingLevel = new RegExp(`^(?:\\[(${levelPattern})\\]|(${levelPattern})(?=[:\\s]|$))[:\\s]*`, 'i');
const diagnostic = /^(?:.+?:\d+(?::\d+)?:\s*)(warning|error|fatal error|[A-Za-z]+Warning|[A-Za-z]+Error)\s*:/i;
const testResult = /^\S+::.+?\s+(PASSED|FAILED|ERROR)(?:\s+\[\s*\d+%\])?\s*$/;

function record(value: unknown): JsonRecord | undefined {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonRecord) : undefined;
}

function string(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function displayLevel(value: unknown): LogLevel | undefined {
  if (typeof value !== 'string') return undefined;
  switch (value.toLowerCase()) {
    case 'trace':
    case 'debug':
      return 'debug';
    case 'info':
    case 'notice':
      return 'info';
    case 'success':
      return 'success';
    case 'warn':
    case 'warning':
      return 'warning';
    case 'err':
    case 'error':
    case 'critical':
    case 'fatal':
      return 'error';
    default:
      return undefined;
  }
}

function timeFields(value: unknown): Pick<LogRow, 'timestamp' | 'dateTime'> {
  if (typeof value === 'string' && value.trim()) return { timestamp: value };
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return {};
  const date = new Date(value < 1e12 ? value * 1000 : value);
  if (!Number.isFinite(date.getTime())) return {};
  const iso = date.toISOString();
  return { timestamp: `${iso.slice(0, 19).replace('T', ' ')}Z`, dateTime: iso };
}

function structuredRow(line: string): Omit<LogRow, 'id'> | undefined {
  if (!line.trimStart().startsWith('{')) return undefined;
  let data: JsonRecord | undefined;
  try {
    data = record(JSON.parse(line));
  } catch {
    return undefined;
  }
  if (!data) return undefined;

  const source = string(data.event_type) ?? string(data.event) ?? string(data.kind);
  const tool = string(data.tool_name) ?? string(record(data.tool_call)?.name);
  const error = string(data.error) ?? string(record(data.error)?.message);
  const message = error ?? string(data.message) ?? string(data.summary) ?? string(data.content) ?? string(data.raw);
  const description = [tool, message].filter(Boolean).join(' · ');
  const level =
    displayLevel(data.level ?? data.severity ?? data.log_level) ??
    (error || data.error === true || /(?:^|[._])error$/.test(source ?? '') ? 'error' : 'info');
  const turn = typeof data.turn === 'number' ? `#${data.turn}` : '';
  const label = description || turn || (source ? '' : line);
  return {
    ...timeFields(data.t ?? data.ts ?? data.timestamp ?? data.created),
    level,
    source,
    message: label,
    raw: label !== line ? line : undefined,
  };
}

function textRow(line: string): Omit<LogRow, 'id'> {
  const launch = launchLine.exec(line);
  if (launch) {
    return {
      timestamp: launch[1],
      source: launch[2].trim(),
      level: displayLevel(launch[3]) ?? 'plain',
      message: launch[4],
    };
  }
  const timestamp = leadingTimestamp.exec(line);
  const body = timestamp ? line.slice(timestamp[0].length) : line;
  const level = leadingLevel.exec(body);
  const code = diagnostic.exec(body);
  const test = testResult.exec(body);
  return {
    timestamp: timestamp?.[1],
    level:
      displayLevel(level?.[1] ?? level?.[2]) ??
      (code && (/warning$/i.test(code[1]) ? 'warning' : 'error')) ??
      (test && (test[1] === 'PASSED' ? 'success' : 'error')) ??
      'plain',
    message: level ? body.slice(level[0].length) : body,
  };
}

export function parseLog(content: string): LogRow[] {
  if (!content) return [];
  const lines = content.split(/\r\n|\n|\r/);
  if (lines[lines.length - 1] === '') lines.pop();
  return lines.map((raw, index) => {
    // Remove terminal controls while keeping evidence as text, including tabs and indentation.
    const line = raw.replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]/g, '');
    return { id: String(index + 1), ...(structuredRow(line) ?? textRow(line)) };
  });
}

export function projectStoryLog(events: readonly StoryEvent[]): LogRow[] {
  return events.map((event) => {
    let level: LogLevel = 'info';
    if (event.mark === '✗') level = 'error';
    else if (event.mark === '✓' || event.kind === 'accept') level = 'success';
    else if (/^(?:replan\/|reject$|revert_component$|report_inconclusive$|partial$)/.test(event.kind))
      level = 'warning';
    return {
      id: `${event.id}:${event.cursor}`,
      ...timeFields(event.created),
      level,
      source: event.kind,
      message: event.summary,
      cursor: event.cursor,
    };
  });
}

export function filterLogRows(rows: readonly LogRow[], query: string, level: LogLevel | 'all'): readonly LogRow[] {
  const needle = query.trim().toLowerCase();
  if (!needle && level === 'all') return rows;
  return rows.filter((row) => {
    if (level !== 'all' && row.level !== level) return false;
    return (
      !needle || [row.message, row.source, row.timestamp, row.raw].some((text) => text?.toLowerCase().includes(needle))
    );
  });
}
