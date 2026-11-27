import argparse

ap = argparse.ArgumentParser(prog="python -m ifbench", description="ifbench v0: reference benchmark package + telemetry adapter")
sub = ap.add_subparsers(dest="cmd", required=True)
r = sub.add_parser("run", help="probe, then benchmarks of one set (smoke / baseline), or a profile pass (--set profile)")
r.add_argument("--config", required=True); r.add_argument("--set", required=True)
r.add_argument("--out", default="runs"); r.add_argument("--no-server", action="store_true",
               help="engine is already running; do not start or stop it")
r.add_argument("--min-mem-available-gib", type=float,
               help="stop the run if Linux MemAvailable falls below this value")
r.add_argument("--reuse-probe", action="store_true",
               help="use a matching completed probe for the budget estimate instead of repeating it")
r.add_argument("--resume-from", help="reuse successful benchmarks from a matching run folder")
c = sub.add_parser("calibrate", help="optional machine calibration: fio storage, BabelStream bandwidth, CUTLASS compute")
c.add_argument("--config", required=True); c.add_argument("--out", default="runs"); c.add_argument("--seconds", type=int, default=30)
c.add_argument("--gpu-only", action="store_true", help="skip the read-only checkpoint fio pass")
c.add_argument("--babelstream", metavar="CUDA_STREAM", help="path to a built BabelStream CUDA executable")
c.add_argument("--cutlass-profiler", metavar="PROFILER", help="path to a built CUTLASS Profiler executable")
n = sub.add_parser("noise", help="A/A: spread of every number across runs of the same engine (run folders)")
n.add_argument("runs", nargs="+"); n.add_argument("--out", default="noise.json")
m = sub.add_parser("compare", help="reference runs vs candidate runs, paired in order; speed, quality, token probabilities")
m.add_argument("--ref", nargs="+", required=True); m.add_argument("--cand", nargs="+", required=True)
m.add_argument("--noise", help="noise.json from the noise command"); m.add_argument("--multiplier", type=float, default=2.0)
m.add_argument("--min-gain", type=float, default=0.01); m.add_argument("--min-top1", type=float)
m.add_argument("--out", default="compare")
pa = sub.add_parser("profile-analyze", help="re-derive the Nsight records of a profile run from its saved trace (offline)")
pa.add_argument("run"); pa.add_argument("--config", help="default: the run's own config.toml")
rp = sub.add_parser("routing-prompts", help="prompts for llama-expert-trace, taken from a baseline run (token probs, GSM8K, probe)")
rp.add_argument("--config", required=True); rp.add_argument("--baseline", required=True); rp.add_argument("--out", required=True)
rp.add_argument("--gsm8k", type=int, default=10)
ra = sub.add_parser("routing-analyze", help="expert selection counts and cache replay from a llama-expert-trace output")
ra.add_argument("--config", required=True); ra.add_argument("--trace", required=True); ra.add_argument("--out", required=True)
ra.add_argument("--baseline", help="baseline run folder: compares the trace program's text with the engine's")
v = sub.add_parser("coverage", help="which of the 47 telemetry IDs the given run folders measured (e.g. baseline + profile)")
v.add_argument("runs", nargs="+"); v.add_argument("--out", help="also write the table to this .md file")
pk = sub.add_parser('pack', help='create a portable Lab Agent evidence bundle')
pk.add_argument('runs', nargs='+'); pk.add_argument('--out', required=True); pk.add_argument('--evidence')
pk.add_argument('--scope', default='small-model toolchain rehearsal; not Muse NVFP4 baseline')
vf = sub.add_parser('verify', help='verify a Lab Agent bundle offline')
vf.add_argument('folder')
rq = sub.add_parser('request-analyze', help='offline per-benchmark request counts, truncation and throughput')
rq.add_argument('folder')
a = ap.parse_args()
if a.cmd == 'request-analyze':
    import json
    from .requests import analyze_run
    print(json.dumps(analyze_run(a.folder), indent=2))
elif a.cmd in ('pack', 'verify'):
    import json
    from .bundle import pack, verify
    result = pack(a.runs, a.out, a.evidence, a.scope) if a.cmd == 'pack' else verify(a.folder)
    print(json.dumps(result, indent=2))
    if not result['ok']:
        raise SystemExit(1)
elif a.cmd == "run":
    from .run import run
    run(a.config, a.set, a.out, a.no_server, a.min_mem_available_gib,
        reuse_probe=a.reuse_probe, resume_from=a.resume_from)
elif a.cmd == "calibrate":
    from .run import calibrate
    if a.gpu_only and not (a.babelstream or a.cutlass_profiler):
        c.error("--gpu-only requires --babelstream or --cutlass-profiler")
    calibrate(a.config, a.out, a.seconds, gpu_only=a.gpu_only,
              babelstream=a.babelstream, cutlass_profiler=a.cutlass_profiler)
elif a.cmd == "profile-analyze":
    from .run import reanalyze_profile
    reanalyze_profile(a.run, a.config)
elif a.cmd == "routing-prompts":
    import json
    from .run import load
    from .routing import routing_prompts
    rows = routing_prompts(a.baseline, load(a.config), a.gsm8k)
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{len(rows)} prompts -> {a.out}")
elif a.cmd == "routing-analyze":
    from .run import load, checkpoint_files
    from .routing import analyze
    cfg = load(a.config)
    analyze(a.trace, cfg, checkpoint_files(cfg), a.out, a.baseline)
elif a.cmd == "coverage":
    from .coverage import coverage
    print(coverage(a.runs, a.out))
elif a.cmd == "noise":
    from .stats import noise, to_markdown
    res = noise(a.runs, a.out)
    open(a.out.rsplit(".", 1)[0] + ".md", "w").write(to_markdown(res))
    print(to_markdown(res))
else:
    from .stats import compare, to_markdown
    print(to_markdown(compare(a.ref, a.cand, a.noise, a.multiplier, a.min_gain, a.min_top1, a.out)))
