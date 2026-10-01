from surprise.genres import genres, off_key


def item(title, venue="", lead_text=None, source_genre=None):
    return {"activity": {"title": title, "venue": {"name": venue}}, "lead_text": lead_text, "source_genre": source_genre, "enrichment": {}}


def test_the_source_genre_comes_first_then_the_title_then_the_texts():
    assert genres(item("Seb Joulie Group", source_genre="jazz")) == ["jazz"]
    assert genres(item("Hip-Hop & Dancehall Party")) == ["rap", "latino"]
    assert genres(item("Mica Millar", lead_text="Une voix soul, un groove funk")) == ["soul"]
    assert genres(item("Les Variations Goldberg", lead_text="Bach au piano")) == ["classique"]
    assert genres(item("Pop-up store de vinyles")) == []
    assert genres(item("Mica Millar")) == []


def test_concerts_keep_to_the_couple_music():
    concert = {"concert"}
    assert off_key(["electro"], concert, {"jazz", "rock"})
    assert not off_key(["electro", "jazz"], concert, {"jazz"})
    assert not off_key(["electro"], concert, set())  # nothing said: all music is fine
    assert not off_key([], concert, {"jazz"})  # unknown music: still proposed
    assert not off_key(["classique"], concert, {"metal"})  # a Candlelight stays possible for an occasion
    assert off_key(["electro"], {"nuit"}, {"jazz"})  # a club night too
    assert not off_key(["jazz"], {"bar"}, {"rock"})  # a bar is not a concert
