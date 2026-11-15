"""Expose the finite prefill job toolset through the shared host bridge."""
from jiuwenswarm.factory.job_packages import main

if __name__ == "__main__":
    main("engine.strata_prefill_workbench")
