// Produce a real frontend-generated decision for the Python contract test.
import { ApprovalController } from './approval_frontend.mjs';
let input = '';
for await (const chunk of process.stdin) input += chunk;
const { scope, notice, approved } = JSON.parse(input);
const controller = new ApprovalController(scope);
if (!controller.receive(notice)) throw new Error('fixture notice rejected');
await controller.decide(approved, async (payload) => {
  process.stdout.write(JSON.stringify(payload));
  return { accepted: true, ticket: payload.ticket };
});
