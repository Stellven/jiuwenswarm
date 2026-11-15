"""Expose one cohesive bounded throughput job through guarded shared routes."""
from jiuwenswarm.factory.job_packages import main

if __name__ == "__main__":
    main("engine.strata_throughput_workbench")
