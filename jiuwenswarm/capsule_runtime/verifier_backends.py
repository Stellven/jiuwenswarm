"""Pluggable models for the worker (ctx.model) and the semantic verifier.

Both are callables ``(prompt, system=None) -> text``; the verifier calls with the
prompt only.

* command: a command line that reads the prompt on stdin and prints the reply
  (for example a ``codex exec`` wrapper). The system text, if any, is prepended.
* openai: any OpenAI-compatible /chat/completions endpoint, standard library only.

Nothing here runs unless a caller configures it. Flags are shared through
``add_arguments(parser, 'worker' | 'verifier')``.
"""
from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import urllib.request


class CommandModel:
    kind = 'cmd'
    last_usage = None
    last_model = None

    def __init__(self, command, *, timeout: float = 300.0):
        if isinstance(command, str):
            # posix=False keeps Windows backslashes; it also keeps the quotes, so strip them.
            self.argv = [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in ('"', "'") else t
                         for t in shlex.split(command, posix=(os.name != 'nt'))]
        else:
            self.argv = list(command)
        self.timeout, self.model_name = timeout, None
        self.identity = 'cmd:' + ' '.join(self.argv)

    async def __call__(self, prompt, system=None):
        text = prompt if not system else system + '\n\n' + prompt

        def run():
            done = subprocess.run(self.argv, input=text, capture_output=True, text=True, encoding='utf-8', timeout=self.timeout)
            if done.returncode != 0:
                raise RuntimeError('model command exited %d: %s' % (done.returncode, done.stderr.strip()[:300]))
            return done.stdout.strip()
        return await asyncio.to_thread(run)


class OpenAIModel:
    kind = 'api'
    last_usage = None
    last_model = None

    def __init__(self, base_url: str, model: str, *, api_key_env: str = 'OPENAI_API_KEY', timeout: float = 300.0):
        self.url, self.model_name, self.api_key_env, self.timeout = base_url.rstrip('/') + '/chat/completions', model, api_key_env, timeout
        self.identity = 'openai:' + base_url.rstrip('/') + '|' + model

    async def __call__(self, prompt, system=None):
        messages = ([{'role': 'system', 'content': system}] if system else []) + [{'role': 'user', 'content': prompt}]

        def run():
            body = json.dumps({'model': self.model_name, 'temperature': 0, 'messages': messages}).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
            if os.environ.get(self.api_key_env):
                headers['Authorization'] = 'Bearer ' + os.environ[self.api_key_env]
            with urllib.request.urlopen(urllib.request.Request(self.url, body, headers), timeout=self.timeout) as reply:
                return json.loads(reply.read().decode('utf-8'))
        data = await asyncio.to_thread(run)
        usage = data.get('usage') or {}
        self.last_usage = {'prompt': usage.get('prompt_tokens'), 'completion': usage.get('completion_tokens')} if usage else None
        self.last_model = data.get('model')
        return data['choices'][0]['message']['content']


# kept for callers that only want the verifier flavour
command_verifier, openai_verifier = CommandModel, OpenAIModel


def add_arguments(parser, role: str = 'verifier') -> None:
    parser.add_argument('--%s-cmd' % role, help='command that reads the %s prompt on stdin and prints the reply' % role)
    parser.add_argument('--%s-openai-base-url' % role, help='OpenAI-compatible base URL for the %s model' % role)
    parser.add_argument('--%s-model' % role, help='model name for --%s-openai-base-url' % role)
    if role == 'verifier':
        parser.add_argument('--require-semantic', action='store_true',
                            help='halt capsules that carry semantic review when no verifier model is configured')


def from_args(args, role: str = 'verifier'):
    command, url, model = (getattr(args, '%s_%s' % (role, key)) for key in ('cmd', 'openai_base_url', 'model'))
    if command:
        return CommandModel(command)
    if url:
        if not model:
            raise SystemExit('--%s-openai-base-url needs --%s-model' % (role, role))
        return OpenAIModel(url, model)
    return None
