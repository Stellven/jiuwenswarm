"""Initialize the actual native app with an inference-denying bridge; never chat."""
import asyncio
import json
import os
from pathlib import Path


def check(root):
    from benchmarks.harbor_suite import native_value as native
    root = Path(root); root.mkdir()
    (root / 'state/config').mkdir(parents=True)
    environment = native.child_environment(root)
    os.environ.clear(); os.environ.update(environment)
    import jiuwenswarm
    package = Path(jiuwenswarm.__file__).resolve().parent
    assert package == Path('/opt/ai4r/jiuwenswarm'), str(package)
    for name in ('.env.template', 'config.yaml'):
        assert (package / 'resources' / name).is_file(), name
    from jiuwenswarm.research.native_logging import configure_native_logging
    configure_native_logging(root / 'logs')
    native.configure({'max_model_calls': 1, 'skill_dirs': []}, root, 'gpt-6.1-sol')
    project = root / 'project'; project.mkdir()
    class DeniedScope:
        failure = None
        calls = 0
        async def invoke(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError('MODEL_CALL_FORBIDDEN_DURING_PREFLIGHT')
    scope = DeniedScope()
    async def initialize():
        from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm
        with native.registered_bridge(scope):
            app = JiuWenSwarm()
            try:
                await asyncio.wait_for(app.create_instance({'project_dir': str(project), 'channel_id': 'cli'}, mode='agent'), 90)
            finally:
                await asyncio.wait_for(app.cleanup(), 15)
    asyncio.run(initialize())
    assert scope.calls == 0, 'INITIALIZATION_ATTEMPTED_INFERENCE'
    return {'passed': True, 'application_package': str(package), 'model_calls': scope.calls}


if __name__ == '__main__':
    import sys
    print(json.dumps(check(sys.argv[1])))
