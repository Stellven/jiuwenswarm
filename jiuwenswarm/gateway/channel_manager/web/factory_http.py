"""Mount explicitly configured CC workflows; keep the old example opt-in."""
import os


def mount_factory_routes(app, channel):
    from jiuwenswarm.software_factory.cc_api import create_cc_router
    from jiuwenswarm.software_factory.cc_service import CCService
    config = os.environ.get('JIUWENSWARM_CC_WORKFLOW_CONFIG')
    service = CCService.from_config(config) if config else None
    app.state.cc_workflow_service = service
    app.include_router(create_cc_router(service))
    # Temporary example/replay compatibility. Never an alternate Spark executor.
    if os.environ.get('JIUWENSWARM_FACTORY_EXAMPLE') == '1':
        from pathlib import Path
        from jiuwenswarm.software_factory.api import create_router
        from jiuwenswarm.software_factory.engine import FactoryService
        root = Path(os.environ.get('JIUWENSWARM_FACTORY_ROOT', '.factory-example'))
        example = FactoryService(root.resolve())
        app.state.factory_service = example
        app.include_router(create_router(example))
