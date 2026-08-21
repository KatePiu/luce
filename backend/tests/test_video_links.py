from app.rag.video_links import build_video_open_url


def test_youtube_deep_link_appends_timestamp_seconds():
    url = build_video_open_url("https://youtube.com/watch?v=abc", "youtube", "00:05:11")
    assert url == "https://youtube.com/watch?v=abc&t=311s"


def test_youtube_deep_link_with_no_existing_query_string():
    url = build_video_open_url("https://youtu.be/abc", "youtube", "01:02:03")
    assert url == "https://youtu.be/abc?t=3723s"


def test_vimeo_deep_link_appends_fragment():
    url = build_video_open_url("https://vimeo.com/12345", "vimeo", "00:01:05")
    assert url == "https://vimeo.com/12345#t=65s"


def test_drive_has_no_deep_link_support_returns_plain_url():
    url = build_video_open_url("https://drive.google.com/file/d/x/view", "drive", "00:05:11")
    assert url == "https://drive.google.com/file/d/x/view"


def test_missing_timestamp_returns_plain_url_unchanged():
    url = build_video_open_url("https://youtube.com/watch?v=abc", "youtube", None)
    assert url == "https://youtube.com/watch?v=abc"


def test_malformed_timestamp_does_not_invent_a_deep_link():
    url = build_video_open_url("https://youtube.com/watch?v=abc", "youtube", "not-a-timestamp")
    assert url == "https://youtube.com/watch?v=abc"
