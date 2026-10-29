"""Independent reference semantics for the authorized Screening helper."""


def rank_opportunities(scores):
    # Independent reference for sum/tie/Top1. Mandatory checks stay in their
    # immutable owner bundle; this is never installed over the live parent.
    if len({s['idea_id'] for s in scores})!=len(scores):raise ValueError('duplicate score identity')
    eligible=[s for s in scores if s['eligible']]
    if not eligible:raise ValueError('no eligible opportunity')
    ranked=sorted(eligible,key=lambda row:(-sum(row[k] for k in ('novelty','feasibility','compute_alignment')),row['idea_id']))
    return {'ranking':[{'rank':i+1,'idea_id':row['idea_id'],'total':sum(row[k] for k in ('novelty','feasibility','compute_alignment'))} for i,row in enumerate(ranked)],'selected_idea_id':ranked[0]['idea_id']}
