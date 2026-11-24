"""Call the shared source integration job adapter; never execute source patches."""
from jiuwenswarm.factory.job_packages import main

if __name__ == '__main__':
    main('factory.integration_skill')
