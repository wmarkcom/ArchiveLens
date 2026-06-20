from datetime import timezone

from app.services.platform.registry import resolve_platform_account_id
from app.services.platform.xueqiu import (
    extract_status_items,
    extract_xueqiu_uid,
    normalize_xueqiu_status,
    strip_xueqiu_html,
)


def test_extract_xueqiu_uid_from_profile_url():
    assert extract_xueqiu_uid("https://xueqiu.com/u/5672579962") == "5672579962"
    assert extract_xueqiu_uid("xueqiu.com/u/5672579962") == "5672579962"
    assert extract_xueqiu_uid("5672579962") == "5672579962"


def test_resolve_platform_account_id_keeps_weibo_and_adds_xueqiu():
    assert resolve_platform_account_id("weibo", None, "https://weibo.com/u/1002568141") == "1002568141"
    assert resolve_platform_account_id("xueqiu", None, "https://xueqiu.com/u/5672579962") == "5672579962"


def test_strip_xueqiu_html_preserves_readable_text():
    assert strip_xueqiu_html("第一行<br/>第二行&nbsp;<a href='/'>链接</a>") == "第一行\n第二行 链接"


def test_normalize_xueqiu_status():
    item = {
        "id": 370598996,
        "user_id": 5672579962,
        "source": "雪球",
        "title": "闷得而蜜雪球交流守则",
        "created_at": 1768287797000,
        "description": "正文<br/>第二行",
        "target": "/5672579962/370598996",
        "pic": "https://xqimg.imedao.com/example.png",
        "pic_sizes": [{"width": 2732, "height": 1534}],
        "edited_at": 1768288897000,
        "retweeted_status": {"description": "转发正文"},
    }

    post = normalize_xueqiu_status(item)

    assert post.platform == "xueqiu"
    assert post.platform_post_id == "370598996"
    assert post.original_url == "https://xueqiu.com/5672579962/370598996"
    assert post.published_at is not None
    assert post.published_at.tzinfo == timezone.utc
    assert post.title == "闷得而蜜雪球交流守则"
    assert post.full_text == "闷得而蜜雪球交流守则\n正文\n第二行"
    assert post.repost_text == "转发正文"
    assert post.image_urls == ["https://xqimg.imedao.com/example.png"]
    assert post.is_edited is True


def test_extract_status_items_from_payload():
    payload = {"statuses": [{"id": 1}, {"id": 2}, "bad"]}
    assert extract_status_items(payload) == [{"id": 1}, {"id": 2}]
