import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useTranslation } from 'react-i18next';
import type { StoryEvent } from '../api';
import { filterLogRows, logLevels, parseLog, projectStoryLog, type LogLevel } from './logModel';
import { ReplayLabel } from './NodeEvidence';
import './terminalViewer.css';

const labels = {
  en: {
    log: 'File log',
    events: 'Replay log',
    search: 'Filter log',
    all: 'All levels',
    level: 'Level',
    time: 'Timestamp',
    entry: 'Entry',
    count: 'Entries shown / total',
    empty: 'No log entries yet.',
    noMatches: 'No entries match these filters.',
    showRecord: 'Show log record',
    hideRecord: 'Hide log record',
    levels: { plain: 'Plain', debug: 'Debug', info: 'Info', success: 'Success', warning: 'Warning', error: 'Error' },
  },
  zh: {
    log: '文件日志',
    events: '回放日志',
    search: '筛选日志',
    all: '所有级别',
    level: '级别',
    time: '时间戳',
    entry: '条目',
    count: '显示条目数 / 总条目数',
    empty: '暂无日志条目。',
    noMatches: '没有符合筛选条件的条目。',
    showRecord: '展开日志记录',
    hideRecord: '收起日志记录',
    levels: { plain: '纯文本', debug: '调试', info: '信息', success: '成功', warning: '警告', error: '错误' },
  },
};

type TerminalViewerProps =
  | { content: string; events?: never; activeCursor?: never; onSeek?: never }
  | { content?: never; events: readonly StoryEvent[]; activeCursor?: number; onSeek?: (cursor: number) => void };

export function TerminalViewer({ content, events, activeCursor, onSeek }: TerminalViewerProps) {
  const { i18n } = useTranslation();
  const text = labels[(i18n.resolvedLanguage ?? i18n.language)?.startsWith('zh') ? 'zh' : 'en'];
  const title = events ? text.events : text.log;
  const [query, setQuery] = useState('');
  const [level, setLevel] = useState<LogLevel | 'all'>('all');
  const [expandedRecord, setExpandedRecord] = useState<string>();
  const scrollRoot = useRef<HTMLDivElement>(null);

  const rows = useMemo(() => (events ? projectStoryLog(events) : parseLog(content ?? '')), [content, events]);
  const visibleRows = useMemo(() => filterLogRows(rows, query, level), [rows, query, level]);
  const virtualizer = useVirtualizer({
    count: visibleRows.length,
    getScrollElement: () => scrollRoot.current,
    getItemKey: useCallback((index: number) => visibleRows[index].id, [visibleRows]),
    estimateSize: () => 32,
    overscan: 12,
  });
  const previousCursor = useRef<number>();
  useLayoutEffect(() => {
    if (activeCursor === previousCursor.current) return;
    const frame = requestAnimationFrame(() => {
      previousCursor.current = activeCursor;
      if (activeCursor === undefined) {
        virtualizer.scrollToOffset(0);
        return;
      }
      const index = visibleRows.findIndex(
        (row) => row.cursor === activeCursor || (row.firstCursor !== undefined && row.cursor !== undefined && row.firstCursor <= activeCursor && activeCursor <= row.cursor),
      );
      if (index !== -1) virtualizer.scrollToIndex(index, { align: 'auto' });
    });
    return () => cancelAnimationFrame(frame);
  }, [activeCursor, visibleRows, virtualizer]);

  return (
    <section className="factory-terminal" aria-label={title} data-testid="factory-runs-terminal-viewer">
      <div className="factory-terminal-toolbar" data-testid="factory-runs-terminal-toolbar">
        <strong data-testid="factory-runs-terminal-title">{title}</strong>
        <input
          type="search"
          value={query}
          placeholder={text.search}
          aria-label={text.search}
          data-testid="factory-runs-terminal-filter"
          onChange={(event) => {
            setQuery(event.target.value);
            virtualizer.scrollToOffset(0);
          }}
        />
        <select
          value={level}
          aria-label={text.level}
          data-testid="factory-runs-terminal-level-filter"
          onChange={(event) => {
            setLevel(event.target.value as LogLevel | 'all');
            virtualizer.scrollToOffset(0);
          }}
        >
          <option value="all" data-testid="factory-runs-terminal-level-option" data-variant="all">
            {text.all}
          </option>
          {logLevels.map((value) => (
            <option key={value} value={value} data-testid="factory-runs-terminal-level-option" data-variant={value}>
              {text.levels[value]}
            </option>
          ))}
        </select>
        <span className="factory-terminal-count" title={text.count} data-testid="factory-runs-terminal-count">
          {visibleRows.length.toLocaleString(i18n.language)} / {rows.length.toLocaleString(i18n.language)}
        </span>
      </div>
      {visibleRows.length ? (
        <>
          <div className="factory-terminal-columns factory-terminal-grid" data-testid="factory-runs-terminal-columns">
            <span data-testid="factory-runs-terminal-time-label">{text.time}</span>
            <span data-testid="factory-runs-terminal-level-label">{text.level}</span>
            <span data-testid="factory-runs-terminal-entry-label">{text.entry}</span>
          </div>
          <div
            className="factory-terminal-scroll"
            ref={scrollRoot}
            tabIndex={0}
            role="region"
            aria-label={title}
            data-testid="factory-runs-terminal-scroll"
          >
            <div
              className="factory-terminal-list"
              style={{ height: virtualizer.getTotalSize() }}
              role="list"
              data-testid="factory-runs-terminal-list"
            >
              {virtualizer.getVirtualItems().map((item) => {
                const row = visibleRows[item.index];
                const cursor = row.cursor;
                const current = cursor !== undefined && activeCursor !== undefined && (cursor === activeCursor || (row.firstCursor !== undefined && row.firstCursor <= activeCursor && activeCursor <= cursor));
                const expanded = row.id === expandedRecord;
                const message = (
                  <>
                    {row.source && <span className="factory-terminal-source">{row.source}</span>}
                    {row.kind && row.kind !== row.source && <small className="factory-original-kind factory-inline-kind" data-testid="factory-runs-terminal-kind">{row.kind}</small>}
                    {row.source && row.message && ' '}
                    <span>{row.message}<ReplayLabel value={row.replayedFrom} /></span>
                  </>
                );
                return (
                  <div
                    key={item.key}
                    className="factory-terminal-row factory-terminal-grid"
                    style={{ transform: `translateY(${item.start}px)` }}
                    ref={virtualizer.measureElement}
                    data-index={item.index}
                    data-level={row.level}
                    data-testid="factory-runs-terminal-row"
                    data-variant={row.id}
                    aria-current={current || undefined}
                    aria-posinset={item.index + 1}
                    aria-setsize={visibleRows.length}
                    role="listitem"
                  >
                    <span className="factory-terminal-time" title={row.dateTime}>
                      {row.dateTime ? <time dateTime={row.dateTime}>{row.timestamp}</time> : (row.timestamp ?? '—')}
                    </span>
                    <span className="factory-terminal-level" data-testid="factory-runs-terminal-row-level">
                      {text.levels[row.level]}
                    </span>
                    <div className="factory-terminal-message">
                      {onSeek && cursor !== undefined ? (
                        <button
                          type="button"
                          className="factory-terminal-seek"
                          data-testid="factory-runs-terminal-seek"
                          data-variant={row.id}
                          onClick={() => onSeek(cursor)}
                        >
                          {message}
                        </button>
                      ) : (
                        message
                      )}
                      {row.raw !== undefined && (
                        <>
                          <button
                            type="button"
                            className="factory-terminal-record-toggle"
                            aria-expanded={expanded}
                            data-testid="factory-runs-terminal-record-toggle"
                            data-variant={row.id}
                            onClick={() => setExpandedRecord(expanded ? undefined : row.id)}
                          >
                            {expanded ? text.hideRecord : text.showRecord}
                          </button>
                          {expanded && (
                            <code className="factory-terminal-record" data-testid="factory-runs-terminal-record">
                              {row.raw}
                            </code>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      ) : (
        <p
          className="factory-terminal-empty"
          data-testid="factory-runs-terminal-empty"
          data-variant={rows.length ? 'filtered' : 'empty'}
        >
          {rows.length ? text.noMatches : text.empty}
        </p>
      )}
    </section>
  );
}
