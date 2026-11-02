from simlab.schemas import write, drift
import sys
if "--write" in sys.argv:
    for p in write():
        print(p)
else:
    d = drift()
    print("drift:", d or "none")
    raise SystemExit(1 if d else 0)
