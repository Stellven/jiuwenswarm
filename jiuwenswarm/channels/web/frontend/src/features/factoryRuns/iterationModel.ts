import type { EvidenceFile, JsonRecord } from './api';

export const asRecord = (value: unknown): JsonRecord =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonRecord) : {};

export const text = (value: unknown) => (typeof value === 'string' ? value : '');
export const rows = (value: unknown) => (Array.isArray(value) ? value.map(asRecord) : []);
const strings = (value: unknown) =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
const unique = (values: string[]) => [...new Set(values.filter(Boolean))];
const recordId = (record: JsonRecord) => text(record.obs_id) || text(record.artifact_id);
const cycleOf = (record: JsonRecord) =>
  text(record.cycle_id) || text(record.iteration_id) || text(asRecord(record.cycle).cycle_id);
const decisionId = (value: unknown) => text(value) || text(asRecord(value).decision_id);
const decisionTask = (value: unknown) =>
  text(asRecord(value).task_id) || /^(.*):decision:\d+$/.exec(decisionId(value))?.[1] || '';
const timestamp = (value: unknown) => (typeof value === 'number' && Number.isFinite(value) ? value : undefined);
const revision = (value: unknown) => (typeof value === 'number' && Number.isSafeInteger(value) ? value : undefined);

export function narrativeSummaries(observations: JsonRecord[]) {
  const decisions = new Map<string, string>();
  const reports = new Map<string, string>();
  for (const observation of observations) {
    const value = asRecord(observation.values);
    if (observation.kind !== 'factory_iteration_summary' || value.schema !== 'factory-iteration-summary/1') continue;
    const summary = text(value.summary).trim();
    if (!summary) continue;
    const decision = text(value.decision_id);
    if (decision) decisions.set(decision, summary);
    for (const id of [text(value.report_artifact_id), text(value.report_observation_id)]) {
      if (id) reports.set(id, summary);
    }
  }
  return { decisions, reports };
}

export function decisionSummary(decision: JsonRecord, summaries: Map<string, string>) {
  return text(asRecord(decision.action).summary).trim() || text(decision.summary).trim() ||
    summaries.get(decisionId(decision)) || '';
}

type ArtifactKind = 'diff' | 'report' | 'analysis' | 'lab' | 'prior' | 'other';
export type IterationArtifact = { id: string; taskId: string; sha256: string; kind: ArtifactKind };
const refId = (value: unknown) => text(value) || text(asRecord(value).artifact_id);
const refIds = (value: unknown) => (Array.isArray(value) ? value.map(refId) : []);
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
      Array.isArray(values) ? values.flatMap((value) => reference(value, 'diff')) : [],
    ),
    ...(Array.isArray(lab.result_artifact_ids)
      ? lab.result_artifact_ids.flatMap((value) => reference(value, 'lab'))
      : []),
    ...(Array.isArray(analysis.output_artifact_ids)
      ? analysis.output_artifact_ids.flatMap((value) => reference(value, 'analysis'))
      : []),
    ...reference(meta.report, 'report'),
    ...(Array.isArray(meta.predecessor_report_ids)
      ? meta.predecessor_report_ids.flatMap((value) => reference(value, 'prior'))
      : []),
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
  const summaries = narrativeSummaries(observations);
  const artifacts = records.artifacts || [];
  const attempts = records.attempts || [];
  const cycles = new Map<string, JsonRecord>();
  const reportHistory = new Map<string, JsonRecord[]>();
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
    if (
      (observation.kind !== 'factory_iteration_report' && observation.kind !== 'factory_iteration_report_revision') ||
      meta.schema !== 'spark-factory-iteration/1' ||
      !id
    )
      continue;
    const history = reportHistory.get(id) ?? [];
    history.push(observation);
    reportHistory.set(id, history);
    const previous = asRecord(asRecord(cycles.get(id)?.meta).report);
    const version = revision(asRecord(meta.report).revision) ?? 0;
    if (version >= (revision(previous.revision) ?? 0)) {
      cycles.set(id, { ...cycles.get(id), cycle_id: id, meta, metadata_observation: observation });
    }
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
      const recordedPlanId = decisionId(metaPlan.decision_id);
      const historical = (reportHistory.get(id) ?? []).filter((observation) => observation !== metadataObservation);
      const historyRefs = historical.flatMap((observation) => {
        const prior = asRecord(asRecord(observation.values).report);
        const artifactId = refId(prior);
        return artifactId
          ? [{ id: artifactId, taskId: text(prior.task_id), sha256: text(prior.sha256), kind: 'report' as const }]
          : [];
      });
      const attached = [...artifactReferences(meta), ...historyRefs];
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
      const reportAliases = new Map(
        (reportHistory.get(id) ?? []).map(
          (observation) => [recordId(observation), refId(asRecord(observation.values).report)] as const,
        ),
      );
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
              localRefs.some((ref) => ref.id === artifact) ||
              linkedIds.has(artifact) ||
              Boolean(revision(cycle.number) !== undefined && artifact.startsWith(`loop-artifact:${number}:`)) ||
              Boolean(attemptId && artifact.startsWith(`${attemptId}:`)),
          ),
        )
        .map((original) => {
          const ref = localRefs.find((entry) => original.artifact_ids?.includes(entry.id));
          const file: EvidenceFile =
            ref?.sha256 && original.sha256 !== ref.sha256 && original.integrity !== 'missing'
              ? { ...original, expected_sha256: ref.sha256, integrity: 'mismatch' }
              : original;
          return { file, kind: ref?.kind || fileKind(file) };
        });
      const relatedReports = new Set(
        unique([
          resultId,
          text(metadataObservation.obs_id),
          ...historical.map(recordId),
          text(asRecord(meta.report).supersedes_observation_id),
          text(asRecord(meta.report).supersedes_artifact_id),
          ...reportRefs.map((ref) => ref.id),
          text(report?.obs_id),
          ...scopedObservations
            .filter((observation) => /(?:^|[_-])report$/i.test(text(observation.kind)))
            .map(recordId),
          ...linkedFiles.filter((entry) => entry.kind === 'report').flatMap(({ file }) => file.artifact_ids || []),
        ]),
      );
      const successors = new Map<string, {
        id: string; task: string; reason: string; summary: string; decisionFile: EvidenceFile; reportFile: EvidenceFile;
      }>();
      for (const observation of scopedObservations) {
        if (observation.kind !== 'factory_iteration_successors') continue;
        const values = asRecord(observation.values);
        const reportId = text(values.report_artifact_id);
        const reportFile = linkedFiles.find(({ file, kind }) =>
          kind === 'report' && file.artifact_ids?.includes(reportId))?.file;
        if (!reportFile || (values.report_sha256 && values.report_sha256 !== reportFile.sha256)) continue;
        for (const edge of rows(values.next_plans)) {
          const id = text(edge.decision_id);
          const task = decisionTask(edge);
          const artifact = text(edge.decision_artifact_id) || text(edge.artifact_id);
          const file = linkedFiles.find(({ file }) => file.artifact_ids?.includes(artifact))?.file;
          if (!id || !task || !file || file.integrity !== 'verified' ||
            (edge.decision_sha256 && edge.decision_sha256 !== file.sha256)) continue;
          successors.set(id, {
            id, task, reason: text(edge.reason_for_change) || successors.get(id)?.reason || '',
            summary: text(edge.summary).trim() || summaries.decisions.get(id) || successors.get(id)?.summary || '',
            decisionFile: file, reportFile,
          });
        }
      }
      const nextPlan = asRecord(meta.next_plan);
      const explicitNextId = decisionId(nextPlan.decision_id);
      const reportedAt = timestamp(metadataObservation.created) ?? timestamp(report?.created) ?? timestamp(cycle.ended);
      const nextDecisions = decisions.flatMap((decision) => {
        const nextRev = revision(decision.rev);
        const decidedAt = timestamp(decision.created);
        const later =
          nextRev !== undefined && activeRev !== undefined
            ? nextRev > activeRev
            : reportedAt !== undefined && decidedAt !== undefined && decidedAt > reportedAt;
        const explicit = Boolean(explicitNextId && decision.decision_id === explicitNextId);
        if (decision === plan || (!explicit && !later)) return [];
        const cited = strings(decision.evidence_ids).filter((reference) => relatedReports.has(reference));
        if (!explicit && !cited.length) return [];
        return [{ decision, cited }];
      });
      const reportId = reportRefs[0]?.id || resultId;
      const reportSummary = text(asRecord(meta.report).summary).trim() || text(reportData.summary).trim() ||
        summaries.reports.get(reportId) || summaries.reports.get(recordId(metadataObservation)) ||
        summaries.reports.get(resultId) || '';
      const linkedNext = ordered.slice(index + 1).find((candidate) => {
        const candidateMeta = asRecord(candidate.meta);
        const candidatePlan = asRecord(candidateMeta.plan);
        const incoming = refIds(candidatePlan.incoming_report_ids);
        return Boolean(
          (explicitNextId && decisionId(candidatePlan.decision_id) === explicitNextId) ||
          incoming.some((reference) => relatedReports.has(reference)),
        );
      });
      const remoteReferences = attached.filter(
        (ref) =>
          !linkedFiles.some(
            ({ file }) => file.artifact_ids?.includes(ref.id) && (!ref.taskId || ref.taskId === localTask),
          ),
      );
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
        reportAliases,
        linkedFiles,
        remoteReferences,
        metadataObservation,
        recordedPlanId,
        planSummary: text(metaPlan.summary).trim() || (plan ? decisionSummary(plan, summaries.decisions) : '') ||
          summaries.decisions.get(recordedPlanId) || '',
        reportSummary,
        rationale: text(metaPlan.rationale),
        sourceCommit: text(asRecord(meta.do).source_commit),
        analysisCapsules: unique(capsuleNames(asRecord(meta.analysis).ccs)),
        explicitNextId,
        explicitNextTask: text(nextPlan.task_id) || decisionTask(nextPlan.decision_id),
        linkedNextId: cycleOf(linkedNext || {}),
        iterationStatus: text(asRecord(meta.report).status),
        nextDecisions,
        successors: [...successors.values()],
        capsuleIds,
        component,
        followup,
        inputs: unique([
          ...strings(plan?.evidence_ids ?? request.evidence_ids),
          ...refIds(metaPlan.incoming_report_ids),
        ]),
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
