"""Regression coverage for foreign analytical text normalization."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.foreign_content_sanitizer import (
    detect_foreign_language,
    normalize_foreign_article,
    normalize_foreign_text,
)
from app.services.foreign_event_service import _build_groups, _detect_language, score_pair
from app.services.foreign_risk_service import _analysis_text, detect_language


def _article(article_id: int, source: str, title: str, summary: str, content: str):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=article_id,
        source_name_snapshot=source,
        source_key=source.casefold().replace(" ", "-"),
        title=title,
        summary=summary,
        content=content,
        url=f"https://fixture.test/{article_id}",
        content_hash=f"hash-{article_id}",
        duplicate_of_id=None,
        published_at=now,
        collected_at=now,
        created_at=now,
    )


def test_normalizer_decodes_entities_drops_resources_and_deduplicates_fields():
    raw = (
        "<div class='article'><p>China &ldquo;policy&rdquo; update</p>"
        "<img src='https://cdn.example/photo.jpg'><script>secret()</script>"
        "<p>正文内容&nbsp;正文内容</p></div>"
    )
    cleaned = normalize_foreign_text(raw)
    assert "policy" in cleaned
    assert "photo.jpg" not in cleaned
    assert "secret()" not in cleaned
    assert "&ldquo;" not in cleaned

    article = normalize_foreign_article("Repeated title", "Repeated title", "Repeated title\nBody")
    assert article.count("Repeated title") == 1
    assert article.endswith("Body")
    assert len(article) <= 12_000


def test_language_detection_ignores_brands_names_and_numbers_but_keeps_prose_mixed():
    chinese = "中国外交部回应 VOA NASA 与 Biden 会面，2026 年发布"
    mixed = "Shared crisis response article 中国"
    assert detect_foreign_language(chinese) == "zh"
    assert _detect_language(chinese) == "zh"
    assert detect_language(chinese) == "zh"
    assert detect_foreign_language(mixed) == "mixed"
    assert detect_foreign_language("The latest crisis response") == "en"
    assert detect_foreign_language("12345 ...") == "unknown"


def test_event_and_risk_inputs_share_clean_deduplicated_text():
    row = _article(
        1,
        "VOA Chinese",
        "<h1>中国政策更新</h1>",
        "中国政策更新",
        "<p>中国政策更新</p><img src='https://cdn.example/a.jpg'><p>正文</p>",
    )
    event_text = normalize_foreign_article(row.title, row.summary, row.content)
    assert _analysis_text(row) == event_text
    assert "cdn.example" not in event_text
    assert event_text.count("中国政策更新") == 1


def test_normalized_similarity_supports_same_language_multi_source_and_keeps_mixed_pending():
    left = _article(1, "Fox News", "<b>Shared crisis response</b>", "Shared crisis response", "<p>Leaders discussed the shared crisis response.</p>")
    right = _article(2, "The Guardian", "Shared crisis response", "Shared crisis response", "Leaders discussed the shared crisis response.")
    evidence = score_pair(left, right)
    assert evidence.score >= 0.72
    groups = _build_groups([left, right])
    assert groups and groups[0].language == "en"
    assert groups[0].confidence >= 0.72

    mixed_left = _article(3, "Fox News", "Shared crisis response 中国", "Shared crisis response 中国", "Shared crisis response 中国")
    mixed_right = _article(4, "The Guardian", "Shared crisis response 中国", "Shared crisis response 中国", "Shared crisis response 中国")
    mixed_groups = _build_groups([mixed_left, mixed_right])
    assert mixed_groups and mixed_groups[0].language == "mixed"
    assert mixed_groups[0].confidence < 0.55
