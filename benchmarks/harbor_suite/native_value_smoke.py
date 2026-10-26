"""Offline full-application plumbing probe. Scripted completion, NO model calls.

Outputs are explicitly offline fixtures, never campaign baseline results.
"""
import asyncio
import json
import os
from pathlib import Path
import shlex
import sys

from benchmarks.harbor_suite import native_value


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "evidence").mkdir()
    (root / "home").mkdir()
    (root / "broker").mkdir()
    os.environ.update(native_value.child_environment(root))
    observed = []
    tool_selected = False
    skill_selected = False

    async def scripted(directory, prompt, timeout, *, model):
        nonlocal tool_selected, skill_selected
        packet = json.loads(prompt[len(native_value.WIRE_INSTRUCTION)+1:])
        observed.append(packet)
        native_value.write(root / f"offline-packet-{len(observed)}.json", packet)
        definitions = native_value.tool_definitions(packet["tools"])
        print("OFFLINE_NATIVE_TOOL_NAMES=" + json.dumps(list(definitions)), flush=True)
        calls = []
        if len(sys.argv) > 2 and sys.argv[2] == "native-skills" and "skill_tool" in definitions and not skill_selected:
            skill_selected = True
            calls = [{"name": "skill_tool", "arguments": {"skill_name": "offline-ordinary-skill"}}]
        elif "bash" in definitions and not tool_selected:
            tool_selected = True
            target = shlex.quote(str(root / "project" / "native-tool-proof.txt"))
            calls = [{"name": "bash", "arguments": {
                "command": "printf native-value-real-tool > " + target + " && cat " + target,
                "call_goal": "Write and read the offline tool-cycle proof"}}]
        return {"text": json.dumps({"content": "offline plumbing fixture", "tool_calls": calls}),
                "offline_fixture": True}

    native_value.file_completion = scripted
    spec = {"variant": "native", "task": "Inspect the working directory and report the files.",
            "completion_directory": str(root / "broker"), "model": "gpt-6.1-sol",
            "reasoning_effort": "medium", "mode": "agent.work.normal", "skill_dirs": [],
            "max_model_calls": 4, "max_tool_calls": 5, "wall_time_s": 45}
    if len(sys.argv) > 2 and sys.argv[2] == "native-skills":
        skill = root / "offline-ordinary-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: offline-ordinary-skill\ndescription: Ordinary offline probe skill.\n---\n"
            "Native skill loading proof marker: NATIVE_VALUE_SKILL_LOADED.\n"
            "Use ordinary shell tools to inspect the project and verify files.\n", encoding="utf-8")
        spec.update(variant="native-skills", skill_dirs=[str(skill)])
    result = asyncio.run(native_value.execute_worker(spec, root))
    proof = root / "project" / "native-tool-proof.txt"
    result["actual_native_tool_cycle"] = proof.is_file() and proof.read_text() == "native-value-real-tool"
    result["tool_result_reentered_model"] = any("native-value-real-tool" in json.dumps(row["messages"])
        and any(m.get("role") == "tool" for m in row["messages"] if isinstance(m, dict)) for row in observed)
    result["offline_fixture"] = True
    result["native_skill_body_observed"] = any("NATIVE_VALUE_SKILL_LOADED" in json.dumps(row["messages"])
                                               for row in observed)
    result["image_probe_calls"] = sum("What color is this image?" in json.dumps(row["messages"])
                                      for row in observed)
    native_value.write(root / "offline-result.json", result)
    print(json.dumps(result))
    okay = result["actual_native_tool_cycle"] and result["tool_result_reentered_model"] and result["image_probe_calls"] == 0
    if spec["variant"] == "native-skills":
        okay &= result["native_skill_body_observed"]
    return 0 if okay else 1


if __name__ == "__main__":
    raise SystemExit(main())
