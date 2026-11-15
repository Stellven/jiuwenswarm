import { Button } from '../../components/ui/Button/Button';
import type { FactoryEvent } from './factoryClient';
import type { ReplayCheckpoint } from './presentationModel';

interface ReplayControlsProps {
  runId: string;
  recordedTime: string | null;
  events: FactoryEvent[];
  cursor: number;
  onCursorChange: (cursor: number) => void;
  onPlay: (speed: number) => void;
  onPause: () => void;
  playing: boolean;
  canPlay?: boolean;
  playbackSpeed: number;
  onSpeedChange: (speed: number) => void;
  onReturnLive: () => void;
  returnLabel?: string;
  checkpoints: ReplayCheckpoint[];
}

export function ReplayControls({
  runId,
  recordedTime,
  events,
  cursor,
  onCursorChange,
  onPlay,
  onPause,
  playing,
  canPlay = true,
  playbackSpeed,
  onSpeedChange,
  onReturnLive,
  returnLabel = 'Return to live',
  checkpoints,
}: ReplayControlsProps) {
  const currentCheckpoint = checkpoints.filter((checkpoint) => checkpoint.cursor <= cursor).slice(-1)[0];
  const seek = (next: number) => {
    onPause();
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
        <label htmlFor="factory-checkpoint" data-testid="workflow-demo-checkpoint-label">
          Checkpoint
        </label>
        <select
          id="factory-checkpoint"
          value={currentCheckpoint?.cursor ?? ''}
          onChange={(event) => seek(Number(event.target.value))}
          data-testid="workflow-demo-replay-checkpoint"
        >
          <option value="">Start</option>
          {checkpoints.map((checkpoint) => (
            <option key={checkpoint.sequence} value={checkpoint.cursor}>
              {checkpoint.label}
            </option>
          ))}
        </select>
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
          disabled={!playing && (!canPlay || events.length === 0 || cursor >= events.length)}
          onClick={() => (playing ? onPause() : onPlay(playbackSpeed))}
          aria-pressed={playing}
          data-testid="workflow-demo-replay-play-pause"
        >
          {playing ? 'Pause' : cursor === 0 ? 'Start walkthrough' : 'Continue'}
        </Button>
        <select
          value={playbackSpeed}
          onChange={(event) => {
            onPause();
            onSpeedChange(Number(event.target.value));
          }}
          aria-label="Replay speed"
          data-testid="workflow-demo-replay-speed"
        >
          {[1, 4, 16].map((speed) => (
            <option key={speed} value={speed} data-testid="workflow-demo-replay-speed-option" data-variant={speed}>
              {speed}x
            </option>
          ))}
        </select>
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
        <Button
          size="sm"
          disabled={cursor >= events.length}
          onClick={() => seek(events.length)}
          data-testid="workflow-demo-replay-result"
        >
          Final result
        </Button>
        <Button
          size="sm"
          onClick={() => {
            onPause();
            onReturnLive();
          }}
          data-testid="workflow-demo-replay-return-live"
        >
          {returnLabel}
        </Button>
      </div>
    </section>
  );
}
