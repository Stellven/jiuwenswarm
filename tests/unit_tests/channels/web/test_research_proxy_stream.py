"""Bounded original-byte proxy forwarding and disconnect cleanup."""
import io
import os
import unittest
from email.message import Message
from unittest.mock import patch

from jiuwenswarm.channels.web import app_web


class ProxyStreamingTests(unittest.TestCase):
    def handler(self,path='/api/v1/runs/run%3Aone/artifacts/artifact'):
        handler=app_web._SpaStaticHandler.__new__(app_web._SpaStaticHandler)
        handler.command='GET';handler.path=path;handler.api_target='http://upstream:19000'
        handler.headers=Message();handler.headers['Host']='127.0.0.1:5175'
        handler.headers['Authorization']='Bearer controlled-fixture'
        handler.headers['X-Forwarded-Host']='untrusted.example'
        handler.wfile=io.BytesIO();handler.rfile=io.BytesIO();handler.close_connection=False
        handler.sent=[];handler.response_headers=[];handler.errors=[]
        handler.send_response=lambda status,reason:handler.sent.append((status,reason))
        handler.send_header=lambda key,value:handler.response_headers.append((key,value))
        handler.end_headers=lambda:None
        handler.log_error=lambda *args:handler.errors.append(args)
        return handler

    def upstream(self,handler,raw,*,declared=True):
        class Upstream:
            status=200;reason='OK';calls=0
            def __init__(self):self.stream=io.BytesIO(raw)
            def getheaders(self):
                return [('Content-Type','application/octet-stream'),('X-Content-SHA256','fixture-digest')]+(
                    [('Content-Length',str(len(raw)))] if declared else [('Transfer-Encoding','chunked')])
            def getheader(self,name):return dict(self.getheaders()).get(name)
            def read(self,amount=None):
                self.calls+=1
                if amount is None:raise AssertionError('original-byte proxy performed an unbounded read')
                if not handler.sent:raise AssertionError('proxy read bytes before publishing status')
                if self.stream.tell() and handler.wfile.getvalue()!=raw[:self.stream.tell()]:
                    raise AssertionError('proxy buffered bytes instead of forwarding each chunk')
                return self.stream.read(amount)
        return Upstream()

    def test_artifact_and_archive_preserve_exact_bytes_headers_and_context(self):
        for path in ('/api/v1/runs/run%3Aone/artifacts/artifact','/api/v1/runs/run%3Aone/export?audience=researcher',
                     '/api/v1/evaluation/requests/request%3Aone?audience=researcher'):
            handler=self.handler(path);raw=b'original bytes\x00'*14000;upstream=self.upstream(handler,raw)
            handler.headers['Accept']='application/zip'
            with patch.dict(os.environ,{'JIUWENSWARM_M1_PROFILE':'1','JIUWENSWARM_M1_ORIGIN':'http://127.0.0.1:5175'}), patch.object(app_web.http.client,'HTTPConnection') as connection:
                connection.return_value.getresponse.return_value=upstream
                handler._proxy_http()
                self.assertEqual(handler.wfile.getvalue(),raw)
                self.assertGreater(upstream.calls,2)
                self.assertEqual(handler.sent,[(200,'OK')]);self.assertFalse(handler.errors)
                self.assertIn(('Content-Length',str(len(raw))),handler.response_headers)
                forwarded=connection.return_value.request.call_args.kwargs['headers']
                self.assertEqual(forwarded['Host'],'127.0.0.1:5175')
                self.assertEqual(forwarded['Authorization'],'Bearer controlled-fixture')
                self.assertNotIn('X-Forwarded-Host',forwarded)
                self.assertEqual(connection.call_args.kwargs['timeout'],300)
                connection.return_value.close.assert_called_once()

    def test_only_exact_bearer_evaluation_posts_receive_finite_transport_window(self):
        cases=[('POST','/api/v1/evaluation/single-cc',True,660),
               ('POST','/api/v1/evaluation/node-replay?fixed=1',True,660),
               ('GET','/api/v1/evaluation/single-cc',True,30),
               ('POST','/api/v1/evaluation/single-cc/extra',True,30),
               ('POST','/api/evaluation/single-cc',True,30),
               ('POST','/api/v1/evaluation/single-cc',False,30),
               ('GET','/api/v1/evaluation/requests/one',True,30),
               ('POST','/api/v1/runs',True,30)]
        for method,path,bearer,timeout in cases:
            with self.subTest(method=method,path=path,bearer=bearer):
                handler=self.handler(path);handler.command=method
                if not bearer:del handler.headers['Authorization']
                with patch.dict(os.environ,{'JIUWENSWARM_M1_PROFILE':'1','JIUWENSWARM_M1_ORIGIN':'http://127.0.0.1:5175'}),patch.object(app_web.http.client,'HTTPConnection') as connection:
                    upstream=connection.return_value.getresponse.return_value
                    upstream.status=200;upstream.reason='OK';upstream.getheaders.return_value=[];upstream.read.return_value=b'{}'
                    handler._proxy_http()
                    self.assertEqual(connection.call_args.kwargs['timeout'],timeout)
                    self.assertEqual(handler.wfile.getvalue(),b'{}')

    def test_evaluation_archive_requires_exact_get_or_head_route_and_zip_accept(self):
        for method,path,bearer,accept in [('POST','/api/v1/evaluation/requests/one',True,'application/zip'),
                                         ('GET','/api/v1/evaluation/requests/one/export',True,'application/zip'),
                                         ('GET','/api/v1/evaluation/requests/one',False,'application/zip'),
                                         ('GET','/api/v1/evaluation/requests/one',True,'application/json')]:
            handler=self.handler(path);handler.command=method;handler.headers['Accept']=accept
            if not bearer:del handler.headers['Authorization']
            with patch.dict(os.environ,{'JIUWENSWARM_M1_PROFILE':'1','JIUWENSWARM_M1_ORIGIN':'http://127.0.0.1:5175'}),patch.object(app_web.http.client,'HTTPConnection') as connection:
                upstream=connection.return_value.getresponse.return_value
                upstream.status=200;upstream.reason='OK';upstream.getheaders.return_value=[];upstream.read.return_value=b'{}'
                handler._proxy_http()
                self.assertEqual(connection.call_args.kwargs['timeout'],30)
                upstream.read.assert_called_once_with()

    def test_disconnect_stops_upstream_without_appending_error_response(self):
        handler=self.handler();upstream=self.upstream(handler,b'bytes'*50000)
        class Disconnected:
            def write(self,value):raise BrokenPipeError()
        handler.wfile=Disconnected()
        with patch.dict(os.environ,{'JIUWENSWARM_M1_PROFILE':'1','JIUWENSWARM_M1_ORIGIN':'http://127.0.0.1:5175'}), patch.object(app_web.http.client,'HTTPConnection') as connection:
            connection.return_value.getresponse.return_value=upstream
            handler._proxy_http()
            self.assertEqual(upstream.calls,1);self.assertTrue(handler.close_connection)
            self.assertEqual(handler.sent,[(200,'OK')]);self.assertFalse(handler.errors)
            connection.return_value.close.assert_called_once()

    def test_unknown_length_is_close_delimited_and_origin_check_still_refuses(self):
        handler=self.handler();upstream=self.upstream(handler,b'bytes',declared=False)
        with patch.dict(os.environ,{'JIUWENSWARM_M1_PROFILE':'1','JIUWENSWARM_M1_ORIGIN':'http://127.0.0.1:5175'}), patch.object(app_web.http.client,'HTTPConnection') as connection:
            connection.return_value.getresponse.return_value=upstream;handler._proxy_http()
            self.assertTrue(handler.close_connection)
            self.assertIn(('Connection','close'),handler.response_headers)
            self.assertNotIn(('Transfer-Encoding','chunked'),handler.response_headers)
            refused=self.handler();refused.headers.replace_header('Host','foreign.example')
            refused._write_proxy_error=lambda status,message:refused.sent.append((status,message))
            connection.reset_mock();refused._proxy_http()
            self.assertEqual(refused.sent,[(403,'native origin is not authorized')]);connection.assert_not_called()


if __name__=='__main__':unittest.main()
