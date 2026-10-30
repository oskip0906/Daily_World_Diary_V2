import json

from diary.sources import espn


def game(home, away, home_score, away_score, note=None, completed=True, series=None, recap=None, records=()):
    """Shape of an event in ESPN's /scoreboard response, trimmed to the fields the parser reads."""
    def side(name, score, other, rec):
        return {"team": {"displayName": name}, "score": score, "winner": int(score) > int(other)} | (
            {"records": [{"summary": rec}]} if rec else {})
    home_rec, away_rec = records or (None, None)
    comp = {"competitors": [side(home, home_score, away_score, home_rec), side(away, away_score, home_score, away_rec)],
            "notes": [{"headline": note}] if note else []}
    if series:
        comp["series"] = {"type": "playoff", "summary": series}
    if recap:
        comp["headlines"] = [{"shortLinkText": recap}]
    return {"competitions": [comp], "status": {"type": {"completed": completed}},
            "links": [{"href": f"https://www.espn.com/game/{home}"}]}


def article(headline, published):
    return {"headline": headline, "published": published, "description": "d",
            "links": {"web": {"href": f"https://www.espn.com/story/{headline}"}}}


def test_scores_put_the_winner_first_and_skip_unfinished_games():
    board = {"events": [game("Rays", "Brewers", "1", "4", "World Series - Game 5", series="MIL wins series 4-1",
                             recap="Brewers win their first title", records=("98-64", "103-59")),
                        game("Hawks", "Heat", "0", "0", completed=False)]}
    [item] = espn.parse_scores(board, "MLB")
    assert item.title == "MLB: Brewers (103-59) 4, Rays (98-64) 1. Brewers win their first title"
    assert item.detail == "World Series - Game 5 · MIL wins series 4-1"
    assert item.url == "https://www.espn.com/game/Rays"


def test_a_routine_game_has_no_detail_so_it_does_not_jump_the_queue():
    [item] = espn.parse_scores({"events": [game("Hawks", "Heat", "117", "129", recap="Heat win")]}, "NBA")
    assert (item.title, item.detail) == ("NBA: Heat 129, Hawks 117. Heat win", "")


def test_gather_leads_with_noted_games_and_keeps_news_in_the_window(monkeypatch):
    def fake_get(url):
        if "baseball/mlb/scoreboard" in url:
            assert "dates=20261028" in url
            return json.dumps({"events": [game("A", "B", "2", "1"), game("Rays", "Brewers", "1", "4", "World Series")]})
        if "football/nfl/news" in url:
            return json.dumps({"articles": [article("fresh", "2026-10-29T11:00:00Z"),
                                            article("stale", "2026-10-27T11:00:00Z")]})
        return json.dumps({})
    monkeypatch.setattr(espn, "get", fake_get)
    titles = [i.title for i in espn.gather("2026-10-29").items]
    assert titles == ["MLB: Brewers 4, Rays 1", "MLB: A 2, B 1", "NFL: fresh"]
