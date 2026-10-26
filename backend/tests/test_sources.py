import json
from pathlib import Path
from types import SimpleNamespace as NS

from openai.types.chat import ChatCompletionMessage

from diary.agent import harvest

FIXTURE = Path(__file__).parent / "fixtures" / "message_with_annotations.json"


def test_recorded_openrouter_message_yields_titled_sources():
    message = ChatCompletionMessage.model_validate(json.loads(FIXTURE.read_text()))
    sources = harvest(message)
    assert sources[0] == {"title": "World | Latest News & Updates | BBC News",
                          "url": "https://www.bbc.com/news/world?form=MG0AV3"}
    assert all(s["url"].startswith("https://") for s in sources)


def test_flat_annotation_shape_is_accepted():
    message = NS(annotations=[NS(type="url_citation", url="https://a.com", title="A")])
    assert harvest(message) == [{"title": "A", "url": "https://a.com"}]


def test_duplicate_urls_are_dropped():
    cite = NS(url_citation=NS(url="https://a.com", title="A"))
    assert len(harvest(NS(annotations=[cite, cite]))) == 1


def test_non_http_schemes_are_dropped():
    bad = NS(url_citation=NS(url="javascript:alert(1)", title="x"))
    assert harvest(NS(annotations=[bad])) == []


def test_missing_title_falls_back_to_url():
    cite = NS(url_citation=NS(url="https://a.com", title=None))
    assert harvest(NS(annotations=[cite])) == [{"title": "https://a.com", "url": "https://a.com"}]


def test_at_most_five_sources():
    cites = [NS(url_citation=NS(url=f"https://a.com/{i}", title=str(i))) for i in range(8)]
    assert len(harvest(NS(annotations=cites))) == 5


def test_message_without_annotations_field_yields_empty_list():
    assert harvest(NS(content="hello")) == []
    assert harvest(NS(annotations=None)) == []
