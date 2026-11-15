import { useEffect, useMemo, useRef, useState } from 'react';
import JSZip from 'jszip';
import { factoryClient, parseCodeDiff, pretty } from './factoryClient';
import type {
  Artifact,
  CodeDiffArtifact,
  FactoryCatalog,
  FactoryEvent,
  FactoryNode,
  FactoryRun,
  WorkflowLibrary,
} from './factoryClient';
import { displayName, nodeOperationIdentity, productionPath, stageLabel, nodePoolRef } from './presentationModel';
import { edgeDeliveryStatus } from './graphLayout';
import { ExecutionLog } from './ExecutionLog';

function filename(artifact: Artifact): string {
  return artifact.path.split(/[\\/]/).pop() || artifact.id;
}

function sourceFilename(artifact: Artifact): string {
  const parts = artifact.path.split(/[\\/]/);
  return artifact.kind === 'construction.cmake' ? filename(artifact) : parts.slice(-2).join('/');
}

export function ArtifactList({
  runId,
  artifacts,
  recordingId,
}: {
  runId: string;
  artifacts: Artifact[];
  recordingId?: string;
}) {
  const [error, setError] = useState('');
  const objectUrls = useRef(new Set<string>());
  useEffect(() => {
    const urls = objectUrls.current;
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
      urls.clear();
    };
  }, []);

  const download = async (artifact: Artifact) => {
    try {
      setError('');
      const response = await factoryClient.artifact(runId, artifact.id, recordingId);
      const url = URL.createObjectURL(await response.blob());
      objectUrls.current.add(url);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename(artifact);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (failure) {
      setError(String(failure));
    }
  };

  return (
    <div className="wd-artifacts" data-testid="workflow-demo-artifacts">
      <ul className="wd-artifact-list" data-testid="workflow-demo-artifact-list">
        {artifacts.map((artifact) => (
          <li key={artifact.id} data-testid="workflow-demo-artifact" data-variant={artifact.id}>
            <a
              href={factoryClient.artifactUrl(runId, artifact.id, recordingId)}
              onClick={(event) => {
                event.preventDefault();
                void download(artifact);
              }}
              data-testid="workflow-demo-artifact-download"
              data-variant={artifact.id}
            >
              {filename(artifact)}
            </a>
            <span className="wd-artifact-kind" data-testid="workflow-demo-artifact-kind">
              {artifact.kind} · {artifact.size.toLocaleString()} bytes · {artifact.producer}
            </span>
            <code className="wd-artifact-path" data-testid="workflow-demo-artifact-path">
              {artifact.path}
            </code>
            <code className="wd-artifact-hash" data-testid="workflow-demo-artifact-hash">
              SHA-256 {artifact.sha256}
            </code>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="wd-error" data-testid="workflow-demo-artifact-error">
          {error}
        </p>
      )}
    </div>
  );
}

function useArtifactText(runId: string, artifact: Artifact | undefined, recordingId?: string) {
  const identity = artifact ? `${recordingId ?? 'live'}/${runId}/${artifact.id}/${artifact.sha256}` : '';
  const [result, setResult] = useState<{ identity: string; text?: string; error?: string } | null>(null);
  useEffect(() => {
    if (!artifact) return;
    const controller = new AbortController();
    void factoryClient
      .artifactText(runId, artifact.id, controller.signal, recordingId)
      .then((text) => {
        if (!controller.signal.aborted) setResult({ identity, text });
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setResult({ identity, error: String(failure) });
      });
    return () => controller.abort();
  }, [runId, artifact?.id, identity, recordingId]);
  return result?.identity === identity ? result : null;
}

function CodeDiffPanel({ run, recordingId }: { run: FactoryRun; recordingId?: string }) {
  const artifact = run.artifacts
    .slice()
    .reverse()
    .find((item) => item.kind === 'construction.code_diff');
  const result = useArtifactText(run.id, artifact, recordingId);
  const parsed = useMemo(() => {
    if (result?.text === undefined) return null;
    try {
      return { data: parseCodeDiff(result.text), error: '' };
    } catch (failure) {
      return { data: null as CodeDiffArtifact | null, error: String(failure) };
    }
  }, [result?.text]);
  const error = result?.error || parsed?.error;
  const files = parsed?.data?.files ?? [];
  const displayFiles =
    run.request.target_backend === 'ascend'
      ? [...files.filter((file) => file.target === 'ASCEND'), ...files.filter((file) => file.target !== 'ASCEND')]
      : files;
  return (
    <section className="wd-code-diff" data-testid="workflow-demo-code-diff" data-artifact={artifact?.id ?? ''}>
      <h3 data-testid="workflow-demo-code-diff-title">Code Diff</h3>
      {!artifact && (
        <p className="wd-empty" data-testid="workflow-demo-code-diff-empty">
          The source comparison has not been published at this event.
        </p>
      )}
      {artifact && !result && (
        <p className="wd-empty" data-testid="workflow-demo-code-diff-loading">
          Loading published source comparison…
        </p>
      )}
      {error && (
        <p className="wd-error" role="alert" data-testid="workflow-demo-code-diff-error">
          {error}
        </p>
      )}
      {displayFiles.map((file, index) => (
        <div
          className="wd-code-diff-grid"
          key={`${artifact?.id}/${file.source_path}/${index}`}
          data-testid="workflow-demo-code-diff-file"
          data-variant={file.generated_path}
        >
          <section className="wd-code-diff-pane" aria-label={`Original source: ${file.source_path}`}>
            <h4 data-testid="workflow-demo-code-diff-original-label">
              {/\.(cu|cuh)$/i.test(file.source_path) ? 'Original CUDA' : 'Original source'}
            </h4>
            <code className="wd-code-diff-path">{file.source_path}</code>
            <pre data-testid="workflow-demo-code-diff-original">
              <code>{file.source_code}</code>
            </pre>
          </section>
          <section className="wd-code-diff-pane" aria-label={`Generated C++: ${file.generated_path}`}>
            <h4 data-testid="workflow-demo-code-diff-generated-label">
              {file.target === 'ASCEND' ? 'Generated Ascend C++' : 'Generated CPU C++'}
            </h4>
            <code className="wd-code-diff-path">{file.generated_path}</code>
            <pre data-testid="workflow-demo-code-diff-generated">
              <code>{file.generated_code}</code>
            </pre>
          </section>
        </div>
      ))}
    </section>
  );
}

function SourcePanel({ run, recordingId }: { run: FactoryRun; recordingId?: string }) {
  const sources = run.artifacts.filter((artifact) =>
    [
      'construction.cpp',
      'construction.header',
      'construction.cmake',
      'construction.native_cpp',
      'construction.native_manifest',
    ].includes(artifact.kind),
  );
  const bundle = run.artifacts
    .slice()
    .reverse()
    .find((item) => item.kind === 'construction.native_sources');
  const nativeDiff =
    run.request.target_backend === 'ascend'
      ? run.artifacts
          .slice()
          .reverse()
          .find((item) => item.kind === 'construction.code_diff')
      : undefined;
  const nativeDiffResult = useArtifactText(run.id, nativeDiff, recordingId);
  const nativeDiffData = useMemo(() => {
    if (nativeDiffResult?.text === undefined) return null;
    try {
      return { data: parseCodeDiff(nativeDiffResult.text), error: '' };
    } catch (failure) {
      return { data: null, error: String(failure) };
    }
  }, [nativeDiffResult?.text]);
  const runIdentity = `${recordingId ?? 'live'}/${run.id}`;
  const bundleIdentity = bundle ? `${runIdentity}/${bundle.id}/${bundle.sha256}` : '';
  const [bundleResult, setBundleResult] = useState<{
    identity: string;
    entries?: { path: string; text: string }[];
    error?: string;
  } | null>(null);
  useEffect(() => {
    if (!bundle) return;
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await factoryClient.artifact(run.id, bundle.id, recordingId);
        const archive = await JSZip.loadAsync(await response.arrayBuffer(), { checkCRC32: true });
        const entries = await Promise.all(
          Object.values(archive.files)
            .filter((entry) => !entry.dir && /\.(cpp|h|hpp)$/i.test(entry.name))
            .map(async (entry) => ({ path: entry.name, text: await entry.async('string') })),
        );
        if (!controller.signal.aborted) setBundleResult({ identity: bundleIdentity, entries });
      } catch (failure) {
        if (!controller.signal.aborted) setBundleResult({ identity: bundleIdentity, error: String(failure) });
      }
    })();
    return () => controller.abort();
  }, [run.id, bundle?.id, bundleIdentity, recordingId]);
  const currentBundle = bundleResult?.identity === bundleIdentity ? bundleResult : null;
  const [selection, setSelection] = useState<{ runIdentity: string; id: string } | null>(null);
  const selected = selection?.runIdentity === runIdentity ? selection.id : '';
  const sourceLabel = (item: Artifact) => {
    const path = sourceFilename(item);
    if (item.kind === 'construction.cpp')
      return `${run.request.target_backend === 'ascend' ? 'CPU reference' : 'CPU source'} · ${path}`;
    if (item.kind === 'construction.native_cpp') return `Ascend source · ${path}`;
    return path;
  };
  const nativeMathPaths = new Set(
    nativeDiffData?.data?.files.filter((file) => file.target === 'ASCEND').map((file) => file.generated_path) ?? [],
  );
  const bundleEntries = (currentBundle?.entries ?? []).filter(
    (entry) => nativeMathPaths.has(entry.path) || !sources.some((item) => sourceFilename(item) === entry.path),
  );
  const bundleEntryKey = (path: string) => `bundle:${bundle?.id}:${path}`;
  const selectedArtifact = sources.find((item) => item.id === selected);
  const explicitEntry = bundleEntries.find((entry) => bundleEntryKey(entry.path) === selected);
  const resolveNativeDefault =
    run.request.target_backend === 'ascend' && !!bundle && !selectedArtifact && !explicitEntry;
  const nativeDefaultLoading = resolveNativeDefault && (!currentBundle || (!!nativeDiff && !nativeDiffResult));
  const nativeDiffError = nativeDiffResult?.error || nativeDiffData?.error;
  const nativeDefaultHeld =
    resolveNativeDefault && (nativeDefaultLoading || !!currentBundle?.error || !!nativeDiffError);
  const preferredNativeEntry = nativeDefaultHeld
    ? undefined
    : nativeDiffData?.data?.files
        .filter((file) => file.target === 'ASCEND')
        .map((file) => bundleEntries.find((entry) => entry.path === file.generated_path))
        .find((entry) => !!entry);
  const selectedEntry = explicitEntry ?? (resolveNativeDefault ? preferredNativeEntry : undefined);
  const artifact =
    selectedEntry || nativeDefaultHeld
      ? undefined
      : (selectedArtifact ??
        (run.request.target_backend === 'ascend'
          ? sources.find((item) => item.kind === 'construction.native_cpp')
          : undefined) ??
        sources[0]);
  const result = useArtifactText(run.id, artifact, recordingId);
  const selectedPath = selectedEntry?.path ?? (artifact ? sourceFilename(artifact) : '');
  return (
    <section className="wd-source" data-testid="workflow-demo-source">
      <div className="wd-panel-heading">
        <h3 data-testid="workflow-demo-source-title">Generated source</h3>
        {!!(sources.length || bundleEntries.length) && (
          <select
            aria-label="Generated source file"
            value={selectedEntry ? bundleEntryKey(selectedEntry.path) : (artifact?.id ?? '')}
            onChange={(event) => setSelection({ runIdentity, id: event.target.value })}
            data-testid="workflow-demo-source-file"
          >
            {!artifact && !selectedEntry && (
              <option value="" disabled data-testid="workflow-demo-source-file-pending">
                {nativeDefaultLoading ? 'Loading Ascend algorithm source…' : 'Select a published source file'}
              </option>
            )}
            {sources.map((item) => (
              <option
                key={item.id}
                value={item.id}
                data-testid="workflow-demo-source-file-option"
                data-variant={item.id}
              >
                {sourceLabel(item)}
              </option>
            ))}
            {bundleEntries.map((entry) => (
              <option
                key={bundleEntryKey(entry.path)}
                value={bundleEntryKey(entry.path)}
                data-testid="workflow-demo-source-file-option"
                data-variant={bundleEntryKey(entry.path)}
              >
                {/^(src\/ascend\/|include\/ascend)/.test(entry.path) ? 'Ascend source' : 'Bundle source'} · {entry.path}
              </option>
            ))}
          </select>
        )}
      </div>
      {nativeDefaultLoading && (
        <p className="wd-empty" data-testid="workflow-demo-source-loading">
          Loading published Ascend algorithm source…
        </p>
      )}
      {resolveNativeDefault && nativeDiffError && (
        <p className="wd-error" role="alert" data-testid="workflow-demo-source-diff-error">
          {nativeDiffError}
        </p>
      )}
      {!artifact && !selectedEntry && !nativeDefaultHeld && (
        <p className="wd-empty" data-testid="workflow-demo-source-empty">
          Generated files have not been published at this event.
        </p>
      )}
      {(artifact || selectedEntry) && (
        <>
          <code className="wd-source-path" data-testid="workflow-demo-source-path">
            {selectedPath}
          </code>
          {artifact && (
            <code className="wd-artifact-hash" data-testid="workflow-demo-source-hash">
              SHA-256 {artifact.sha256}
            </code>
          )}
          {selectedEntry && bundle && (
            <>
              <p data-testid="workflow-demo-source-bundle-origin">
                Published bundle: {filename(bundle)} · {selectedEntry.path}
              </p>
              <code className="wd-artifact-hash" data-testid="workflow-demo-source-bundle-hash">
                Bundle SHA-256 {bundle.sha256}
              </code>
            </>
          )}
          {artifact && !result && (
            <p className="wd-empty" data-testid="workflow-demo-source-loading">
              Loading published source…
            </p>
          )}
          {result?.error && (
            <p role="alert" className="wd-error" data-testid="workflow-demo-source-error">
              {result.error}
            </p>
          )}
          {artifact && result?.text !== undefined && (
            <pre className="wd-source-code" data-testid="workflow-demo-source-code" data-artifact={artifact.id}>
              <code>{result.text}</code>
            </pre>
          )}
          {selectedEntry && bundle && (
            <pre
              className="wd-source-code"
              data-testid="workflow-demo-source-code"
              data-artifact={bundle.id}
              data-entry={selectedEntry.path}
            >
              <code>{selectedEntry.text}</code>
            </pre>
          )}
        </>
      )}
      {bundle && !currentBundle && (
        <p className="wd-empty" data-testid="workflow-demo-source-bundle-loading">
          Loading source files from the published source bundle…
        </p>
      )}
      {currentBundle?.error && (
        <p className="wd-error" role="alert" data-testid="workflow-demo-source-bundle-error">
          {currentBundle.error}
        </p>
      )}
    </section>
  );
}

interface EvidenceReport {
  artifact: Artifact;
  data?: Record<string, unknown>;
  text?: string;
  error?: string;
}

const reportKinds = new Set([
  'construction.source',
  'construction.native_manifest',
  'construction.build',
  'construction.execution',
  'construction.portability',
  'construction.cpu_validation',
  'build.components',
  'verification.components',
  'implementation.generated',
  'implementation.checkout',
  'build.binary',
  'build.baseline',
  'inference.result',
  'inference.baseline',
  'verification.comparison',
  'environment.report',
]);

function flagRows(data: Record<string, unknown>, fields: string[]): [string, unknown][] {
  const result: [string, unknown][] = [];
  for (const field of fields) {
    if (Object.prototype.hasOwnProperty.call(data, field)) result.push([field, data[field]]);
  }
  return result;
}

function layerRows(data: Record<string, unknown>, fields: string[]): [string, unknown][] {
  if (!data.layers || typeof data.layers !== 'object' || Array.isArray(data.layers)) return [];
  return flagRows(data.layers as Record<string, unknown>, fields).map(([field, value]) => [`layers.${field}`, value]);
}

function EvidenceFlags({ rows }: { rows: [string, unknown][] }) {
  if (!rows.length) return null;
  return (
    <dl className="wd-evidence-flags" data-testid="workflow-demo-evidence-flags">
      {rows.map(([field, value]) => (
        <div key={field} data-testid="workflow-demo-evidence-flag" data-variant={field}>
          <dt>{field}</dt>
          <dd>{JSON.stringify(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function BuildPanel({ run, events, recordingId }: { run: FactoryRun; events: FactoryEvent[]; recordingId?: string }) {
  const artifacts = run.artifacts.filter((artifact) => reportKinds.has(artifact.kind));
  const identity = `${recordingId ?? 'live'}/${run.id}/${artifacts.map((item) => `${item.id}:${item.sha256}`).join('/')}`;
  const [result, setResult] = useState<{ identity: string; reports: EvidenceReport[] } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all(
      artifacts.map(async (artifact): Promise<EvidenceReport> => {
        try {
          const text = await factoryClient.artifactText(run.id, artifact.id, controller.signal, recordingId);
          const data: unknown = JSON.parse(text);
          if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Expected a report object');
          return { artifact, text, data: data as Record<string, unknown> };
        } catch (failure) {
          return { artifact, error: String(failure) };
        }
      }),
    ).then((reports) => {
      if (!controller.signal.aborted) setResult({ identity, reports });
    });
    return () => controller.abort();
  }, [identity, run.id, recordingId]);
  const current = result?.identity === identity ? result : null;
  const reports = current?.reports ?? [];
  const cpuFields = ['cpu_compilation_validated', 'independent_rebuild_validated', 'coverage_complete'];
  const nativeFields = [
    'source_generation',
    'native_compilation',
    'native_compilation_validated',
    'device_execution',
    'numerical_equivalence',
    'native_numerical_equivalence',
    'full_model',
    'native_device_validated',
    'full_inference_validated',
    'original_model_comparison_validated',
    'ascend_validated',
    'cuda_full_model_runtime_validated',
  ];
  const cpuRows = (data: Record<string, unknown>) => [
    ...flagRows(data, cpuFields),
    ...layerRows(data, ['source_implementation', 'host_compilation']),
  ];
  const nativeRows = (data: Record<string, unknown>) => [
    ...flagRows(data, nativeFields),
    ...layerRows(data, [
      'native_compilation',
      'device_loading',
      'operator_execution',
      'model_inference',
      'original_comparison',
    ]),
  ];
  const nativeAttempts = run.nodes.flatMap((node) =>
    node.attempts
      .filter(
        (attempt) =>
          attempt.error &&
          (/^strata\.(build_full|build_native|inference|compare|baseline_build|baseline_inference)$/.test(
            node.stage_id,
          ) ||
            (run.request.target_backend === 'ascend' && /^construction\.(build|execute)$/.test(node.stage_id))),
      )
      .map((attempt) => ({ node, attempt })),
  );
  const output = events.filter((event) => event.type === 'command.output');
  return (
    <section className="wd-build-evidence" data-testid="workflow-demo-build-evidence">
      <h3 data-testid="workflow-demo-build-title">Build &amp; verification</h3>
      <section className="wd-evidence-scope" data-testid="workflow-demo-cpu-evidence">
        <h4 data-testid="workflow-demo-cpu-evidence-title">Source and CPU validation</h4>
        {reports.map((report) => {
          const rows = report.data ? cpuRows(report.data) : [];
          return rows.length ? (
            <div key={report.artifact.id} data-testid="workflow-demo-cpu-report" data-variant={report.artifact.id}>
              <code>{report.artifact.kind}</code>
              <EvidenceFlags rows={rows} />
              {report.data?.schema === 'strata.cpu.reference.validation.v1' &&
                !!report.data.cpu_numerical_validation &&
                typeof report.data.cpu_numerical_validation === 'object' && (
                  <section className="wd-cpu-reference-summary" data-testid="workflow-demo-cpu-reference-summary">
                    <h4>CPU reference comparisons</h4>
                    <EvidenceFlags
                      rows={Object.entries(report.data.cpu_numerical_validation as Record<string, unknown>)}
                    />
                    {Array.isArray(report.data.operation_coverage) && (
                      <table data-testid="workflow-demo-cpu-operation-results">
                        <thead>
                          <tr>
                            <th>Source function</th>
                            <th>Result</th>
                            <th>Comparisons</th>
                          </tr>
                        </thead>
                        <tbody>
                          {report.data.operation_coverage.map((value: Record<string, unknown>, index: number) => (
                            <tr key={String(value.source_id || index)}>
                              <td>{String(value.name || value.source_id || '')}</td>
                              <td>{String(value.status || '')}</td>
                              <td>{String(value.built_in_comparisons ?? '')}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </section>
                )}
            </div>
          ) : null;
        })}
        {!artifacts.some((artifact) =>
          /^(construction|build\.components|verification\.components)/.test(artifact.kind),
        ) && (
          <p className="wd-empty" data-testid="workflow-demo-cpu-evidence-empty">
            No source or CPU validation report is published at this event.
          </p>
        )}
      </section>
      <section className="wd-evidence-scope" data-testid="workflow-demo-native-evidence">
        <h4 data-testid="workflow-demo-native-evidence-title">Ascend device, model and original comparison</h4>
        {reports.map((report) => {
          const rows = report.data ? nativeRows(report.data) : [];
          const nativeGeneration = report.data?.native_generation;
          if (!rows.length && nativeGeneration === undefined) return null;
          return (
            <div key={report.artifact.id} data-testid="workflow-demo-native-report" data-variant={report.artifact.id}>
              <code>{report.artifact.kind}</code>
              <EvidenceFlags rows={rows} />
              {nativeGeneration !== undefined && (
                <section className="wd-native-generation" data-testid="workflow-demo-native-generation">
                  <h4 data-testid="workflow-demo-native-generation-title">Generated native source</h4>
                  <pre data-testid="workflow-demo-native-generation-content">{pretty(nativeGeneration)}</pre>
                </section>
              )}
            </div>
          );
        })}
        {nativeAttempts.map(({ node, attempt }) => (
          <section
            key={`${node.id}/${attempt.number}`}
            className="wd-native-attempt"
            data-testid="workflow-demo-native-attempt"
            data-variant={`${node.id}/${attempt.number}`}
          >
            <h4>{node.name}</h4>
            <p>
              {node.stage_id} · {attempt.status}
            </p>
            <pre data-testid="workflow-demo-native-error">{pretty(attempt.error)}</pre>
          </section>
        ))}
        {!reports.some(
          (report) => report.data && (nativeRows(report.data).length || report.data.native_generation !== undefined),
        ) &&
          !nativeAttempts.length && (
            <p className="wd-empty" data-testid="workflow-demo-native-evidence-empty">
              No device or model validation evidence is published at this event.
            </p>
          )}
      </section>
      {artifacts.length > 0 && !current && (
        <p className="wd-empty" data-testid="workflow-demo-build-loading">
          Loading published verification reports…
        </p>
      )}
      {reports.map((report) => (
        <section
          key={report.artifact.id}
          className="wd-verification-report"
          data-testid="workflow-demo-verification-report"
          data-variant={report.artifact.id}
        >
          <h4>{report.artifact.kind}</h4>
          {report.error ? (
            <p role="alert" className="wd-error" data-testid="workflow-demo-verification-report-error">
              {report.error}
            </p>
          ) : (
            <pre data-testid="workflow-demo-verification-report-content">{report.text}</pre>
          )}
        </section>
      ))}
      {output.length > 0 && (
        <section className="wd-terminal" data-testid="workflow-demo-terminal">
          <h3 data-testid="workflow-demo-terminal-title">Terminal</h3>
          <pre data-testid="workflow-demo-terminal-content">
            {output
              .map((event) => `[${event.node_id} ${String(event.payload.stream)}] ${String(event.payload.text ?? '')}`)
              .join('')}
          </pre>
        </section>
      )}
    </section>
  );
}

function ValuePanel({ run, recordingId }: { run: FactoryRun; recordingId?: string }) {
  const artifact = run.artifacts
    .slice()
    .reverse()
    .find((item) => item.kind === 'value.report');
  const result = useArtifactText(run.id, artifact, recordingId);
  return (
    <section className="wd-value-report" data-testid="workflow-demo-value-report" data-artifact={artifact?.id ?? ''}>
      <h3 data-testid="workflow-demo-value-report-title">Value Report</h3>
      {!artifact && (
        <p className="wd-empty" data-testid="workflow-demo-value-report-empty">
          The value report has not been published at this event.
        </p>
      )}
      {artifact && !result && (
        <p className="wd-empty" data-testid="workflow-demo-value-report-loading">
          Loading published value report…
        </p>
      )}
      {result?.error && (
        <p className="wd-error" role="alert" data-testid="workflow-demo-value-report-error">
          {result.error}
        </p>
      )}
      {result?.text !== undefined && <pre data-testid="workflow-demo-value-report-content">{result.text}</pre>}
    </section>
  );
}

function originLabels(node: FactoryNode, catalog: FactoryCatalog | null, library?: WorkflowLibrary | null) {
  const parts = nodePoolRef(node).split('/');
  const workflowId = parts[0] || node.workflow_id;
  const subworkflowId = parts[1] || node.subworkflow_id;
  const workflow = library?.workflows.find((item) => item.id === workflowId);
  const instance = workflow?.subworkflows.find((item) => item.id === subworkflowId);
  const definition = instance && library?.subworkflows.find((item) => item.id === instance.definition);
  const workflowName =
    workflow?.name || catalog?.groups.find((item) => item.id === workflowId)?.name || displayName(workflowId);
  const subworkflowName =
    definition?.name ||
    catalog?.subworkflows.find((item) => item.workflow_id === workflowId && item.id === subworkflowId)?.name ||
    displayName(subworkflowId);
  return {
    workflowId,
    workflowName,
    subworkflowName,
    full: `${workflowName} / ${subworkflowName} / ${stageLabel(node)}`,
  };
}

function InternalExtraction({
  run,
  catalog,
  onSelectNode,
  library,
}: {
  run: FactoryRun;
  catalog: FactoryCatalog | null;
  onSelectNode: (id: string) => void;
  library?: WorkflowLibrary | null;
}) {
  const rows = run.edges.flatMap((input) => {
    if (input.data !== 'source.operator') return [];
    const source = run.nodes.find((node) => node.id === input.from);
    const inner = run.nodes.find((node) => node.id === input.to);
    if (!source || !inner || !nodePoolRef(inner)) return [];
    const output = run.edges.find((edge) => edge.from === inner.id && edge.data === 'core.lowered');
    const destination = output && run.nodes.find((node) => node.id === output.to);
    return [{ input, source, inner, output, destination }];
  });
  if (!rows.length) return null;
  const origin = (node: FactoryNode) =>
    library
      ? originLabels(node, catalog, library).full
      : nodePoolRef(node)
        ? nodePoolRef(node).split('/').map(displayName).join(' / ')
        : originLabels(node, catalog).full;
  const button = (node: FactoryNode) => (
    <button
      type="button"
      className="wd-internal-stage"
      onClick={() => onSelectNode(node.id)}
      data-testid="workflow-demo-internal-stage"
      data-variant={node.id}
    >
      <span>{origin(node)}</span>
      <strong>{stageLabel(node)}</strong>
    </button>
  );
  const arrow = (edge: FactoryRun['edges'][number]) => (
    <span
      className="wd-production-edge"
      data-testid="workflow-demo-internal-edge"
      data-from={edge.from}
      data-to={edge.to}
      data-delivery={edgeDeliveryStatus(edge, run.nodes, run.artifacts)}
    >
      →
    </span>
  );
  return (
    <section className="wd-internal-extraction" data-testid="workflow-demo-internal-extraction">
      <h3>Extracted internal stages</h3>
      <p>Existing workflow / sub-workflow / internal stage</p>
      {rows.map(({ input, source, inner, output, destination }) => {
        const operation = nodeOperationIdentity(inner, run) || nodeOperationIdentity(source, run);
        return (
          <section
            className="wd-internal-row"
            key={inner.id}
            data-testid="workflow-demo-internal-row"
            data-variant={inner.id}
          >
            {operation && <p data-testid="workflow-demo-internal-operation">{operation}</p>}
            <div className="wd-internal-flow">
              {button(source)}
              {arrow(input)}
              {button(inner)}
              {output && destination && (
                <>
                  {arrow(output)}
                  {button(destination)}
                </>
              )}
            </div>
          </section>
        );
      })}
    </section>
  );
}

function ProductionChain({
  run,
  catalog,
  selected,
  onSelectNode,
  library,
}: {
  run: FactoryRun;
  catalog: FactoryCatalog | null;
  selected: string;
  onSelectNode: (id: string) => void;
  library?: WorkflowLibrary | null;
}) {
  const path = productionPath(run);
  if (!path.nodes.length) return null;
  const groups: { id: string; nodes: FactoryNode[] }[] = [];
  const parentId = (node: FactoryNode) => nodePoolRef(node).split('/')[0] || node.workflow_id;
  for (const node of path.nodes) {
    const previous = groups[groups.length - 1];
    if (previous?.id === parentId(node)) previous.nodes.push(node);
    else groups.push({ id: parentId(node), nodes: [node] });
  }
  const parentName = (id: string) =>
    library?.workflows.find((item) => item.id === id)?.name ||
    catalog?.groups.find((item) => item.id === id)?.name ||
    displayName(id);
  const subworkflowName = (node: FactoryNode) => originLabels(node, catalog, library).subworkflowName;
  const origin = (node: FactoryNode) =>
    library
      ? originLabels(node, catalog, library).full
      : nodePoolRef(node)
        ? nodePoolRef(node).split('/').map(displayName).join(' / ')
        : originLabels(node, catalog).full;
  const rawOrigin = (node: FactoryNode) =>
    `${node.workflow_id} / ${node.subworkflow_id} / ${node.stage_id}${node.workflow_path ? `\n${node.workflow_path}` : ''}`;
  const operationName = (node: FactoryNode) => nodeOperationIdentity(node, run)?.split(':').pop();
  const pathOperations = new Set(path.nodes.map((node) => nodeOperationIdentity(node, run)).filter(Boolean));
  const branches = new Map<string, FactoryNode>();
  for (const node of path.ancestors) {
    const operation = nodeOperationIdentity(node, run);
    if (operation && !pathOperations.has(operation) && (!branches.has(operation) || node.stage_id.startsWith('lower.')))
      branches.set(operation, node);
  }
  const edge = (from: FactoryNode, to: FactoryNode) => {
    const recorded = run.edges.find((item) => item.from === from.id && item.to === to.id);
    if (!recorded) return null;
    return (
      <span
        className="wd-production-edge"
        data-testid="workflow-demo-production-edge"
        data-from={from.id}
        data-to={to.id}
        data-delivery={edgeDeliveryStatus(recorded, run.nodes, run.artifacts)}
      >
        →
      </span>
    );
  };
  return (
    <section className="wd-production" data-testid="workflow-demo-production-chain">
      <h3 data-testid="workflow-demo-production-title">Production chain</h3>
      <p data-testid="workflow-demo-production-scope">
        Actual internal-stage dependency path to {path.endpoint ? filename(path.endpoint) : 'the published artifact'}
      </p>
      <ol className="wd-production-groups">
        {groups.map((group, groupIndex) => {
          const next = groups[groupIndex + 1];
          return (
            <li
              key={`${group.id}/${groupIndex}`}
              className="wd-production-group"
              data-testid="workflow-demo-production-parent"
              data-variant={group.id}
            >
              <h4>
                {groupIndex + 1}. {parentName(group.id)}
              </h4>
              <div className="wd-production-steps">
                {group.nodes.map((node, index) => (
                  <span key={node.id}>
                    {index > 0 && edge(group.nodes[index - 1], node)}
                    <button
                      type="button"
                      onClick={() => onSelectNode(node.id)}
                      aria-label={`${origin(node)}\n${rawOrigin(node)}\n${nodeOperationIdentity(node, run) || node.name}`}
                      aria-pressed={selected === node.id}
                      data-testid="workflow-demo-production-step"
                      data-variant={node.id}
                    >
                      <span className="wd-production-step-subworkflow">{subworkflowName(node)}</span>
                      <strong className="wd-production-step-name">{stageLabel(node)}</strong>
                      {operationName(node) && <span>{operationName(node)}</span>}
                    </button>
                  </span>
                ))}
              </div>
              {group.nodes.some((node) => node.id === selected) && (
                <p className="wd-production-origin" data-testid="workflow-demo-production-origin">
                  {origin(group.nodes.find((node) => node.id === selected)!)}
                </p>
              )}
              {next && (
                <div className="wd-production-next">
                  {edge(group.nodes[group.nodes.length - 1], next.nodes[0])}
                  <span>{parentName(next.id)}</span>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {!!branches.size && (
        <div className="wd-production-branches" data-testid="workflow-demo-production-branches">
          <h4>Additional input branches</h4>
          {[...branches].map(([operation, node]) => (
            <button
              type="button"
              key={operation}
              onClick={() => onSelectNode(node.id)}
              aria-label={`${origin(node)}\n${rawOrigin(node)}\n${operation}`}
              data-testid="workflow-demo-production-branch"
              data-variant={node.id}
            >
              {parentName(parentId(node))} / {subworkflowName(node)} / {stageLabel(node)} · {operation.split(':').pop()}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function CompositionPanel({
  run,
  catalog,
  selected,
  onSelectNode,
  library,
  recordingId,
}: {
  run: FactoryRun;
  catalog: FactoryCatalog | null;
  selected: string;
  onSelectNode: (id: string) => void;
  library?: WorkflowLibrary | null;
  recordingId?: string;
}) {
  const lineage = (node: FactoryNode) => {
    if (library) {
      const labels = originLabels(node, catalog, library);
      return `${labels.workflowName} / ${labels.subworkflowName}`;
    }
    const reference = nodePoolRef(node);
    if (reference) return reference.split('/').slice(0, 2).map(displayName).join(' / ');
    const parent = catalog?.groups.find((item) => item.id === node.workflow_id);
    const subworkflow = catalog?.subworkflows.find(
      (item) => item.id === node.subworkflow_id && item.workflow_id === node.workflow_id,
    );
    return `${parent?.name || displayName(node.workflow_id)} / ${subworkflow?.name || displayName(node.subworkflow_id)}`;
  };
  const connections = run.edges.flatMap((edge) => {
    const from = run.nodes.find((node) => node.id === edge.from);
    const to = run.nodes.find((node) => node.id === edge.to);
    return from &&
      to &&
      originLabels(from, catalog, library).workflowId !== originLabels(to, catalog, library).workflowId
      ? [{ edge, from, to }]
      : [];
  });
  const sourceOutputs = run.artifacts.filter((artifact) =>
    ['construction.cpp', 'construction.native_cpp', 'construction.package', 'construction.native_sources'].includes(
      artifact.kind,
    ),
  );
  const nodeButton = (node: FactoryNode) => {
    const operation = nodeOperationIdentity(node, run);
    const separator = operation?.lastIndexOf(':') ?? -1;
    return (
      <button
        type="button"
        className="wd-composition-stage"
        aria-label={`${lineage(node)} / ${node.name}\n${node.workflow_id} / ${node.subworkflow_id} / ${node.stage_id}${node.workflow_path ? `\n${node.workflow_path}` : ''}`}
        aria-pressed={selected === node.id}
        onClick={() => onSelectNode(node.id)}
        data-testid="workflow-demo-composition-stage"
        data-variant={node.id}
      >
        <span className="wd-composition-parent">{lineage(node)}</span>
        <span>{node.name}</span>
        {operation && (
          <span className="wd-composition-operation" data-testid="workflow-demo-composition-operation">
            <span>{separator >= 0 ? operation.slice(separator + 1) : operation}</span>
            {separator >= 0 && <code>{operation.slice(0, separator)}</code>}
          </span>
        )}
      </button>
    );
  };

  return (
    <section className="wd-composition" data-testid="workflow-demo-composition">
      {!run.artifacts.some((artifact) =>
        ['construction.package', 'construction.native_sources'].includes(artifact.kind),
      ) && <InternalExtraction run={run} catalog={catalog} onSelectNode={onSelectNode} library={library} />}
      <ProductionChain run={run} catalog={catalog} selected={selected} onSelectNode={onSelectNode} library={library} />
      {!!sourceOutputs.length && (
        <section className="wd-composition-output" data-testid="workflow-demo-composition-outputs">
          <h3 data-testid="workflow-demo-composition-output-title">Published source and ZIP</h3>
          <ArtifactList runId={run.id} artifacts={sourceOutputs} recordingId={recordingId} />
        </section>
      )}
      <h3 data-testid="workflow-demo-composition-title">All cross-workflow handoffs</h3>

      {!connections.length && (
        <p className="wd-empty" data-testid="workflow-demo-composition-empty">
          No cross-workflow handoff is recorded at this event.
        </p>
      )}
      <ol className="wd-composition-handoffs" data-testid="workflow-demo-composition-handoffs">
        {connections.map(({ edge, from, to }, index) => (
          <li
            key={`${from.id}/${to.id}/${index}`}
            className="wd-composition-handoff"
            data-testid="workflow-demo-composition-handoff"
            data-variant={`${from.id}/${to.id}/${index}`}
            data-from={from.id}
            data-to={to.id}
            data-delivery={edgeDeliveryStatus(edge, run.nodes, run.artifacts)}
          >
            {nodeButton(from)}
            <span className="wd-composition-arrow" aria-hidden="true">
              →
            </span>
            {nodeButton(to)}
            <div className="wd-composition-artifact">
              <span data-testid="workflow-demo-composition-receipt">
                {
                  { verified: 'Consumed', running: 'Consuming', failed: 'Failed', pending: 'Awaiting input' }[
                    edgeDeliveryStatus(edge, run.nodes, run.artifacts)
                  ]
                }
              </span>
              <span>{displayName(edge.data)}</span>
            </div>
          </li>
        ))}
      </ol>

      <h3 data-testid="workflow-demo-composition-selected-title">Extracted internal stages</h3>
      <div className="wd-composition-selected" data-testid="workflow-demo-composition-selected">
        {run.nodes.map((node) => (
          <div key={node.id} data-testid="workflow-demo-composition-selected-stage" data-variant={node.id}>
            {nodeButton(node)}
          </div>
        ))}
      </div>
    </section>
  );
}

const tabs = [
  { id: 'composition', label: 'Composition' },
  { id: 'diff', label: 'Code Diff' },
  { id: 'source', label: 'Source' },
  { id: 'log', label: 'Run log' },
  { id: 'build', label: 'Build & verification' },
  { id: 'downloads', label: 'Downloads' },
  { id: 'value', label: 'Value' },
  { id: 'request', label: 'Request' },
] as const;

export function EvidencePanel({
  run,
  events,
  recordingId,
  catalog,
  selected,
  onSelectNode,
  library,
}: {
  run: FactoryRun | null;
  events: FactoryEvent[];
  recordingId?: string;
  catalog: FactoryCatalog | null;
  selected: string;
  onSelectNode: (id: string) => void;
  library?: WorkflowLibrary | null;
}) {
  const [tab, setTab] = useState<(typeof tabs)[number]['id']>('composition');
  const downloads = (run?.artifacts ?? [])
    .slice()
    .sort(
      (first, second) => Number(second.kind === 'construction.package') - Number(first.kind === 'construction.package'),
    );
  return (
    <section className="wd-evidence" data-testid="workflow-demo-evidence">
      <div
        className="wd-evidence-tabs"
        role="tablist"
        aria-label="Published evidence"
        data-testid="workflow-demo-evidence-tabs"
      >
        {tabs.map((item) => (
          <button
            type="button"
            role="tab"
            key={item.id}
            aria-selected={tab === item.id}
            aria-controls={`factory-evidence-${item.id}`}
            id={`factory-evidence-tab-${item.id}`}
            onClick={() => setTab(item.id)}
            data-testid="workflow-demo-evidence-tab"
            data-variant={item.id}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div
        className="wd-evidence-content"
        role="tabpanel"
        id={`factory-evidence-${tab}`}
        aria-labelledby={`factory-evidence-tab-${tab}`}
        data-testid="workflow-demo-evidence-content"
        data-variant={tab}
      >
        {!run && (
          <p className="wd-empty" data-testid="workflow-demo-evidence-empty">
            Select a recorded task or construct STRATA to inspect published evidence.
          </p>
        )}
        {run && tab === 'diff' && <CodeDiffPanel run={run} recordingId={recordingId} />}
        {run && tab === 'composition' && (
          <CompositionPanel
            run={run}
            catalog={catalog}
            selected={selected}
            onSelectNode={onSelectNode}
            recordingId={recordingId}
            library={library}
          />
        )}
        {run && tab === 'source' && <SourcePanel run={run} recordingId={recordingId} />}
        {run && tab === 'log' && (
          <ExecutionLog run={run} events={events} recordingId={recordingId} onSelectNode={onSelectNode} />
        )}
        {run && tab === 'build' && <BuildPanel run={run} events={events} recordingId={recordingId} />}
        {run && tab === 'downloads' && (
          <section className="wd-deliveries" data-testid="workflow-demo-deliverables">
            <h3 data-testid="workflow-demo-downloads-title">Published downloads</h3>
            {downloads.length ? (
              <ArtifactList runId={run.id} artifacts={downloads} recordingId={recordingId} />
            ) : (
              <p className="wd-empty" data-testid="workflow-demo-downloads-empty">
                No artifacts are published at this event.
              </p>
            )}
          </section>
        )}
        {run && tab === 'value' && <ValuePanel run={run} recordingId={recordingId} />}
        {run && tab === 'request' && (
          <section className="wd-recorded-request" data-testid="workflow-demo-recorded-request">
            <h3 data-testid="workflow-demo-recorded-request-title">Actual task request</h3>
            <pre data-testid="workflow-demo-recorded-request-content">{pretty(run.request)}</pre>
          </section>
        )}
      </div>
    </section>
  );
}
