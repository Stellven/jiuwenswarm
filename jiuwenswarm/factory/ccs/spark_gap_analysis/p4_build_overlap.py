"""Classify the final A+ window against the retained disjoint build lane."""
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import PurePosixPath
import re
from statistics import median


AUTHORIZED_UNITS = ('spark-owner-d-cpu.service', 'spark-owner-c2-cpu.service')
PREFLIGHT_UNIT = 'spark-c2-placement-tier-build.service'
BUILD_CPUS = set(range(12, 20))
COMPILERS = {'cc1', 'cc1plus', 'nvcc', 'cicc', 'ptxas'}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def stamp(value):
    timestamp = datetime.fromisoformat(value)
    require(timestamp.tzinfo is not None, 'Build overlap timestamps must have timezone offsets')
    return timestamp


def service_record(raw):
    fields = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    require(fields['ActiveState'] == 'active' and int(fields['MainPID']) > 0 and
            fields['Nice'] == '19' and fields['IOSchedulingClass'] == '3' and
            fields['CPUAffinity'] == '12-19' and fields.get('AllowedCPUs', '12-19') == '12-19',
            'Systemd receipt does not establish the owner-authorized disjoint build lane')
    entered, zone = fields['ActiveEnterTimestamp'].rsplit(' ', 1)
    offset = {'EST': -5, 'EDT': -4, 'UTC': 0}[zone]
    start = datetime.strptime(entered, '%a %Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=offset)))
    return dict(start=start.astimezone(timezone.utc).isoformat(), main_pid=int(fields['MainPID']))


def service_intervals(unit, raw):
    intervals = []
    active = None
    for line in raw.splitlines():
        instant = line.split(maxsplit=1)[0]
        if f': Started {unit} - ' in line:
            require(active is None, 'A new build invocation lacks its prior stop')
            active = dict(start=stamp(instant).isoformat(), stop=None, attempt=None)
        elif active is not None:
            if match := re.search(r'\battempt ([0-9a-f]{32})\b', line):
                active['attempt'] = match.group(1)
            if any(f': {unit}: {message}' in line for message in ('Main process exited', 'Deactivated successfully')):
                active['stop'] = stamp(instant).isoformat()
                intervals.append(active)
                active = None
    if active:
        intervals.append(active)
    require(intervals, 'Build service journal is missing an invocation start')
    return intervals


def validate_process(record, services, observed):
    units = set(PurePosixPath(record['cgroup']).parts) & services.keys()
    require(len(units) == 1 and type(record['pid']) is int and record['pid'] > 0 and
            bool(record['cpus']) and all(type(cpu) is int for cpu in record['cpus']) and
            set(record['cpus']) <= BUILD_CPUS and observed >= services[next(iter(units))],
            'Request observed CPU activity outside its authorized build services or before their start')
    return next(iter(units))


def classify_and_compare(evidence, accepted):
    services = evidence['build_services']
    require(tuple(row['unit'] for row in services) == AUTHORIZED_UNITS and
            all(service_record(row['raw']) == row['value'] for row in services),
            'Expected the two exact owner-authorized build receipts')
    starts = {row['unit']: stamp(row['value']['start']) for row in services}
    final = evidence['scopes'][-1]
    journal = evidence['build_journals']
    require([row['unit'] for row in journal] == [*AUTHORIZED_UNITS, PREFLIGHT_UNIT], 'Build activity journals are incomplete')
    intervals = {row['unit']: service_intervals(row['unit'], row['raw']) for row in journal}
    require(all(hashlib.sha256(row['raw'].encode()).hexdigest() == row['sha256'] for row in [*services, *journal]) and
            all(timedelta(0) <= stamp(intervals[unit][-1]['start']) - starts[unit] < timedelta(seconds=1)
                for unit in AUTHORIZED_UNITS), 'Build receipts do not bind the published service intervals')
    first_start = min(stamp(entry['start']) for values in intervals.values() for entry in values)
    require(final['arm'] == 'A+' and final['launch_pass'] == 2 and
            stamp(final['value']['start']) < first_start < stamp(final['value']['stop']) and
            all(stamp(final['value']['start']) < time < stamp(final['value']['stop']) for time in starts.values()),
            'Both build services must have started during final A+ only')
    exposures = []
    affected = set()
    for row in evidence['requests']:
        result = row['result']
        build = row['build_boundary']
        boundaries = (stamp(build['before']['utc']), stamp(build['after']['utc']))
        require(boundaries[0] <= stamp(result['started']) <= boundaries[1], 'Build boundary timestamps differ from request')
        samples = [(validate_process(proc, starts, boundary_time), proc['process'])
                   for boundary_time, boundary in zip(boundaries, (build['before'], build['after']))
                   for proc in boundary['processes']]
        seen = sorted({unit for unit, _ in samples})
        compilers = sorted({unit for unit, process in samples if process in COMPILERS})
        possible = sorted(unit for unit, entries in intervals.items() if any(
            stamp(entry['start']) <= boundaries[1] and (entry['stop'] is None or stamp(entry['stop']) >= boundaries[0])
            for entry in entries))
        is_final = row['scope_id'] == final['artifact_id']
        require((is_final or not possible) and set(seen) <= set(possible), 'Unexpected build overlap in a prior scope')
        if is_final and boundaries[1] >= first_start:
            key = (result['prompt_tokens'], result['repeat'])
            if not result['discard']:
                affected.add(key)
            exposures.append(dict(result=row['artifact_id'], before=row['evidence']['before'], after=row['evidence']['after'],
                                  prompt_tokens=key[0], repeat=key[1], discard=result['discard'],
                                  before_utc=build['before']['utc'], after_utc=build['after']['utc'],
                                  possible_units=possible, units_seen=seen, compiler_units_seen=compilers))
    require(affected and any(row['units_seen'] for row in exposures), 'Screening needs actual observed build activity')
    quiet = []
    for size in (512, 2048):
        cells = {arm: {row['repeat']: row for row in accepted if row['arm'] == arm and row['prompt_tokens'] == size}
                 for arm in ('A+', 'C3')}
        labels = sorted((set(cells['A+']) & set(cells['C3'])) - {repeat for n, repeat in affected if n == size})
        require(set(range(1, 6)).issubset(labels), 'The verified arrival order must preserve the five forward pairs')
        saved = [cells['A+'][i]['ttft_s'] - cells['C3'][i]['ttft_s'] for i in labels]
        decode = [cells['C3'][i]['decode_tps'] - cells['A+'][i]['decode_tps'] for i in labels]
        quiet.append(dict(prompt_tokens=size, labels=labels, n=len(labels),
                          seconds_saved=dict(median=median(saved), range=[min(saved), max(saved)]),
                          decode_gained=dict(median=median(decode), range=[min(decode), max(decode)])))
    return dict(qualification='screening-final-control-build-overlap', services=services,
                journals=[dict(unit=row['unit'], artifact_id=row['artifact_id'], sha256=row['sha256'],
                               intervals=intervals[row['unit']]) for row in journal],
                first_activity_utc=first_start.isoformat(), exposed_requests=exposures, quiet_prefix=quiet)
