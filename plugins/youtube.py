import re2 as re


REJECT_LIST = [
    r"^https?:\/\/youtubei\.googleapis\.com\/youtubei\/v\d\/player\/ad_break",
    r"^https?:\/\/(www|s)\.youtube\.com\/api\/stats\/ads",
    r"^https?:\/\/(www|s)\.youtube\.com\/(pagead|ptracking)",
    r"^https?:\/\/s\.youtube\.com\/api\/stats\/qoe\?adcontext",
    r"^https?:\/\/[\w-]+\.googlevideo\.com\/(?!(dclk_video_ads|videoplayback\?)).+&oad"
]


REJECT_RE = re.compile("|".join(REJECT_LIST), flags=re.IGNORECASE)

REDIRECT_RE = re.compile("ctier=[A-Z]")
# REDIRECT_RE = re.compile(r"^https?:\/\/[\w-]+\.googlevideo\.com\/(?!dclk_video_ads).+?&ctier=L&.+?,ctier,.+")