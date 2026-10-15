"""The couple's content fed beside the collection (surprise.inspirations): the ideas a page of couple questions gives,
their genre and palier, our version drawn by the rules or by Claude (a stand-in here), never the source's words; the
pages read again only after a month; the moderation's page and API; and the publication at the end of the journey in
the local Supabase (npm run db:start), never the project's, each row removed afterwards."""

import json
from types import SimpleNamespace

import httpx
import psycopg
import pytest

from serving import serving
from surprise import inspirations
from surprise.admin import make_handler
from surprise.inspirations import by_claude, by_rules, check, classify, extract, publier, publier_serie, too_close, tutoyer
from surprise.local_store import LocalStore, PostgresStore
from test_admin import request
from test_push import local_db  # noqa: F401 (the fixture)

PAGE = """<html><body><nav><a>Quel est votre signe ?</a></nav><header><p>Inscrivez-vous à la newsletter ?</p></header>
<article>
<h1>Les questions pour mieux se connaître</h1>
<h2>1. Quel est son plat préféré ?</h2>
<p>Un classique. Préférez-vous la mer ou la montagne ? Qu'est-ce que vous admirez le plus chez votre partenaire ?</p>
<h3>Côté souvenirs : « Vous vous souvenez de votre premier rendez-vous ? »</h3>
<ul><li>N°4 — Avez-vous déjà eu peur de perdre l'autre ?</li><li>Organisez un pique-nique surprise au bord du canal.</li>
<li>Faites notre test</li><li>Quel est son plat préféré ?</li><li>Trop court ?</li></ul>
""" + "<p>Un paragraphe sans question, pour que l'article soit bien l'article.</p>" * 40 + "</article></body></html>"


def test_a_pages_ideas_its_questions_and_what_it_gives_to_do_without_its_menus_titles_or_twice_the_same():
    assert extract(PAGE) == [
        "Quel est son plat préféré ?",
        "Préférez-vous la mer ou la montagne ?",
        "Qu'est-ce que vous admirez le plus chez votre partenaire ?",
        "Vous vous souvenez de votre premier rendez-vous ?",
        "Avez-vous déjà eu peur de perdre l'autre ?",
        "Organisez un pique-nique surprise au bord du canal.",
    ]


def test_each_idea_its_genre_and_palier():
    assert classify("Quel est son plat préféré ?") == ("quiz", 1)
    assert classify("Quelle est la couleur préférée de votre partenaire ?") == ("quiz", 1)
    assert classify("Préférez-vous la mer ou la montagne ?") == ("question", 1)
    assert classify("Quel est ton plus beau souvenir d'enfance ?") == ("question", 2)
    assert classify("Comment réagis-tu après une dispute ?") == ("question", 3)
    assert classify("Avez-vous déjà eu peur de perdre l'autre ?") == ("question", 4)
    assert classify("Organisez un pique-nique surprise au bord du canal.") == ("defi", 1)


def test_the_rules_speak_the_apps_way_the_partner_spoken_of_become_me_a_quiz_question_in_the_first_person():
    assert tutoyer("Qu'est-ce que vous admirez le plus chez votre partenaire ?") == "Qu'est-ce que tu admires le plus chez moi ?"
    assert tutoyer("Préférez-vous la mer ou la montagne ?") == "Préfères-tu la mer ou la montagne ?"
    assert tutoyer("Vous vous souvenez de votre premier rendez-vous ?") == "Tu te souviens de ton premier rendez-vous ?"
    assert tutoyer("Vous sentez-vous écouté ?") == "Te sens-tu écouté ?"
    assert tutoyer("Que feriez-vous si vous gagniez au loto ?") == "Que ferais-tu si tu gagnais au loto ?"
    assert tutoyer("Vous êtes plutôt thé ou café ?") == "Tu es plutôt thé ou café ?"
    assert tutoyer("Qu'est-ce qui vous rend heureux ?") == "Qu'est-ce qui te rend heureux ?"
    quiz = lambda words: by_rules({"texte": words, "genre": "quiz", "palier": 1})  # noqa: E731
    assert quiz("Quel est son plat préféré ?") == {"question": "Mon plat préféré", "choix": ["", "", "", ""]}
    assert quiz("Quelle est la couleur préférée de votre partenaire ?")["question"] == "Ma couleur préférée"
    assert quiz("Quel était le prénom de son premier flirt ?")["question"] == "Le prénom de mon premier flirt"
    assert by_rules({"texte": "Quel est votre plus beau souvenir d'enfance ?", "genre": "question", "palier": 2}) == {
        "texte": "Quel est ton plus beau souvenir d'enfance ?", "theme": "enfance", "palier": 2}


def test_a_version_too_close_to_the_sources_words_or_incomplete_is_not_ours():
    source = "Quel est votre plus beau souvenir d'enfance ?"
    assert too_close(source, "Quel est ton plus beau souvenir d'enfance ?")  # the register changed, not the words
    assert not too_close(source, "Quelle odeur te ramène tout droit à tes huit ans ?")
    check("question", {"texte": "Quelle odeur te ramène tout droit à tes huit ans ?", "theme": "enfance", "palier": 2})
    with pytest.raises(ValueError, match="Quatre réponses"):
        check("quiz", {"question": "Mon plat préféré", "choix": ["Pâtes", "Pâtes", "Riz", ""]})
    with pytest.raises(ValueError, match="finie par"):
        check("question", {"texte": "Raconte ton plus beau souvenir.", "theme": "souvenirs", "palier": 2})


def pages(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_the_pages_read_at_most_limit_ideas_each_an_idea_met_again_kept_once_a_page_read_again_after_a_month(tmp_path, monkeypatch):
    monkeypatch.setattr(inspirations, "SOURCES", {
        "un": ("Un", ["https://un.example/questions"]), "deux": ("Deux", ["https://deux.example/quiz", "https://deux.example/absente"]),
    })
    read = []

    def handler(req):
        read.append(str(req.url))
        return httpx.Response(404) if req.url.path == "/absente" else httpx.Response(200, text=PAGE)

    with LocalStore(tmp_path / "s.db") as store, pages(handler) as http:
        assert inspirations.aspirer(store, http, limit=4, delay=0) == {"un": 4, "deux": 0}  # the same ideas: kept once
        assert len(read) == 3 and len(store.inspirations()) == 4
        assert {i["genre"] for i in store.inspirations()} == {"quiz", "question"}
        # Read again tomorrow: nothing asked, but the page that failed.
        read.clear()
        inspirations.aspirer(store, http, limit=50, delay=0)
        assert read == ["https://deux.example/absente"]
        inspirations.aspirer(store, http, limit=50, delay=0, refresh=True, sources=["un"])
        assert read[1:] == ["https://un.example/questions"] and len(store.inspirations()) == 6


def fake_claude(answer: str):
    """A client of Claude's API saying `answer`, and the prompts it was given."""
    asked = []

    def create(**kwargs):
        asked.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=answer)], stop_reason="end_turn")

    return SimpleNamespace(messages=SimpleNamespace(create=create)), asked


def test_claude_writes_a_version_of_its_own_one_too_close_or_malformed_left_to_the_rules():
    idea = {"texte": "Quel est son plat préféré ?", "genre": "quiz", "palier": 1}
    client, asked = fake_claude('Voici : {"question": "Le plat que je commanderais les yeux fermés", "choix": ["Une pizza", "Des sushis", "Un couscous", "Une raclette"]}')
    assert by_claude(client, "claude-test", idea) == {"question": "Le plat que je commanderais les yeux fermés", "choix": ["Une pizza", "Des sushis", "Un couscous", "Une raclette"]}
    assert "Quel est son plat préféré ?" in asked[0]["messages"][0]["content"] and "reprends pas" in asked[0]["system"]
    copied, _ = fake_claude('{"question": "Quel est son plat préféré", "choix": ["a", "b", "c", "d"]}')
    assert by_claude(copied, "claude-test", idea) is None
    broken, _ = fake_claude("Je n'ai pas compris.")
    assert by_claude(broken, "claude-test", idea) is None


def stored(tmp_path) -> LocalStore:
    store = LocalStore(tmp_path / "s.db")
    store.save_inspirations("un", "https://un.example/questions", [
        {"id": inspirations.fingerprint(w), "texte": w, "genre": g, "palier": p}
        for w in ["Quel est son plat préféré ?", "Quel est votre plus beau souvenir d'enfance ?", "Organisez un pique-nique surprise."]
        for g, p in [classify(w)]
    ])
    return store


def test_each_new_idea_gets_a_version_the_writers_or_the_rules(tmp_path):
    with stored(tmp_path) as store:
        assert inspirations.reimaginer(store, lambda idea: {"titre": "Pique-nique", "texte": "x"} if idea["genre"] == "defi" else None, "claude-test") == 3
        ideas = {i["genre"]: i for i in store.inspirations()}
        assert {i["statut"] for i in ideas.values()} == {"proposee"}
        assert ideas["defi"]["proposee_par"] == "claude-test" and ideas["quiz"]["proposee_par"] == "regles"
        assert ideas["quiz"]["proposition"] == {"question": "Mon plat préféré", "choix": ["", "", "", ""]}
        assert inspirations.reimaginer(store) == 0  # none new


def test_the_moderation_page_lists_them_sets_one_aside_and_publishes_only_our_words_in_supabase(tmp_path):
    with stored(tmp_path) as store:
        inspirations.reimaginer(store)
        ideas = {i["genre"]: i for i in store.inspirations()}
    with serving(make_handler(tmp_path / "s.db")) as url:
        status, body = request(f"{url}/admin/contenus")
        assert status == 200 and "Contenus du couple" in body.decode()
        status, body = request(f"{url}/api/inspirations")
        listed = json.loads(body)
        assert status == 200 and len(listed["inspirations"]) == 3 and listed["sources"]["ozer"] == "Ozer" and "enfance" in listed["themes"]

        souvenir = f"{url}/api/inspirations/{ideas['question']['id']}"
        status, body = request(souvenir, {"action": "publier", "genre": "question", "proposition": ideas["question"]["proposition"]})
        assert status == 400 and "Trop proche" in json.loads(body)["error"]
        ours = {"texte": "Quelle odeur te ramène tout droit à tes huit ans ?", "theme": "enfance", "palier": 2}
        status, body = request(souvenir, {"action": "publier", "genre": "question", "proposition": ours})
        assert status == 409 and "Supabase" in json.loads(body)["error"]  # the app's tables are Supabase's

        # A quiz question kept for its series, with its four answers.
        quiz = {"question": "Le plat que je commanderais les yeux fermés", "choix": ["Une pizza", "Des sushis", "Un couscous", "Une raclette"]}
        status, body = request(f"{url}/api/inspirations/{ideas['quiz']['id']}", {"action": "publier", "genre": "quiz", "proposition": quiz})
        assert (status, json.loads(body)["statut"]) == (200, "gardee")
        status, body = request(f"{url}/api/quiz-series", {"titre": "À table", "accroche": "Ce que l'on mange vraiment", "ids": [ideas["quiz"]["id"]]})
        assert status == 400 and "huit questions" in json.loads(body)["error"]

        assert request(f"{url}/api/inspirations/{ideas['defi']['id']}", {"action": "ecarter"})[0] == 200
        assert request(f"{url}/api/inspirations/inconnue", {"action": "ecarter"})[0] == 404
        assert request(f"{url}/api/inspirations/{ideas['defi']['id']}", {"action": "ecarter"}, content_type="text/plain")[0] == 415
    with LocalStore(tmp_path / "s.db") as store:
        assert {i["genre"]: i["statut"] for i in store.inspirations()} == {"question": "proposee", "quiz": "gardee", "defi": "ecartee"}


@pytest.fixture
def supabase(local_db):
    """The local Supabase's store, the inspirations and the content rows a test adds removed afterwards."""
    with psycopg.connect(local_db, autocommit=True) as conn:
        before = {t: conn.execute(f"select coalesce(max(id), 0) from public.{t}").fetchone()[0]
                  for t in ("questions_du_jour", "defis", "cartes_du_soir", "quiz_questions", "quiz_series")}
    store = PostgresStore(local_db)
    try:
        yield store
    finally:
        store.close() if hasattr(store, "close") else store._db.close()
        with psycopg.connect(local_db, autocommit=True) as conn:
            for table in ("quiz_questions", "quiz_series", "questions_du_jour", "defis", "cartes_du_soir"):
                conn.execute(f"delete from public.{table} where id > %s", (before[table],))
            conn.execute("delete from pipeline.inspirations where source_id = 'test'")
            conn.execute("delete from pipeline.inspiration_pages where source_id = 'test'")


def test_published_at_the_end_of_the_journey_a_question_a_defi_a_card_and_eight_quiz_questions_as_a_series(supabase):
    store = supabase
    words = [f"Quelle est la chose numéro {n} que tu préfères chez moi ?" for n in range(8)] + [
        "Quel est votre plus beau souvenir d'enfance ?", "Organisez un pique-nique surprise.", "Racontez votre premier baiser."]
    store.save_inspirations("test", "https://test.example/", [
        {"id": inspirations.fingerprint(w), "texte": w, "genre": "quiz" if n < 8 else classify(w)[0], "palier": 1} for n, w in enumerate(words)])
    idea = {i["texte"]: i["id"] for i in store.inspirations() if i["source_id"] == "test"}
    last = store._run("select max(id) from public.questions_du_jour").fetchone()[0]

    where = publier(store, idea[words[8]], "question", {"texte": "Quelle odeur te ramène tout droit à tes huit ans ?", "theme": "enfance", "palier": 2})
    assert where == f"questions_du_jour:{last + 1}"
    assert store._run("select profondeur, theme, texte from public.questions_du_jour where id = %s", (last + 1,)).fetchone() == (
        2, "enfance", "Quelle odeur te ramène tout droit à tes huit ans ?")
    with pytest.raises(ValueError, match="Déjà publiée"):
        publier(store, idea[words[8]], "question", {"texte": "Quel goût te ramène à tes huit ans, sans hésiter ?", "theme": "enfance", "palier": 2})
    assert publier(store, idea[words[9]], "defi", {"titre": "Le panier mystère", "texte": "Chacun glisse trois choses dans le panier sans le dire à l'autre.", "genre": "sortie"}).startswith("defis:")
    card = publier(store, idea[words[10]], "carte", {"texte": "Quel détail de ce soir voudrais-tu garder dans dix ans ?", "genre": "conversation", "profondeur": 2})
    assert store._run("select formule, profondeur from public.cartes_du_soir where id = %s", (int(card.split(":")[1]),)).fetchone() == ("duo", 2)

    for n in range(8):
        assert publier(store, idea[words[n]], "quiz", {"question": f"Mon petit plaisir n° {n}", "choix": ["Un", "Deux", "Trois", "Quatre"]}) == "gardee"
    series = store._run("select max(id) from public.quiz_series").fetchone()[0]
    order = [idea[w] for w in reversed(words[:8])]
    assert publier_serie(store, "Petits plaisirs", "Ce qui nous fait du bien, en vrai", order) == f"quiz_series:{series + 1}"
    rows = store._run("select rang, question from public.quiz_questions where serie = %s order by rang", (series + 1,)).fetchall()
    assert rows[0] == (1, "Mon petit plaisir n° 7") and len(rows) == 8
    assert {i["statut"] for i in store.inspirations() if i["source_id"] == "test"} == {"publiee"}
