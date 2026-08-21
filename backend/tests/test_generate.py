from app.rag.generate import _exclude_already_covered_videos
from app.rag.retrieval import RetrievedChunk, VideoCandidate


def _chunk(video_id: str | None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="c1",
        source_id="s1",
        source_title="Fonte",
        video_id=video_id,
        video_title="Video citato",
        video_url="https://drive.google.com/x",
        video_platform="drive",
        video_preview_url=None,
        document_url=None,
        start_timestamp="00:01:00",
        end_timestamp=None,
        text="testo",
        score=0.8,
    )


def _candidate(video_id: str) -> VideoCandidate:
    return VideoCandidate(video_id=video_id, title="Titolo", url="https://drive.google.com/y", platform="drive")


def test_video_already_cited_is_not_also_suggested():
    # Trovato in test end-to-end: lo stesso video compariva sia in cited_sources (con
    # timestamp reale) sia in suggested_videos (senza), producendo due card duplicate.
    combined = [_chunk(video_id="video-1")]
    videos = [_candidate("video-1"), _candidate("video-2")]
    result = _exclude_already_covered_videos(videos, combined)
    assert [v.video_id for v in result] == ["video-2"]


def test_no_overlap_keeps_all_candidates():
    combined = [_chunk(video_id="video-9")]
    videos = [_candidate("video-1"), _candidate("video-2")]
    result = _exclude_already_covered_videos(videos, combined)
    assert [v.video_id for v in result] == ["video-1", "video-2"]


def test_chunks_without_video_do_not_exclude_anything():
    combined = [_chunk(video_id=None)]
    videos = [_candidate("video-1")]
    result = _exclude_already_covered_videos(videos, combined)
    assert [v.video_id for v in result] == ["video-1"]
