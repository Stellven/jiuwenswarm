"""Constructor-only mechanics authority. This is not13-case qualification."""
class ControlledQualification:
    def __init__(self):self.calls=[]
    def require(self,operation,**context):
        self.calls.append((operation,context))
        return {'qualification_ref':{'id':'controlled-unit-qualification-not-operational','sha256':'a'*64},
                'scope_ref':{'id':'controlled-unit-scope-not-observed','sha256':'b'*64}}
