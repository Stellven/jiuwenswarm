import { addInfo } from "../helpers.js";
import { CommandKind, type SlashCommand } from "../types.js";

export function createSwarmFlowsCommand(): SlashCommand {
  return {
    name: "swarmflows",
    altNames: ["swarmworkflows"],
    description: "Show swarm workflow runs for the current session",
    usage: "/swarmflows",
    example: "/swarmflows",
    kind: CommandKind.BUILT_IN,
    action: async (ctx) => {
      ctx.addItem(
        addInfo(
          ctx.sessionId,
          "Swarm flows view is handled by the TUI. If this message appears, reopen the command from the interactive TUI.",
          "w",
        ),
      );
    },
  };
}

export function createResearchCommand(): SlashCommand {
  return {
    name: "research", description: "Inspect readiness, status, export or request cancellation through the protected research service",
    usage: "/research readiness | status RUN | export RUN [NEW_FILE] | cancel RUN", example: "/research readiness",
    kind: CommandKind.BUILT_IN,
    action: async (ctx, args) => {
      const [action, runId, ...output] = args.trim().split(/\s+/);
      if (!["readiness", "status", "export", "cancel"].includes(action) || (action !== "readiness" && !runId)) {
        ctx.addItem(addInfo(ctx.sessionId, "Usage: /research readiness | status RUN | export RUN [NEW_FILE] | cancel RUN", "i"));
        return;
      }
      const payload = await ctx.request(`research.${action}`, { ...(runId ? { run_id: runId } : {}),
        ...(action === "export" && output.length ? { output: output.join(" ") } : {}),
        ...(action === "cancel" ? { request_id: `cancel:${Date.now()}:${Math.random().toString(36).slice(2)}` } : {}) });
      ctx.addItem(addInfo(ctx.sessionId, JSON.stringify(payload, null, 2), "i"));
    },
  };
}
