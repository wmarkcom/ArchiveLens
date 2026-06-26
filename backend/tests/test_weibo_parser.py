from app.services.platform.weibo import (
    WeiboCollectOptions,
    WeiboAdapter,
    choose_weibo_full_text,
    clean_weibo_detail_text,
    extract_weibo_uid,
    has_weibo_auth_cookie,
    image_urls_from_status,
    is_truncated_status,
    normalize_weibo_status,
    parse_weibo_datetime,
    parse_weibo_json_body,
    strip_weibo_html,
)


def test_strip_weibo_html() -> None:
    assert strip_weibo_html('hello<br /><a href="//x">#tag#</a> ​​​ ...<span class="expand">展开</span>') == "hello #tag#"


def test_image_urls_from_status_prefers_large() -> None:
    item = {
        "pics": [
            {
                "url": "https://wx1.sinaimg.cn/orj360/a.jpg",
                "large": {"url": "https://wx1.sinaimg.cn/mw2000/a.jpg"},
            }
        ],
        "pic_ids": ["b"],
    }
    assert image_urls_from_status(item) == [
        "https://wx1.sinaimg.cn/mw2000/a.jpg",
        "https://wx1.sinaimg.cn/mw2000/b.jpg",
    ]


def test_normalize_weibo_status() -> None:
    item = {
        "id": 123,
        "mid": "456",
        "mblogid": "ABC",
        "created_at": "Wed Jun 10 14:36:59 +0800 2026",
        "text_raw": "正文",
        "source": "微博网页版",
    }
    post = normalize_weibo_status("1642512402", item)
    assert post.platform_post_id == "456"
    assert post.original_url == "https://weibo.com/1642512402/ABC"
    assert post.full_text == "正文"
    assert post.source == "微博网页版"


def test_choose_weibo_full_text_prefers_longer_detail() -> None:
    item = {"text_raw": "短正文"}

    assert choose_weibo_full_text(item, "短正文，详情页补全后的完整内容") == "短正文，详情页补全后的完整内容"


def test_choose_weibo_full_text_keeps_list_text_when_detail_is_shorter() -> None:
    item = {"text_raw": "列表接口里更完整的正文内容"}

    assert choose_weibo_full_text(item, "短正文") == "列表接口里更完整的正文内容"


def test_clean_weibo_detail_text_removes_translate_ui_noise() -> None:
    detail = "收盘了，商络没有走，小亏1个多点能接受 Translate content 喜欢我家小程😽😽 为TA助威"

    assert clean_weibo_detail_text(detail) == "收盘了，商络没有走，小亏1个多点能接受"


def test_clean_weibo_detail_text_keeps_normal_body() -> None:
    detail = "今天复盘：Translate 这个词如果出现在普通英文句子里不处理，因为不是完整 UI 文案。"

    assert clean_weibo_detail_text(detail) == detail


def test_parse_weibo_datetime_converts_to_utc() -> None:
    parsed = parse_weibo_datetime("Fri Jun 19 14:30:44 +0800 2026")
    assert parsed is not None
    assert parsed.isoformat() == "2026-06-19T06:30:44+00:00"


def test_is_truncated_status() -> None:
    assert is_truncated_status({"text": '...<span class="expand">展开</span>'})


def test_collect_options_defaults(tmp_path) -> None:
    options = WeiboCollectOptions(storage_state_path=tmp_path / "weibo.json", uid="1642512402")
    assert options.page_no == 1
    assert options.limit == 20
    assert options.detail_fallback_limit == 3
    assert options.detail_timeout_ms == 10000


def test_weibo_adapter_detail_candidates(tmp_path) -> None:
    adapter = WeiboAdapter(tmp_path / "weibo.json")
    normal_post = normalize_weibo_status("1642512402", {"id": 1, "mid": "1", "mblogid": "A", "text_raw": "正文"})
    truncated_post = normalize_weibo_status(
        "1642512402",
        {"id": 2, "mid": "2", "mblogid": "B", "text": '正文...<span class="expand">展开</span>'},
    )

    assert adapter.should_fetch_detail_for_monitor(normal_post, is_new=True)
    assert not adapter.should_fetch_detail_for_monitor(normal_post, is_new=False)
    assert adapter.should_fetch_detail_for_monitor(truncated_post, is_new=False)


def test_has_weibo_auth_cookie(tmp_path) -> None:
    state_file = tmp_path / "weibo.json"
    state_file.write_text(
        '{"cookies":[{"domain":".weibo.com","name":"SUB","value":"redacted"}]}',
        encoding="utf-8",
    )
    assert has_weibo_auth_cookie(state_file)


def test_extract_weibo_uid_from_profile_urls() -> None:
    assert extract_weibo_uid("1642512402") == "1642512402"
    assert extract_weibo_uid("https://weibo.com/u/1642512402") == "1642512402"
    assert extract_weibo_uid("https://weibo.com/1642512402/R3t77kc9F") == "1642512402"
    assert extract_weibo_uid("https://m.weibo.cn/u/1642512402") == "1642512402"
    assert extract_weibo_uid("https://weibo.com/profile?uid=1642512402") == "1642512402"


def test_parse_weibo_json_body_detects_passport_html() -> None:
    body = "<html><head><title>新浪通行证</title></head></html>".encode("gb18030")
    try:
        parse_weibo_json_body(body, "text/html")
    except RuntimeError as exc:
        assert "微博登录态已失效" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
