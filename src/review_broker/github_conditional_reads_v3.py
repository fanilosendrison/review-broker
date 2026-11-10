"""Fresh authenticated HTTP conditional GETs, never stale permissions or mutation responses."""
from collections import OrderedDict
from urllib.request import Request

from .github_http_live_v3 import HttpResponseV3


class GitHubConditionalReadsV3:
    """RFC 9110/9111 validator reuse. Every call still reaches the provider once.

    Credentials partition representations. No cache-on-error, redirect cache,
    POST cache, retries or TTL-based acceptance. Paginated Link responses are not
    retained. A 304 without an exact prior authenticated representation refuses.
    """
    def __init__(self,executor):
        self.executor=executor;self._entries=OrderedDict();self._bytes=0

    def __call__(self,request):
        if request.get_method()!='GET' or request.data is not None:return self.executor(request)
        headers={k.lower():v for k,v in request.header_items()}
        key=(request.full_url,headers.get('authorization'),headers.get('accept'),headers.get('x-github-api-version'))
        prior=self._entries.get(key)
        outgoing=request
        if prior is not None:
            outgoing=Request(request.full_url,method='GET',headers=dict(request.header_items()))
            outgoing.add_header('If-None-Match',prior[0])
        response=self.executor(outgoing)
        if type(response) is not HttpResponseV3:return response
        if response.status==304:
            if prior is None:raise ValueError('UNRECOGNIZED_CONDITIONAL_GITHUB_RESPONSE')
            self._entries.move_to_end(key)
            return HttpResponseV3(200,prior[1].body,{**prior[1].headers,**response.headers})
        if prior is not None:
            self._bytes-=len(prior[1].body);del self._entries[key]
        etags=[v for k,v in response.headers.items() if k.lower()=='etag']
        if (response.status==200 and type(response.body) is bytes and len(response.body)<=1_000_000
                and len(etags)==1 and etags[0] and '\r' not in etags[0] and '\n' not in etags[0]
                and not any(k.lower()=='link' for k in response.headers)):
            self._entries[key]=(etags[0],response);self._bytes+=len(response.body)
            while len(self._entries)>256 or self._bytes>32_000_000:
                _,(_,old)=self._entries.popitem(last=False);self._bytes-=len(old.body)
        return response
