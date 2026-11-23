# Spark run kit

Two scripts. They use only the Python 3 standard library; nothing has to be installed and no administrator rights are needed.

| Script | What it does | What it writes |
|---|---|---|
| `probe.py` | Collects measured data on this machine: total memory and memory available now, GPU and driver, disk capacity, sequential read speed from storage, scattered read speed (random positions, ranges the size of one expert, 1/8/16/32 read at a time), memory copy speed | `env-<name>.yaml`, a measured environment description |
| `measure.py` | Against an OpenAI-compatible endpoint that is already running, measures time to first token, decode rate and the drop in system memory | `evidence-<name>.yaml`, one piece of measured evidence |

## Steps on a DGX Spark

**1. Copy this directory to the Spark.**

**2. Run the probe.** `--data-dir` points to a writable directory on the SSD that will hold the model files. The script writes a temporary 16 GiB file there to measure the read speed from storage and deletes it afterwards.

```bash
python3 probe.py --data-dir /path/on/the/ssd --out-dir .
```

**3. Copy the `env-dgx-spark-measured.yaml` it writes back into the `examples/given/` directory of the workspace.**

**4. Compute the figures again in the workspace with the measured environment.**

```bash
python tools/so_assess.py sys/muse-on-spark --spec spec/muse-spark-open-on-dgx-spark/target --environment env/dgx-spark-measured --budget-gb 80 --out runs/muse-assessment-new --root .
```

The figures are in `runs/muse-assessment-new/assessment.md`; its table of inputs says which values are measured.

**5. (Optional) If any OpenAI-compatible endpoint is running on the Spark, measure a baseline once.** It need not be Muse; any model will do to confirm that the measuring script and the way it measures work on this machine.

```bash
python3 measure.py --base-url http://127.0.0.1:8080/v1 --model <model name> --artifact "<runtime version> + <identifier of the weight file>" --name baseline-01
```

## Known limits

- **On 2026-11-13 the memory, GPU and sequential read parts ran through on a DGX Spark; the scattered read was added afterwards, and on this machine only its logic was checked, with stand-in functions.** The original note follows: The two scripts were written and tried on a Windows laptop. There, the memory and copy speed parts of the probe ran through and the read speed test was skipped (it is implemented only on Linux); the measuring script ran through against a fake endpoint on the same machine. `/proc/meminfo`, `nvidia-smi` and the `O_DIRECT` read were run for the first time on the Spark. When something fails, the script writes the reason into the file it produces and does not stop.
- **The read speed is a sequential read in large blocks** (16 MiB blocks, single thread, bypassing the page cache). An engine actually reads experts as random reads, object by object, which may be slower.
- **Available memory is the value at the moment of the probe.** Other processes running on the machine make it smaller.
- **The memory copy speed is single-thread.** It is for reference only and does not replace the memory bandwidth the vendor states.
- **The memory figure of `measure.py` is for the whole machine**: the largest drop in the available memory of the system during the measurement, not the engine process's own use.
- **`measure.py` does not start an engine.** To measure Muse, a runtime and weight files that can run it on the Spark are needed first; according to the model card the NVFP4 version needs at least 700 GB of GPU memory, so an off-the-shelf runtime will very likely not manage it. That it cannot run is itself evidence that should be recorded.
