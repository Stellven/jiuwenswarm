def pytest_runtest_logreport(report):
    if report.failed:
        print('\nFAILED '+report.nodeid+'\n'+str(report.longrepr),flush=True)
