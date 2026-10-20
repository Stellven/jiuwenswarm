"""Offline report reconstruction from existing exact CLI campaign/score bytes."""
import hashlib
from pathlib import Path

from jiuwenswarm.research_sidecar.evidence import canonical,read_verified
from jiuwenswarm.research_sidecar.frozen_records import strict_json
from jiuwenswarm.research_sidecar.reports import build_report,markdown


def test_credential_free_referee_rebuilds_exact_reports_and_preserves_unsuccessful_rows(frozen_campaign):
    assert frozen_campaign['check']=='M1-QA/V12'
    root=frozen_campaign['root'];results=frozen_campaign['results_root'];campaign=frozen_campaign['campaign']
    bench=root.parent.parent
    scores=[];source_paths=[];metadata={c['case_id']:c for c in frozen_campaign['cases']}
    seen=set()
    for row in frozen_campaign['rows']:
        folder=results/'runs'/row['run_id'];run=strict_json((folder/'run_record.json').read_bytes())
        for key in ('campaign_id','run_id','case_id','case_version','config_id','repeat_index'):assert run[key]==row[key]
        for export in run['exports']:read_verified(folder,export)
        case=metadata[row['case_id']]
        score_path=bench/'scores'/campaign['campaign_id']/row['run_id']/case['oracle_version']/'score_record.json'
        score=strict_json(score_path.read_bytes())
        assert (score['campaign_id'],score['run_id'],score['case_id'],score['case_version'])==(row['campaign_id'],row['run_id'],row['case_id'],row['case_version'])
        assert score['checks'] and all(c['status']!='not_run' for c in score['checks'])
        assert row['run_id'] not in seen;seen.add(row['run_id'])
        scores.append(score);source_paths.append(score_path.relative_to(bench).as_posix())
    assert seen=={r['run_id'] for r in frozen_campaign['rows']},'Unsuccessful/missing rows cannot be dropped from report population.'
    source_paths.sort()
    for audience in ('referee','public'):
        report=build_report(scores,audience=audience,report_id=campaign['campaign_id']+'_'+audience,
            generated_at=campaign['frozen_at'],pins=campaign['pins'],source_scores=source_paths,case_metadata=metadata)
        destination=bench/'reports'/(campaign['campaign_id']+'_'+audience)
        assert (destination/'report.json').read_bytes()==canonical(report)
        assert (destination/'report.md').read_bytes()==markdown(report).encode('utf8')
        if audience=='public':
            assert report['source_scores']==[hashlib.sha256(canonical(sorted(scores,key=lambda s:(s['campaign_id'],s['run_id'],s['oracle_version'])))).hexdigest()]
            assert not report['comparability']['comparable_case_keys']


def test_registered_extension_preserves_product_source_identity(frozen_campaign):
    """Require a real pre-frozen replacement/oracle registration receipt.

    A newly manufactured fixture or a CLI rerun is not extension evidence.
    """
    from jiuwenswarm.research_sidecar.evidence import relative
    path=frozen_campaign['results_root']/'extension-receipt.json'
    assert path.is_file(),'Required actual documented fixture/oracle extension receipt is absent.'
    receipt=strict_json(path.read_bytes())
    assert receipt['schema']=='ai4r-benchmark-extension-observation:1'
    assert receipt['campaign_id']==frozen_campaign['campaign']['campaign_id']
    assert receipt['kind'] in {'visible_fixture_replacement','independent_oracle_addition','controlled_variant_addition'}
    assert receipt['product_code_before']==receipt['product_code_after'] and receipt['product_code_before']
    assert receipt['registered_before_execution'] is True and receipt['replayed_as_new_execution'] is False
    assert receipt['evidence_files']
    for row in receipt['evidence_files']:
        relative(row['path']);read_verified(frozen_campaign['results_root'],row)
