# 20261113 Recorded Demo Replay prepresentation

Open the package console, select Replay and play at normal speed. The existing film is 406.03 seconds at 1920x1080. It already compresses long waits and labels that compression. The talk allows 193.97 seconds around it, for ten minutes total.

On Linux, from this extracted package, replay raw terminal recordings without a model or factory:

```sh
cd evidence/incremental/recording
for n in 1 2 3; do
  scriptreplay -t "seg$n.timing" "seg$n.typescript" -d 20
done
```

Use -d 1 for original timing. No live job is submitted. Current startup instructions are in context/recovery; the original LAUNCH-REPLAY.md beside the recordings is historical and contains superseded startup prerequisites.

This is the 32-token fill-only task, whose outcome was inconclusive. The historical 64-token J-OM13 performance result has a separate report and specification. Raw recordings and measured results were not altered.
