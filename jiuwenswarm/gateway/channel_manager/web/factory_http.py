"""Mount the executable Software Factory in the existing WebChannel application.

This service has its own mutable engineering graph. It does not mutate a frozen
ResearchService run or bypass its admission/activation boundaries.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, Request


def mount_factory_routes(app, channel) -> None:
    from jiuwenswarm.software_factory.api import create_router
    from jiuwenswarm.software_factory.engine import FactoryService

    configured = os.environ.get("JIUWENSWARM_FACTORY_ROOT")
    data_root = Path(os.environ.get("JIUWENSWARM_DATA_DIR", str(Path.cwd() / ".factory")))
    root = Path(configured) if configured else data_root / "software-factory"
    service = getattr(channel, "factory_service", None)
    if service is None:
        service = FactoryService(root.resolve())
        channel.factory_service = service
    app.state.factory_service = service

    authorize = None
    if bool(getattr(channel, "research_profile", False)):
        authority = getattr(channel, "research_authority", None)
        if authority is None:
            raise RuntimeError("Protected factory requires the host session authority")

        def authorize(request: Request, operation: str):
            from jiuwenswarm.research.contracts.types import ResearchError
            try:
                return authority.authenticate(request.headers.get("authorization"), operation)
            except ResearchError as error:
                raise HTTPException(status_code=401, detail="Factory access requires an authorized host session") from error

    app.include_router(create_router(service, authorize=authorize))
