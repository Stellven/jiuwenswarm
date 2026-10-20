"""Bounded approved deepsearch operator with immutable captured text.

API definitions: https://info.arxiv.org/help/api/user-manual.html and
https://api.semanticscholar.org/api-docs/ . No retry or recursive retrieval.
"""
from __future__ import annotations

import asyncio
import hashlib
import copy
import math
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable

import httpx

from .contracts import ResearchError,contract_schema,validate


def _require(condition,detail):
    if not condition:raise ResearchError('auth',detail)


class AcademicConnectors:
    def __init__(self, store, *, approved, timeout_s: float, tool_limit: int = 20,
                 before_tool: Callable | None = None, client=None, semantic_scholar_key: str | None = None):
        if (not set(approved) <= {'local_documents', 'arxiv', 'semantic_scholar'}
                or type(tool_limit) is not int or not 0 <= tool_limit <= 20
                or type(timeout_s) not in (int,float) or not math.isfinite(timeout_s) or timeout_s <= 0):
            raise ValueError('invalid protected connector authority')
        self.store, self.approved, self.timeout = store, frozenset(approved), timeout_s
        self.tool_limit, self.tool_calls, self.before_tool = tool_limit, 0, before_tool
        self.client, self.key = client, semantic_scholar_key
        self._last_arxiv = 0.0

    def bind_invocation(self, contract_ref, invocation_id, contract, *, before_tool):
        """Narrow the installed operator to one frozen Search invocation."""
        kind=self.store.record_kind(contract_ref)
        _require(kind in {'subnode-execution-contract','evaluation-subnode-context'}
            and self.store.read_record(contract_ref)==contract,'Search binding differs from its exact original child')
        validate('subnode-execution-contract' if kind=='subnode-execution-contract'
            else 'urn:ai4r:private:evaluation-subnode-context:1',contract)
        _require(len(contract['bindings'])==1,'Search has no exact single original binding')
        rows = [row for row in contract['inputs'] if row['name'] == 'search_scope']
        binding=contract['bindings'][0];authority = binding['effective_authority']
        if (not invocation_id or not callable(before_tool) or len(rows) != 1
                or len(rows[0]['artifact_refs']) != 1 or 'deepsearch' not in authority['tools']):
            raise ResearchError('auth', 'Search requires its protected invocation binding')
        declaration=self.store.read_record(binding['declaration_ref'],contract_id='capsule-declaration')
        template_ref=contract['template_ref'] if kind=='subnode-execution-contract' else contract['source_template_ref']
        _require(self.store.record_kind(template_ref)=='subnode-template','Search lacks its original assigned template')
        template=self.store.read_record(template_ref)
        _require(self.store.record_kind(binding['admission_ref'])=='library-admission','Search has no original captured admission')
        admission=self.store.read_record(binding['admission_ref'],contract_id='library-admission')
        tool_ceiling=declaration['budget']['per_call'].get('tool_calls')
        _require(template['capsule_ref']==binding['declaration_ref']==admission['candidate_ref']
            and template['admission_ref']==binding['admission_ref'] and admission['status']=='admitted'
            and any(row['kind'] in {'operator','tool'} and row['identifier']=='deepsearch' for row in declaration['needs']['external'])
            and type(tool_ceiling) is int and 0<tool_ceiling<=20,
            'Search operator/tool allowance differs from its original admitted declaration')
        scope_ref=rows[0]['artifact_refs'][0]
        _require(contract_schema(rows[0]['contract_id'])==contract_schema('search-scope')
            and scope_ref in contract['input_refs'] and scope_ref in authority['resource_reads']
            and self.store.record_kind(scope_ref)=='search-scope','Search scope lacks its exact typed input/read association')
        scope = self.store.read_record(scope_ref, contract_id='search-scope')
        briefs=[row for row in contract['inputs'] if row['name']=='brief']
        _require(len(briefs)==1 and briefs[0]['artifact_refs']==[scope['brief_ref']]
            and contract_schema(briefs[0]['contract_id'])==contract_schema('research-brief'),
            'Search scope names another original Brief')
        parent=self.store.read_record(contract['node_contract_ref'],contract_id='node-execution-contract'
            if kind=='subnode-execution-contract' else 'urn:ai4r:private:evaluation-node-context:1')
        _require(all(ref in parent['authority_ceiling']['resource_reads'] for ref in scope['local_document_refs']),
            'Search local document exceeds its original whole-parent read ceiling')
        for ref in scope['local_document_refs']:
            raw=self.store.read_blob(ref)
            _require(not raw.startswith(b'%PDF-') and bool(raw.strip()),'Search requires actual captured extracted UTF-8 local text')
            try:raw.decode('utf-8',errors='strict')
            except UnicodeError as error:raise ResearchError('auth','Search local document is not captured UTF-8 text') from error
        approved = self.approved.intersection(scope['connectors'])
        hosts = {'arxiv': 'export.arxiv.org', 'semantic_scholar': 'api.semanticscholar.org'}
        approved = {name for name in approved if name == 'local_documents' or
                    (authority['network'] == 'allowlist' and hosts[name] in authority['network_allowlist'])}

        async def claim(connector, query):
            value = before_tool('deepsearch')
            if hasattr(value, '__await__'): value = await value
            self.store.append_record('search_query', {'contract_ref': contract_ref, 'invocation_id': invocation_id,
                'run_id': contract['run_id'], 'connector': connector, 'query': query, 'claim_ref': value})

        operator = AcademicConnectors(self.store, approved=approved, timeout_s=self.timeout,
            tool_limit=min(self.tool_limit,tool_ceiling),
            before_tool=claim, client=self.client, semantic_scholar_key=self.key)
        return _BoundSearch(operator, scope)

    async def _request(self, connector, query, hits):
        if self.tool_calls >= self.tool_limit:
            raise ResearchError('budget_exhausted', 'Search connector tool ceiling reached')
        if self.before_tool:
            result = self.before_tool(connector, query)
            if hasattr(result, '__await__'):
                await result
        self.tool_calls += 1
        if connector == 'local_documents':
            return None
        if connector == 'arxiv':
            # arXiv's documented API rate spacing; never turn throttling into retry.
            await asyncio.sleep(max(0, 3 - (time.monotonic() - self._last_arxiv)))
            self._last_arxiv = time.monotonic()
            url, params, headers = 'https://export.arxiv.org/api/query', {'search_query': 'all:' + query, 'start': 0, 'max_results': hits}, {}
        else:
            url, params = 'https://api.semanticscholar.org/graph/v1/paper/search', {'query': query, 'limit': hits, 'fields': 'title,abstract,url'}
            headers = {'x-api-key': self.key} if self.key else {}
        owned = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout, follow_redirects=False, trust_env=False)
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            self.store.append_record('search_response', {'connector': connector, 'query': query,
                                    'response_ref': self.store.put_blob(response.content), 'status': response.status_code})
            if connector == 'arxiv':
                # stdlib parser rejects external entity references; no DTD fetch.
                root = ET.fromstring(response.content)
                ns = {'a': 'http://www.w3.org/2005/Atom'}
                return [{'title': e.findtext('a:title', default='', namespaces=ns).strip(),
                         'text': e.findtext('a:summary', default='', namespaces=ns).strip(),
                         'locator': e.findtext('a:id', default='', namespaces=ns)} for e in root.findall('a:entry', ns)][:hits]
            value = response.json()
            return [{'title': e.get('title') or 'Untitled academic source', 'text': e.get('abstract') or '',
                     'locator': e.get('url') or e.get('paperId') or ''} for e in value.get('data', [])][:hits]
        finally:
            if owned:
                await client.aclose()

    async def retrieve(self, scope, queries):
        _require(type(queries) is list and 1<=len(queries)<=scope['max_queries']
            and all(type(query) is str and 3<=len(query)<=200 for query in queries)
            and len(queries)==len(set(queries)),'Search query population exceeds its original frozen bounds')
        citations, outcomes = [], []
        # One outcome per declared connector. Each query is used once in order.
        for connector in scope['connectors']:
            if connector not in self.approved:
                outcomes.append({'connector': connector, 'status': 'unavailable', 'reason': 'Connector access has not been qualified', 'citations_captured': 0})
                continue
            count, failures = 0, []
            for query in queries:
                try:
                    results = await asyncio.wait_for(self._request(connector, query, scope['max_hits_per_query']), self.timeout)
                    if connector == 'local_documents':
                        results = []
                        for ref in scope['local_document_refs']:
                            raw = self.store.read_blob(ref)
                            text = raw.decode('utf-8')
                            terms = re.findall(r'\w+', query)
                            if terms and all(re.search(re.escape(t), text, re.IGNORECASE) for t in terms):
                                offset=max(0,min(re.search(re.escape(t),text,re.IGNORECASE).start() for t in terms)-100)
                                results.append({'title': ref['id'][:300], 'text': text, 'locator': ref['id'][:300], 'ref': ref,'offset':offset})
                    for result in results:
                        text = result['text']
                        if not text:
                            continue
                        ref = result.get('ref') or self.store.put_blob(text.encode('utf-8'), media_type='text/plain',
                                provenance={'connector': connector, 'query': query, 'origin': result['locator']})
                        offset=result.get('offset',0);excerpt = text[offset:offset+2000]
                        citations.append({'id': 'citation:' + str(len(citations) + 1), 'source_ref': ref, 'connector': connector,
                                          'query': query, 'title': result['title'][:300], 'locator': result['locator'][:300],
                                          'char_start': offset, 'char_end': offset+len(excerpt), 'excerpt': excerpt,
                                          'excerpt_sha256': hashlib.sha256(excerpt.encode('utf-8')).hexdigest()})
                        count += 1
                except ResearchError:
                    raise  # budget/integrity refusal is never connector fallback
                except (httpx.HTTPError, TimeoutError, UnicodeError, ET.ParseError, ValueError, KeyError) as exc:
                    failures.append(type(exc).__name__)
            outcomes.append({'connector': connector, 'status': 'used' if count or not failures else 'unavailable',
                             'reason': 'Captured bounded query results' if not failures else 'Bounded connector limitation: ' + ','.join(sorted(set(failures))),
                             'citations_captured': count})
        return citations, outcomes


class _BoundSearch:
    __slots__ = ('__operator', '__scope','__consumed')

    def __init__(self, operator, scope):
        self.__operator, self.__scope = operator, copy.deepcopy(scope)
        self.__consumed=False

    async def retrieve(self, scope, queries):
        if scope != self.__scope:
            raise ResearchError('auth', 'Search scope differs from the frozen named input')
        if self.__consumed:
            raise ResearchError('attempt_already_claimed','Search invocation already issued its one query round')
        self.__consumed=True
        return await self.__operator.retrieve(copy.deepcopy(self.__scope),list(queries))
