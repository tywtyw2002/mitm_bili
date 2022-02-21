# from mitmproxy.script import concurrent
from mitmproxy import http
from mitmproxy.proxy import layer, server_hooks
from mitmproxy.proxy.layers import tls
import re2

from plugins import bili
from plugins import youtube


# def next_layer(data: layer.NextLayer):
#     print("next_layer", data)


# def server_connect(data: server_hooks.ServerConnectionHookData):
#     print("server_connect", data)


def tls_clienthello(data: tls.ClientHelloData):
    # if data.context.server.address is None:
    if data.context.server.address[0] == '1.1.1.100':
        sni = data.context.client.sni
        data.context.server.sni = sni
        data.context.server.address = (sni, 443)
        # data.context.server.address = bili.DNS_MAP[sni]


def request(flow: http.HTTPFlow) -> None:
    if flow.request.pretty_host.startswith(bili.DNS_HOST):
        bili.process_http_dns(flow)
    elif youtube.REJECT_RE.match(flow.request.pretty_url):
        # print(flow.request.pretty_url)
        flow.kill()
    elif flow.request.pretty_host.endswith(".googlevideo.com"):
        if youtube.REDIRECT_RE.search(flow.request.pretty_url):
            redirect_url = youtube.REDIRECT_RE.sub('ctier=A', flow.request.pretty_url)
            flow.request.url = redirect_url
            print(flow.request.pretty_url)


def response(flow: http.HTTPFlow):
    if bili.CTX_RE.match(flow.request.pretty_url):
        bili.process_response(flow)