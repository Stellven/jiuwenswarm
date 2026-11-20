import type { EvidenceFile, JsonRecord } from './api';

export const asRecord = (value: unknown): JsonRecord =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonRecord) : {};

export const text = (value: unknown) => (typeof value === 'string' ? value : '');
export const rows = (value: unknown) => (Array.isArray(value) ? value.map(asRecord) : []);
const strings = (value: unknown) =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
const unique = (values: string[]) => [...new Set(values.filter(Boolean))];
const recordId = (record: JsonRecord) => text(record.obs_id) || text(record.artifact_id);
const cycleOf = (record: JsonRecord) => text(record.cycle_id) || text(record.iteration_id) || text(asRecord(record.cycle).cycle_id);
const revision = (value: unknown) => (typeof value === 'number' && Number.isSafeInteger(value) ? value : undefined);

type ArtifactKind = 'diff' | 'report' | 'analysis' | 'lab' | 'other';
export type IterationArtifact = { id: string; taskId: string; sha256: string; kind: ArtifactKind };
const refId = (value: unknown) => text(value) || text(asRecord(value).artifact_id);
const refIds = (value: unknown) => Array.isArray(value) ? value.map(refId) : [];
const capsuleNames = (value: unknown) =>
  Array.isArray(value) ? value.map((item) => text(item) || text(asRecord(item).id)) : [];

function artifactReferences(meta: JsonRecord): IterationArtifact[] {
  function reference(value: unknown, kind: ArtifactKind): IterationArtifact[] {
    const id = refId(value);
    return id ? [{ id, taskId: text(asRecord(value).task_id), sha256: text(asRecord(value).sha256), kind }] : [];
  }
  const work = asRecord(meta.do);
  const lab = asRecord(meta.lab);
  const analysis = asRecord(meta.analysis);
  return [
    ...reference(work.diff_artifact_id, 'diff'),
    ...[work.build_receipt_ids, work.verification_receipt_ids].flatMap((values) =>
      Array.isArray(values) ? values.flatMap((value) => reference(value, 'diff')) : []),
    ...(Array.isArray(lab.result_artifact_ids) ? lab.result_artifact_ids.flatMap((value) => reference(value, 'lab')) : []),
    ...(Array.isArray(analysis.output_artifact_ids) ? analysis.output_artifact_ids.flatMap((value) => reference(value, 'analysis')) : []),
    ...reference(meta.report, 'report'),
  ];
}

function fileKind(file: EvidenceFile): ArtifactKind {
  const name = `${file.path} ${file.display_path || ''} ${file.artifact_ids?.join(' ') || ''}`;
  if (/\.(?:diff|patch)(?:\s|@|$)|\b(?:source_diff|source-diff)\b/i.test(name)) return 'diff';
  if (/\breport(?:\b|_)|\bsummary\.md\b/i.test(name)) return 'report';
  if (/\banalysis\b|profil(?:e|ing)|phase[_ -]breakdown|attribution/i.test(name)) return 'analysis';
  if (/\bbench(?:mark)?\b|\bresult\b|\bmetrics\b/i.test(name)) return 'lab';
  return 'other';
}

export function buildIterations(records: Record<string, JsonRecord[]>, files: EvidenceFile[]) {
  const decisions = [...(records.decisions || [])].sort((a, b) => (revision(a.rev) || 0) - (revision(b.rev) || 0));
  const observations = records.observations || [];
  const artifacts = records.artifacts || [];
  const attempts = records.attempts || [];
  const cycles = new Map<string, JsonRecord>();
  for (const observation of observations) {
    const cycle = asRecord(asRecord(observation.values).cycle);
    const id = cycleOf(cycle);
    if (
      observation.kind === 'factory_loop' &&
      id &&
      (revision(cycle.event) ?? 0) >= (revision(cycles.get(id)?.event) ?? 0)
    ) {
      cycles.set(id, cycle);
    }
  }
  for (const item of records.factory_loop_cycles || []) {
    const cycle = asRecord(item.record);
    const id = cycleOf(item) || cycleOf(cycle);
    if (id) cycles.set(id, { ...cycle, cycle_id: id, number: item.number ?? cycle.number });
  }
  for (const decision of decisions) {
    const id = cycleOf(asRecord(decision.action));
    if (id && !cycles.has(id)) cycles.set(id, { cycle_id: id, decision_rev: decision.rev });
  }

  for (const observation of observations) {
    const meta = asRecord(observation.values);
    const id = text(meta.iteration_id);
    if (observation.kind !== 'factory_iteration_report' || meta.schema !== 'spark-factory-iteration/1' || !id) continue;
    cycles.set(id, { ...cycles.get(id), cycle_id: id, meta, metadata_observation: observation });
  }

  return [...cycles.values()]
    .sort(
      (a, b) =>
        (revision(a.number) ?? revision(a.decision_rev) ?? 0) - (revision(b.number) ?? revision(b.decision_rev) ?? 0),
    )
    .map((cycle, index, ordered) => {
      const id = cycleOf(cycle);
      const number = revision(cycle.number) ?? index + 1;
      const meta = asRecord(cycle.meta);
      const metaPlan = asRecord(meta.plan);
      const metadataObservation = asRecord(cycle.metadata_observation);
      const recordedPlanId = text(metaPlan.decision_id) || text(asRecord(metaPlan.decision_id).decision_id);
      const attached = artifactReferences(meta);
      const contract = asRecord(cycle.contract);
      const request = asRecord(cycle.request);
      const result = asRecord(cycle.result);
      const followup = asRecord(cycle.followup);
      const plan =
        decisions.find((decision) => recordedPlanId && decision.decision_id === recordedPlanId) ??
        decisions.find((decision) => decision.rev === cycle.decision_rev) ??
        decisions.find((decision) => cycleOf(asRecord(decision.action)) === id);
      const activeRev = revision(plan?.rev) ?? revision(cycle.decision_rev);
      const attemptId = text(cycle.attempt_id);
      const cycleAttempts = attempts.filter(
        (attempt) => cycleOf(attempt) === id || Boolean(attemptId && attempt.attempt_id === attemptId),
      );
      const scopedObservations = observations.filter(
        (observation) =>
          cycleOf(asRecord(observation.values)) === id ||
          Boolean(attemptId && asRecord(observation.host_run).attempt_id === attemptId),
      );
      const evidenceId = text(cycle.evidence_id);
      const report =
        observations.find((observation) => Boolean(evidenceId && observation.obs_id === evidenceId)) ??
        scopedObservations.find((observation) => observation.kind === 'factory_loop_result');
      const localTask = text(records.tasks?.[0]?.task_id);
      const reportRefs = attached.filter((ref) => ref.kind === 'report');
      const resultId = text(report?.obs_id) || evidenceId;
      const reportData = asRecord(report?.values ?? result.analysis);
      const rawArtifacts = rows(reportData.raw_artifacts);
      const linkedIds = new Set(
        unique([
          ...cycleAttempts.flatMap((attempt) => strings(attempt.result_refs)),
          ...scopedObservations.flatMap((observation) => strings(observation.source_artifacts)),
          ...strings(report?.source_artifacts),
          ...rawArtifacts.map(recordId),
          ...artifacts
            .filter((artifact) => cycleOf(artifact) === id || Boolean(attemptId && artifact.attempt_id === attemptId))
            .map(recordId),
        ]),
      );
      const localRefs = attached.filter((ref) => !ref.taskId || ref.taskId === localTask);
      const linkedFiles = files
        .filter((file) =>
          file.artifact_ids?.some(
            (artifact) =>
              localRefs.some((ref) => ref.id === artifact) || linkedIds.has(artifact) ||
              Boolean(revision(cycle.number) !== undefined && artifact.startsWith(`loop-artifact:${number}:`)) ||
              Boolean(attemptId && artifact.startsWith(`${attemptId}:`)),
          ),
        )
        .map((original) => {
          const ref = localRefs.find((entry) => original.artifact_ids?.includes(entry.id));
          const file: EvidenceFile = ref?.sha256 && original.sha256 !== ref.sha256 && original.integrity !== 'missing'
            ? { ...original, expected_sha256: ref.sha256, integrity: 'mismatch' } : original;
          return { file, kind: ref?.kind || fileKind(file) };
        });
      const relatedReports = new Set(
        unique([
          resultId,
          text(metadataObservation.obs_id),
          ...reportRefs.map((ref) => ref.id),
          text(report?.obs_id),
          ...scopedObservations
            .filter((observation) => /(?:^|[_-])report$/i.test(text(observation.kind)))
            .map(recordId),
          ...linkedFiles.filter((entry) => entry.kind === 'report').flatMap(({ file }) => file.artifact_ids || []),
        ]),
      );
      const nextPlan = asRecord(meta.next_plan);
      const explicitNextId = text(nextPlan.decision_id) || text(asRecord(nextPlan.decision_id).decision_id);
      const nextDecisions = decisions.flatMap((decision) => {
        const nextRev = revision(decision.rev);
        const explicit = Boolean(explicitNextId && decision.decision_id === explicitNextId);
        if (decision === plan || (!explicit && (nextRev === undefined || activeRev === undefined || nextRev <= activeRev))) return [];
        const cited = strings(decision.evidence_ids).filter((reference) => relatedReports.has(reference));
        if (!explicit && !cited.length) return [];
        return [{ decision, cited }];
      });
      const reportId = reportRefs[0]?.id || resultId;
      const linkedNext = ordered.slice(index + 1).find((candidate) => {
        const candidateMeta = asRecord(candidate.meta);
        const candidatePlan = asRecord(candidateMeta.plan);
        const incoming = [...refIds(candidatePlan.incoming_report_ids), ...refIds(candidateMeta.predecessor_report_ids)];
        return Boolean(
          (explicitNextId && candidatePlan.decision_id === explicitNextId) ||
          incoming.some((reference) => relatedReports.has(reference)),
        );
      });
      const remoteReferences = attached.filter((ref) =>
        !linkedFiles.some(({ file }) => file.artifact_ids?.includes(ref.id) && (!ref.taskId || ref.taskId === localTask)));
      const component = text(contract.component);
      const capsuleIds = unique([
        ...capsuleNames(metaPlan.builder_ccs),
        ...strings(cycle.capsules),
        ...strings(cycle.ccs),
        ...strings(asRecord(cycle.do).capsules),
        ...strings(request.capsules),
        ...strings(asRecord(plan?.action).capsules),
        text(asRecord(plan?.action).component),
        ...cycleAttempts.flatMap((attempt) => [
          text(attempt.component_cc),
          text(asRecord(attempt.resources).component_cc),
        ]),
      ]);
      return {
        id,
        number,
        plan,
        activeRev,
        attemptId,
        contract,
        report,
        reportData,
        resultId,
        reportId,
        linkedFiles,
        remoteReferences,
        metadataObservation,
        recordedPlanId,
        rationale: text(metaPlan.rationale),
        sourceCommit: text(asRecord(meta.do).source_commit),
        analysisCapsules: unique(capsuleNames(asRecord(meta.analysis).ccs)),
        explicitNextId,
        linkedNextId: cycleOf(linkedNext || {}),
        iterationStatus: text(asRecord(meta.report).status),
        nextDecisions,
        capsuleIds,
        component,
        followup,
        inputs: unique([...strings(plan?.evidence_ids ?? request.evidence_ids), ...refIds(metaPlan.incoming_report_ids), ...refIds(meta.predecessor_report_ids)]),
        state: text(cycle.state),
        template: text(asRecord(plan?.action).template_id) || text(request.template_id),
        childTask: text(cycle.child_task_id),
        operator: scopedObservations.some(
          (observation) =>
            observation.kind === 'operator_orchestration' && asRecord(observation.values).llm_agent === false,
        ),
        analysisObservations: scopedObservations.filter(
          (observation) =>
            /analysis|profil(?:e|ing)|attribution/i.test(text(observation.kind)) && observation !== report,
        ),
        labState: text(asRecord(meta.lab).status) || text(result.state) || text(cycleAttempts[0]?.status),
      };
    });
}

export type Iteration = ReturnType<typeof buildIterations>[number];
