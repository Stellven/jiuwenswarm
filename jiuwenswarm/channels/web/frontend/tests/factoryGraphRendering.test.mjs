import assert from 'node:assert/strict';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { buildSync } from 'esbuild';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { detectGraph } from '../src/features/factoryRuns/views/graphModel.ts';
import { layoutOntologyGroups } from '../src/features/factoryRuns/views/ontologyLayout.ts';

test('fit-to-width ontology layout keeps membership links and wraps cards with 1:1 label sizing', () => {
  const graph = detectGraph(`block-beta
block:g_a["A"]
  a1["A1"]
  a2["A2"]
end
block:g_b["B"]
  b1["B1"]
end
block:g_c["C"]
  c1["C1"]
end`);
  for (const width of [755, 560, 320]) {
    const { placement, links, height } = layoutOntologyGroups(graph, width);
    assert.deepEqual(links, graph.links);
    const groups = placement.filter((item) => item.grouped);
    assert.equal(groups.length, 3);
    assert.equal(new Set(groups.map(({ position }) => position.y)).size, width >= 738 ? 1 : width >= 496 ? 2 : 3);
    for (const group of groups) {
      assert.ok(group.position.x + group.width <= width);
      assert.ok(group.position.y + group.height <= height);
    }
    for (const edge of links) {
      const entity = placement.find(({ node }) => node.id === edge.target);
      assert.equal(entity.parentId, edge.source);
      assert.ok(entity.position.x >= 35);
      assert.ok(entity.height >= 40);
    }
  }
});

test('membership edge renderer emits a visible routed SVG path and carries the arrow marker', async () => {
  const component = new URL('../src/features/factoryRuns/views/MembershipEdge.tsx', import.meta.url);
  const { outputFiles } = buildSync({
    entryPoints: [fileURLToPath(component)],
    bundle: true,
    platform: 'node',
    format: 'esm',
    jsx: 'automatic',
    write: false,
    define: { 'process.env.NODE_ENV': '"production"' },
  });
  const { MembershipEdge } = await import(
    'data:text/javascript;base64,' + Buffer.from(outputFiles[0].text).toString('base64')
  );
  const svg = renderToStaticMarkup(
    createElement(
      'svg',
      null,
      createElement(MembershipEdge, {
        sourceX: 30,
        sourceY: 46,
        targetX: 47,
        targetY: 92,
        source: 'group:a',
        target: 'entity:b',
        markerEnd: 'url(#member-arrow)',
      }),
    ),
  );
  assert.match(svg, /<path[^>]+class="[^"]*factory-graph-membership-edge/);
  assert.match(svg, /d="M 30 46 V 92 H 47"/);
  assert.match(svg, /marker-end="url\(#member-arrow\)"/);
  assert.match(svg, /data-variant="group:a → entity:b"/);
});
