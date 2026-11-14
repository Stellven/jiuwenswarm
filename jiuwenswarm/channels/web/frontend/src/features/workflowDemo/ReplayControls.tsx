import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '../../components/ui/Button/Button';
import type { FactoryEvent } from './factoryClient';
import { eventOffset, replayDuration } from './replayProjection.js';

interface ReplayControlsProps {
  runId: string;
  recordedTime: string | null;
  events: FactoryEvent[];
  cursor: number;
  onCursorChange: (cursor: number) => void;
  onReturnLive: () => void;
}

export function ReplayControls({
  runId,
  recordedTime,
  events,
  cursor,
  onCursorChange,
  onReturnLive,
}: ReplayControlsProps) {
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const eventOffsets = useMemo(() => events.map((_, index) => eventOffset(events, index)), [events]);
  const cursorRef = useRef(cursor);
  useEffect(() => {
    cursorRef.current = cursor;
  }, [cursor]);

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let previousTime: number | null = null;
    let elapsed = cursorRef.current ? eventOffsets[cursorRef.current - 1] : 0;
    const duration = replayDuration(events);
    const tick = (time: number) => {
      if (previousTime !== null) elapsed += (time - previousTime) * speed;
      previousTime = time;
      let next = cursorRef.current;
      while (next < events.length && eventOffsets[next] <= elapsed) next += 1;
      if (next !== cursorRef.current) {
        cursorRef.current = next;
        onCursorChange(next);
      }
      if (next >= events.length || elapsed > duration) setPlaying(false);
      else frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, events, eventOffsets, onCursorChange]);

  const seek = (next: number) => {
    setPlaying(false);
    onCursorChange(Math.max(0, Math.min(events.length, next)));
  };
  const step = (direction: -1 | 1) => {
    const isStage = (event: FactoryEvent) => /^stage\.(started|verified|failed|blocked)$/.test(event.type);
    if (direction < 0) {
      for (let index = cursor - 2; index >= 0; index -= 1) {
        if (isStage(events[index])) return seek(index + 1);
      }
      seek(0);
    } else {
      for (let index = cursor; index < events.length; index += 1) {
        if (isStage(events[index])) return seek(index + 1);
      }
      seek(events.length);
    }
  };

  return (
    <section className="wd-replay-controls" data-testid="workflow-demo-replay-controls">
      <div className="wd-replay-metadata">
        <strong data-testid="workflow-demo-replay-label">Replay</strong>
        <code data-testid="workflow-demo-run-id">{runId}</code>
        <time dateTime={recordedTime ?? undefined} data-testid="workflow-demo-replay-recorded-time">
          {recordedTime ?? '—'}
        </time>
      </div>
      <input
        type="range"
        min={0}
        max={events.length}
        step={1}
        value={cursor}
        onChange={(event) => seek(Number(event.target.value))}
        aria-label="Recorded event timeline"
        aria-valuetext={`${cursor} of ${events.length} recorded events`}
        data-testid="workflow-demo-replay-timeline"
      />
      <div className="wd-replay-buttons">
        <Button
          size="sm"
          disabled={cursor === 0}
          onClick={() => step(-1)}
          data-testid="workflow-demo-replay-previous-stage"
        >
          Back stage
        </Button>
        <Button
          size="sm"
          disabled={cursor === 0}
          onClick={() => seek(cursor - 1)}
          data-testid="workflow-demo-replay-previous-event"
        >
          Back event
        </Button>
        <Button
          size="sm"
          disabled={events.length === 0 || (!playing && cursor >= events.length)}
          onClick={() => setPlaying((value) => !value)}
          aria-pressed={playing}
          data-testid="workflow-demo-replay-play-pause"
        >
          {playing ? 'Pause' : 'Play'}
        </Button>
        <Button
          size="sm"
          disabled={cursor >= events.length}
          onClick={() => seek(cursor + 1)}
          data-testid="workflow-demo-replay-next-event"
        >
          Next event
        </Button>
        <Button
          size="sm"
          disabled={cursor >= events.length}
          onClick={() => step(1)}
          data-testid="workflow-demo-replay-next-stage"
        >
          Next stage
        </Button>
        <select
          value={speed}
          onChange={(event) => setSpeed(Number(event.target.value))}
          aria-label="Replay speed"
          data-testid="workflow-demo-replay-speed"
        >
          {[1, 4, 16].map((value) => (
            <option value={value} key={value}>
              {value}x
            </option>
          ))}
        </select>
        <Button size="sm" onClick={onReturnLive} data-testid="workflow-demo-replay-return-live">
          Return to live
        </Button>
        <Button size="sm" disabled data-testid="workflow-demo-run-button">
          Construct STRATA
        </Button>
      </div>
    </section>
  );
}
