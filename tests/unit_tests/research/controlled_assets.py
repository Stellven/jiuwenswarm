"""Explicit component-test authority; never evidence of calibrated eligibility.

Controlled model/component tests exercise other mechanisms independently of
missing real protected calibration profiles. Production imports none of this.
"""
from jiuwenswarm.research.checks.assets import CheckAssetAdmissions
from jiuwenswarm.research.library import LibraryService


class ControlledCheckingAssets(CheckAssetAdmissions):
    def require(self, bundle_ref, profile_ref):
        self.closure(bundle_ref, profile_ref)
        return ()  # Deliberate test authority; not a measured admission receipt.


class ControlledLibraryService(LibraryService):
    def __init__(self, store, **kwargs):
        kwargs['check_assets'] = ControlledCheckingAssets(store)
        super().__init__(store, **kwargs)
