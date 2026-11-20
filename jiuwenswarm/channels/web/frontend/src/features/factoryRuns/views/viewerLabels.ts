import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

const labels = {
  artifacts: ['Artifacts', '产物'],
  browseFiles: ['Evidence files', '证据文件'],
  filterFiles: ['Filter evidence files', '筛选证据文件'],
  chooseFile: ['Choose a file to inspect.', '请选择要查看的文件。'],
  binaryFile: ['Binary evidence has no text preview.', '二进制证据没有文本预览。'],
  fileLoading: ['Loading file…', '正在加载文件…'],
  fileMissing: [
    'The manifest lists this file, but it is missing from the run.',
    '清单列出了此文件，但运行记录中缺少该文件。',
  ],
  noResults: ['No matches.', '没有匹配项。'],
  noFileDigest: ['No file digest', '无文件摘要'],
  previewSize: ['Preview size', '预览大小'],
  modes: ['Document view', '文档视图'],
  readable: ['Readable', '易读'],
  tree: ['Tree', '树状'],
  chart: ['Chart', '图表'],
  metric: ['Metric', '指标'],
  table: ['Table', '表格'],
  graph: ['Graph', '图谱'],
  raw: ['Raw', '原始文本'],
  report: ['Report', '报告'],
  copy: ['Copy', '复制'],
  copied: ['Copied', '已复制'],
  copyError: ['Copy failed', '复制失败'],
  parseError: ['Could not parse this preview.', '无法解析此预览。'],
  structureLimit: ['This document exceeds the structured view limits.', '此文档超出结构化视图的限制。'],
  empty: ['Empty', '空'],
  root: ['Root', '根节点'],
  search: ['Search keys and values', '搜索键和值'],
  chooseTable: ['Choose an array', '选择数组'],
  previous: ['Previous', '上一页'],
  next: ['Next', '下一页'],
  showMore: ['Show more', '显示更多'],
  open: ['Open', '打开'],
  fields: ['fields', '字段'],
  items: ['items', '项'],
  preview: ['Preview', '预览'],
  recordedEvents: ['Replay events', '回放事件'],
} as const;

export function useViewerLabels() {
  const { i18n } = useTranslation();
  const lang = i18n.resolvedLanguage || i18n.language;
  const label = useCallback((key: keyof typeof labels) => labels[key][lang?.startsWith('zh') ? 1 : 0], [lang]);
  return { label, lang };
}
