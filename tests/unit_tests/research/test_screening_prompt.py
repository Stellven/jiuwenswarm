"""Pinned work prompt has an observable effect without changing check authority."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsules.ranking import rank_opportunities
from jiuwenswarm.research.capsules.screening import ScreeningCarrier
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.mark.asyncio
async def test_exact_admitted_prompt_is_read_and_outside_body_is_rejected(tmp_path):
    source=Path(__file__).parents[2]/'fixtures/research/pipeline/source-valid'
    store=SQLiteRunStore(tmp_path/'store')
    try:
        values={name:json.loads((source/(filename+'.json')).read_bytes()) for name,filename in
                [('brief','lifecycle_research_brief'),('candidate_set','candidate_set'),('screening_rubric','screening_rubric')]}
        refs={name:store.put_blob(json.dumps(value).encode()) for name,value in values.items()}
        scores=json.loads((source/'screening_result.json').read_bytes())['scores']
        helper_ref=store.put_blob(b'unit installed ranking closure')
        prompt_ref=store.put_blob(b'Visible controlled admitted work prompt marker.')
        contract={'bindings':[{'implementation_refs':[helper_ref,prompt_ref],'dependency_refs':[]}]}
        seen=[]
        async def model(prompt,*,system=None):
            seen.append(system)
            return json.dumps({'scores':scores,'opportunity_statement':'The frozen mechanism avoids repeated lookup work.'})
        ctx=SimpleNamespace(contract=contract,store=store,model=model,input_ref=refs.__getitem__,record_host=lambda *_:None)
        outputs=await ScreeningCarrier(rank_opportunities,helper_ref,prompt_ref).execute(ctx,values)
        assert set(outputs)=={'screening_result','opportunity_card'}
        assert len(seen)==1 and 'Visible controlled admitted work prompt marker.' in seen[0]
        assert 'novelty, feasibility and compute_alignment' in seen[0]
        foreign=store.put_blob(b'Not in the admitted body')
        with pytest.raises(ResearchError,match='outside the admitted body'):
            await ScreeningCarrier(rank_opportunities,helper_ref,foreign).execute(ctx,values)
        assert len(seen)==1
    finally:
        store.close()
