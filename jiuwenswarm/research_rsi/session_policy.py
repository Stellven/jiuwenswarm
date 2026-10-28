"""Frozen private execution budgets; no extra evaluation or release authority."""
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import math

BUDGET_SCHEMA='urn:ai4r:private:rsi-final-budget:1'
PHASE_SCHEMA='urn:ai4r:private:rsi-session-phase:1'


@lru_cache(maxsize=1)
def _contracts():
    from jiuwenswarm.research_records.contracts import ContractData
    return ContractData()


def validate_private(name,value):
    _contracts().validate(name,value)


@dataclass(frozen=True)
class FinalBudget:
    final_reserve_s:int
    execution_s:float
    invocation_wall_s:float
    worker_timeout_s:float
    hidden_final_units:int
    mandatory_units:int
    evidence_wall_s:float

    @classmethod
    def from_record(cls,value,*,wall_s,target_ref,repeats):
        validate_private(BUDGET_SCHEMA,value)
        if value['target_ref']!=target_ref or value['pass_count_repeats']!=repeats:
            raise ValueError('Frozen final budget target/repeat binding differs')
        if value['worker_timeout_s']>value['invocation_wall_s']:
            raise ValueError('Final invocation bound is below the worker timeout')
        # Both mandatory suites, both final quality suites, then every batch
        # in five warmups/seven paired rounds at the frozen repeat count.
        calls=2*repeats*(value['mandatory_units']+value['hidden_final_units']*(1+5+7))
        execution=calls*Fraction(str(value['invocation_wall_s']))
        reserve=math.ceil(execution+Fraction(str(value['evidence_wall_s'])))
        if value['final_reserve_s']!=reserve:raise ValueError('Final reserve does not match the frozen execution/evidence plan')
        if reserve+value['evidence_wall_s']>=wall_s:raise ValueError('Final reserve and dispatch margin leave no search wall budget')
        return cls(reserve,float(execution),value['invocation_wall_s'],value['worker_timeout_s'],
            value['hidden_final_units'],value['mandatory_units'],value['evidence_wall_s'])

    @classmethod
    def for_session(cls,session,store,*,worker_profile=None,manifest=None):
        genesis=store.get(session['chain_root_ref'])
        pin=genesis.get('final_budget_ref')
        if pin is None:raise ValueError('Frozen final budget is required before evaluation')
        budget=cls.from_record(store.get(pin),wall_s=session['limits']['wall_s'],
            target_ref=session['target_profile_ref'],repeats=session['pass_count_repeats'])
        if worker_profile is not None and worker_profile['timeout_s']!=budget.worker_timeout_s:
            raise ValueError('Frozen final budget differs from the actual worker timeout')
        if manifest is not None:
            partitions=manifest['partitions']
            if len(partitions['hidden_final'])!=budget.hidden_final_units or len(partitions['platform'])!=budget.mandatory_units:
                raise ValueError('Frozen final budget differs from the protected fixture populations')
        return budget

    def search_remaining(self,*,deadline,now):
        # Keep the same frozen I/O allowance outside the assessment reserve
        # for phase/selection persistence before terminal dispatch.
        return max(0,deadline-self.final_reserve_s-self.evidence_wall_s-now)
