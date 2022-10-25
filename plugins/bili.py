import re2 as re
import json
import gzip
import sys


ViewReply = None


try:
    sys.path.append('proto/')
    import bilibili.app.view.v1.view_pb2 as _view
    ViewReply = _view.ViewReply()
except Exception as e:
    print('Failed to load GRPC', e)


from mitmproxy import http


KV_STORAGE = {
    'storyAidKey': ""
}


BLOCK_RULES = []
CONTENT_FILTER_RULES = [
    r"^https?:\/\/app\.bilibili\.com\/x\/v2\/feed\/index",
    r"^https?:\/\/api\.bilibili\.com\/pgc\/page\/bangumi",
    r"^https?:\/\/api\.live\.bilibili\.com\/xlive\/app-room\/v1\/index\/getInfoByRoom",
    r"^https?:\/\/api\.vc\.bilibili\.com\/dynamic_svr\/v1\/dynamic_svr\/dynamic_(history|new)\?",
    r"^https?:\/\/app\.bilibili\.com\/x\/v2\/splash\/list",
    r"^https?:\/\/app\.bilibili\.com\/x\/resource\/show\/tab",
    r"^https?:\/\/app\.bilibili\.com\/x\/v2\/account\/mine",
    r"^https:\/\/app\.bilibili\.com\/bilibili\.app\.(view\.v1\.View\/View|dynamic\.v2\.Dynamic\/DynAll)$",
    r"^https:\/\/grpc\.biliapi\.net\/bilibili\.app\.(view\.v1\.View\/View|dynamic\.v2\.Dynamic\/DynAll)$"
]

DNS_HOST = "203.107.1."
DNS_OVERRIDE = [
    'api.bilibili.com',
    'app.bilibili.com',
    'api.vc.bilibili.com',
    'api.live.bilibili.com',
    'grpc.biliapi.net'
]

# DNS_MAP = {
#     "api.bilibili.com": "148.153.56.163",
#     "app.bilibili.com": "148.153.56.162",
#     "api.vc.bilibili.com": "23.236.97.62",
#     "api.live.bilibili.com": "23.236.97.62"
# }


CTX_RE = re.compile("|".join(CONTENT_FILTER_RULES), flags=re.IGNORECASE)
DNS_RE = re.compile(r"^/\d+\/resolve\?host=(.+?)&query")


def bill_grpc_process(content):
    if not content or ViewReply is None:
        return content

    # decompress
    data = gzip.decompress(content[5:])

    # proto
    ViewReply.ParseFromString(data)

    del ViewReply.cms[:]

    rm_ids = []

    for idx, ele in enumerate(ViewReply.relates):
        if ele.goto == 'cm':
            rm_ids.append(idx)

    if rm_ids:
        rm_ids.reverse()
        for idx in rm_ids:
            del ViewReply.relates[idx]

    # repack
    data = ViewReply.SerializeToString()
    data = gzip.compress(data, 0, mtime=0)
    data_len = len(data)
    content = content[:2] + data_len.to_bytes(3, 'big') + data

    return content


def process_http_dns(flow: http.HTTPFlow):
    m = DNS_RE.match(flow.request.path)
    if m:
        dns = []
        domains = m.group(1).split(',')
        for domian in domains:
            if domian in DNS_OVERRIDE:
                dns.append({
                    "host": domian,
                    "client_ip": '166.111.4.100',
                    "ips": ['1.1.1.100'],
                    "type": 1,
                    "ttl": 80,
                    "origin_ttl": 90
                })

        if dns:
            flow.response = http.Response.make(
                200,
                json.dumps({"dns": dns}).encode('utf-8'),
                {"Content-Type": "application/json; charset=utf-8"}
            )


def process_response(flow: http.HTTPFlow):
    # 推荐去广告，最后问号不能去掉，以免匹配到story模式
    if re.match(
        r"^https:\/\/app\.bilibili\.com\/x\/v2\/feed\/index\?",
        flow.request.pretty_url
    ):
        obj = flow.response.json()
        items = []
        for item in obj['data']['items']:
            if item.get('banner_item', ""):
                banner_items = []
                for banner in item["banner_item"]:
                    if banner['type'] == 'ad':
                        continue
                    elif banner.get('static_banner', False) \
                        and banner['static_banner'].get(
                            'is_ad_loc', False) is not True:
                        banner_items.append(banner)
                if banner_items:
                    item['banner_items'] = banner_items;
                    items.append(item)
            elif not item.get('ad_info', False) \
                and item.get('card_goto', "").find('ad') < 0 \
                and (
                    item['card_type'] in ['small_cover_v2', 'large_cover_v1', 'large_cover_single_v9']):
                items.append(item)

        obj['data']['items'] = items
        flow.response.content = json.dumps(obj).encode("utf-8")

    # 匹配story模式，用于记录Story的aid
    elif re.match(
        r"^https:\/\/app\.bilibili\.com\/x\/v2\/feed\/index\/story\?",
        flow.request.pretty_url
    ):
        obj = flow.response.json()
        last_item = obj['data']['items'][-1]
        KV_STORAGE['storyAidKey'] = str(last_item['stat']['aid'])

    # 开屏广告处理
    elif re.match(
        r"^https?:\/\/app\.bilibili\.com\/x\/v2\/splash\/list",
        flow.request.pretty_url
    ):
        obj = flow.response.json()
        obj["data"]['max_time'] = 0
        obj["data"]["min_interval"] = 31536000
        obj["data"]["pull_interval"] = 31536000
        for i in range(len(obj["data"]["list"])):
            obj["data"]["list"][i]["duration"] = 0
            obj["data"]["list"][i]["begin_time"] = 1915027200
            obj["data"]["list"][i]["end_time"] = 1924272000

        flow.response.content = json.dumps(obj).encode("utf-8")

    # 标签页处理，如去除会员购等等
    # elif re.match(
    #     r"^https?:\/\/app\.bilibili\.com\/x\/resource\/show\/tab",
    #     flow.request.pretty_url
    # ):
    # 我的页面处理，去除一些推广按钮
    # r"^https?:\/\/app\.bilibili\.com\/x\/v2\/account\/mine"
    # 直播去广告
    elif re.match(
        r"^https?:\/\/api\.live\.bilibili\.com\/xlive\/app-room\/v1\/index\/getInfoByRoom",
        flow.request.pretty_url
    ):
        obj = flow.response.json()
        obj["data"]["activity_banner_info"] = None
        flow.response.content = json.dumps(obj).encode("utf-8")

    # 追番去广告
    # elif re.match(
    #     r"^https?:\/\/api\.bilibili\.com\/pgc\/page\/bangumi",
    #     flow.request.pretty_url
    # ):

    # 动态去广告
    elif re.match(
        r"^https?:\/\/api\.vc\.bilibili\.com\/dynamic_svr\/v1\/dynamic_svr\/dynamic_(history|new)\?",
        flow.request.pretty_url
    ):
        obj = flow.response.json()
        cards = []

        for ele in obj['data']['cards']:
            if ele.get('display', None) and ele['card'].find("ad_ctx") <= 0:
                ele["desc"]["dynamic_id"] = ele["desc"]["dynamic_id_str"]
                ele["desc"]["pre_dy_id"] = ele["desc"]["pre_dy_id_str"]
                ele["desc"]["orig_dy_id"] = ele["desc"]["orig_dy_id_str"]
                ele["desc"]["rid"] = ele["desc"]["rid_str"]
                cards.append(ele)

        obj['data']['cards'] = cards
        flow.response.content = json.dumps(obj).encode("utf-8")

    # 去除统一设置的皮肤
    elif re.match(
        r"^https?:\/\/app\.bilibili\.com\/x\/resource\/show\/skin\?",
        flow.request.pretty_url
    ):
        obj = flow.response.json()
        if obj and obj.get('data', None):
            obj['data']['common_equip'] = {}

        flow.response.content = json.dumps(obj).encode("utf-8")

    # grpc
    elif re.search(
        r"bilibili\.app\.(view\.v1\.View\/View|dynamic\.v2\.Dynamic\/DynAll)$",
        flow.request.pretty_url
    ):
        flow.response.content = bill_grpc_process(flow.response.content)