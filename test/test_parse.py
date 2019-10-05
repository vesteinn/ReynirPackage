"""

    test_parse.py

    Tests for Reynir module

    Copyright(C) 2019 by Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""

import pytest
from collections import defaultdict


@pytest.fixture(scope="module")
def r():
    """ Provide a module-scoped Reynir instance as a test fixture """
    from reynir import Reynir
    r = Reynir()
    yield r
    # Do teardown here
    r.__class__.cleanup()


def test_parse(r, verbose=False):

    sentences = [
        # 0
        "Hér er verið að gera tilraunir með þáttun.",
        # 1
        "Margar málsgreinar koma hér fyrir.",
        # 2
        "Þetta takast ekki að þáttar.",  # Error sentence
        # 3
        "Fjórða málsgreinin er síðust.",
        # 4
        "Hitastig vatnsins var 30,5 gráður og ég var ánægð með það.",
        # 5
        "Hún skuldaði mér 1.000 dollara.",
        # 6
        "Ég hitti hana þann 17. júní árið 1944 á Þingvöllum.",
        # 7
        "Hann eignaðist hús við ströndina og henni tókst að mála það.",
        # 8
        "Barnið fór í augnrannsóknina eftir húsnæðiskaupin.",
        # 9
        "Barnið fór í loðfílarannsókn.",  # Test composite words
        # 10
        "Eðlisfræðingurinn Stephen Hawking lést í dag, á pí-deginum.",
        # 11
        "Löngu áður en Jón borðaði ísinn sem hafði bráðnað hratt "
        "í hádeginu fór ég á veitingastaðinn á horninu og keypti mér rauðvín "
        "með hamborgaranum sem ég borðaði í gær með mikilli ánægju.",
        # 12
        "Ég horfði á Pál borða kökuna.",
        # 13
        "Fyrir Pál eru þetta góð tíðindi.",
        # 14
        "Ég hef unnið og þrælað alla mína tíð.",
        # 15
        "Jón borðaði ísinn um svipað leyti og Gunna skrifaði bréfið.",
        # 16
        "Það að þau viðurkenna ekki að þjóðin er ósátt við gjörðir þeirra er alvarlegt.",
        # 17
        "Hann hefur nú viðurkennt að hafa ákveðið sjálfur að birta "
        "hvorki almenningi né Alþingi skýrsluna.",
        # 18
        "Ríkissjóður stendur í blóma ef 27 milljarða "
        "arðgreiðsla Íslandsbanka er talin með.",
        # 19
        "Auk alls þessa þá getum við líka einfaldlega vandað okkur meira.",
        # 20
        "Það er óskandi að gripið verði til margfalt öflugri aðgerða "
        "en verið hefur á liðnum árum og áratugum.",
        # 21
        "Eftir vanfjármögnun úrbóta sl. kjörtímabil, í margyfirlýstu góðæri "
        "þar sem fjárlagafrumvarp 2017 var samt undir núlli tekjumegin, "
        "er deginum ljósara að mikla viðbótarfjármögnun þarf svo koma megi "
        "mörgu í betra horf á næstu 1-2 árum.",
        # 22
        "Lögreglan fer ekki nánar ofan í það hvaða skemmdir það voru.",
        # 23
        "Ég leyfði þeim að taka allt sitt inn í veturinn.",
        # 24
        "Það sem þeir vilja berjast fyrir er ekki loforð, heldur áherslur.",
        # 25
        "Mér finnst í sjálfu sér slæmt að það skyldi hafa verið þannig.",
        # 26
        "Jón hefur aðgang að gögnum þeirra starfssviða sem eiga að vera aðskilin.",
        # 27
        "Fréttaveiturnar Reuters og Bloomberg fengu að vera viðstaddar fundinn.",
        # 28
        "Samtök ferðaþjónustunnar eru fylgjandi virðisaukandi þjónustu "
        "þar með talið bílastæðagjöldum.",
        # 29
        "Starfsmenn hans voru ekki á eitt sáttir.",
        # 30
        "Það var ekki bara á þann hátt að glútenið vantaði.",
        # 31
        "Slökkviliðið var á sama tíma í óðaönn við að slökkva eld "
        "sem kom upp í húsnæði við Bauganes í Skerjafirði.",
        # 32
        "Gömul mynd sem fannst nýlega í Þjóðskjalasafni Bandaríkjanna "
        "er sögð gefa í skyn að frægasti kvenkyns flugmaður sögunnar, "
        "Amelia Earhart, hafi ekki dáið í flugslysi í Kyrrahafinu.",
        # 33
        "Sams konar mál var svo höfðað í tvígang fyrir dómi, annars vegar "
        "með stefnu í apríl fyrir sex árum sem var felld niður og hins vegar "
        "í júlí ári seinna.",
        # 34
        "Lögreglan á Suðurlandi rannsakar nú hvort að maður um tvítugt "
        "hafi brotið kynferðislega gegn unglingsstúlku í liðinni viku.",
        # 35
        "Þetta hefur alltaf verið svona, að mér skilst.",
        # 36
        "Árásin átti sér stað um klukkan fimm aðfaranótt síðastliðins sunnudags "
        "þegar karlmaður var stunginn ítrekað í kviðinn með hnífi.",
    ]
    job = r.submit(" ".join(sentences))

    results = list(job.sentences())

    for i, sent in enumerate(results):
        if verbose:
            print("Sentence {0}: {1}".format(i, sent.tidy_text))
        assert sent.tidy_text == sentences[i], "'{0}' != '{1}'".format(
            sent.tidy_text, sentences[i]
        )
        if sent.parse():
            # Sentence parsed successfully
            assert i != 2
            if verbose:
                print("Successfully parsed")
        else:
            # An error occurred in the parse
            # The error token index is at sent.err_index
            assert i == 2
            assert sent.err_index == 5
            if verbose:
                print("Error in parse at token {0}".format(sent.err_index))

    assert job.num_sentences == len(sentences)
    assert job.num_parsed == len(sentences) - 1

    if verbose:
        print("Number of sentences : {0}".format(job.num_sentences))
        print("Thereof parsed      : {0}".format(job.num_parsed))
        print("Ambiguity           : {0:.2f}".format(job.ambiguity))
        print("Parsing time        : {0:.2f}".format(job.parse_time))

    # Test that the parser finds the correct nouns
    assert results[0].tree.nouns == ["tilraun", "þáttun"]
    assert results[1].tree.nouns == ["málsgrein"]
    assert results[2].tree is None  # Error sentence
    assert results[3].tree.nouns == ["málsgrein"]
    assert results[4].tree.nouns == [
        "hitastig",
        "vatn",
        "gráða",
    ]
    assert results[5].tree.nouns == [
        "1.000 dollara"
    ]
    # 'árið 1944' er tímaliður en ekki nafnliður
    assert results[6].tree.nouns == [
        "Þingvellir"
    ]
    assert results[7].tree.nouns == ["hús", "strönd"]
    assert results[8].tree.nouns == ["barn", "augnrannsókn", "húsnæðiskaup"]
    assert results[9].tree.nouns == ["barn", "loðfíla-rannsókn"]
    assert results[10].tree.nouns == ["eðlisfræðingur", "dagur", "pí", "dagur"]
    assert results[11].tree.nouns == [
        "Jón",
        "ís",
        "hádegi",
        "veitingastaður",
        "horn",
        "rauðvín",
        "hamborgari",
        "ánægja",
    ]
    assert results[12].tree.nouns == ["Páll", "kaka"]

    assert results[22].tree.nouns == ["lögregla", "skemmd"]
    assert results[23].tree.nouns == ["vetur"]
    assert results[24].tree.nouns == ["loforð", "áhersla"]
    assert results[32].tree.nouns == ["mynd", "þjóðskjalasafn", "Bandaríkin",
        "skyn", "flugmaður", "saga", "flugslys", "Kyrrahaf"]

    # Test that the parser finds the correct verbs
    assert results[0].tree.verbs == ["vera", "vera", "gera"]
    assert results[1].tree.verbs == ["koma"]
    assert results[2].tree is None  # Error sentence
    assert results[3].tree.verbs == ["vera"]
    assert results[4].tree.verbs == ["vera", "vera"]
    assert results[5].tree.verbs == ["skulda"]
    assert results[6].tree.verbs == ["hitta"]
    assert results[7].tree.verbs == ["eigna", "taka", "mála"]
    assert results[8].tree.verbs == ["fara"]
    assert results[9].tree.verbs == ["fara"]
    assert results[10].tree.verbs == ["láta"]
    assert results[11].tree.verbs == [
        "borða",
        "hafa",
        "bráðna",
        "fara",
        "kaupa",
        "borða",
    ]
    assert results[12].tree.verbs == ["horfa", "borða"]
    assert results[32].tree.verbs == [
        "finna", "segja", "gefa", "hafa", "deyja"
    ]

    # Test that the parser finds the correct word lemmas
    assert results[0].tree.lemmas == [
        "hér",
        "vera",
        "vera",
        "að",
        "gera",
        "tilraun",
        "með",
        "þáttun",
        ".",
    ]
    assert results[1].tree.lemmas == [
        "margur",
        "málsgrein",
        "koma",
        "hér",
        "fyrir",
        ".",
    ]
    assert results[2].tree is None  # Error sentence
    assert results[3].tree.lemmas == ["fjórði", "málsgrein", "vera", "síðari", "."]
    assert results[4].tree.lemmas == [
        "hitastig",
        "vatn",
        "vera",
        "30,5",
        "gráða",
        "og",
        "ég",
        "vera",
        "ánægður",
        "með",
        "það",
        ".",
    ]
    assert results[5].tree.lemmas == ["hún", "skulda", "ég", "1.000 dollara", "."]
    assert results[6].tree.lemmas == [
        "ég",
        "hitta",
        "hún",
        "sá",
        "17. júní árið 1944",
        "á",
        "Þingvellir",
        ".",
    ]
    assert results[7].tree.lemmas == [
        "hann",
        "eigna",
        "hús",
        "við",
        "strönd",
        "og",
        "hún",
        "taka",
        "að",
        "mála",
        "það",
        ".",
    ]
    assert results[8].tree.lemmas == [
        "barn",
        "fara",
        "í",
        "augnrannsókn",
        "eftir",
        "húsnæðiskaup",
        ".",
    ]
    assert results[9].tree.lemmas == ["barn", "fara", "í", "loðfíla-rannsókn", "."]
    assert results[10].tree.lemmas == [
        "eðlisfræðingur",
        "Stephen",
        "Hawking",
        "láta",
        "í",
        "dagur",
        ",",
        "á",
        "pí",
        "—",
        "dagur",
        ".",
    ]
    assert results[11].tree.lemmas == [
        "löngu",
        "áður",
        "en",
        "Jón",
        "borða",
        "ís",
        "sem",
        "hafa",
        "bráðna",
        "hratt",
        "í",
        "hádegi",
        "fara",
        "ég",
        "á",
        "veitingastaður",
        "á",
        "horn",
        "og",
        "kaupa",
        "ég",
        "rauðvín",
        "með",
        "hamborgari",
        "sem",
        "ég",
        "borða",
        "í gær",
        "með",
        "mikill",
        "ánægja",
        ".",
    ]
    assert results[12].tree.lemmas == ["ég", "horfa", "á", "Páll", "borða", "kaka", "."]
    assert results[36].tree.lemmas == [
        "árás",
        "eiga",
        "sig",
        "staður",
        "um",
        "klukkan fimm",
        "aðfaranótt",
        "síðastliðinn",
        "sunnudagur",
        "þegar",
        "karlmaður",
        "vera",
        "stinga",
        "ítrekað",
        "í",
        "kviður",
        "með",
        "hnífur",
        "."
    ]

    def num_pp(s):
        """ Count the prepositional phrases in the parse tree for sentence s """
        return len([t for t in s.tree.descendants if t.match("PP")])

    # Test that the correct number of prepositional phrases (PPs) is generated
    assert num_pp(results[8]) == 2
    assert num_pp(results[9]) == 1
    assert num_pp(results[10]) == 1
    assert num_pp(results[11]) == 4
    assert num_pp(results[12]) == 0


def test_consistency(r, verbose=False):
    """ Check that multiple parses of the same sentences yield exactly
        the same preposition counts, and also identical scores. This is
        inter alia to guard agains nondeterminism that may arise from
        Python's random hash seeds. """

    sent15 = [
        "Barnið fór í augnrannsóknina eftir húsnæðiskaupin.",
        "Ég sendi póstinn frá Ísafirði með kettinum",
    ]
    sent45 = [
        "Barnið fór í augnrannsóknina fyrir húsnæðiskaupin.",
        "Ég sendi póstinn með kettinum til Ísafjarðar",
    ]
    for tc15, tc45 in zip(sent15, sent45):

        cnt = defaultdict(int)
        scores = defaultdict(int)
        ptime = 0.0

        ITERATIONS = 60
        if verbose:
            print(
                "Consistency test, {0} iterations:\n   {1}\n   {2}".format(
                    ITERATIONS, tc15, tc45
                )
            )

        for i in range(ITERATIONS):
            # The following two sentences have different scores
            if i % 5 == 4:
                # One fifth of the test cases
                j = r.submit(tc15)
            else:
                # Four fifths of the test cases
                j = r.submit(tc45)
            s = next(iter(j))
            s.parse()
            ptime += j.parse_time
            pp = [t.text for t in s.tree.descendants if t.match("PP")]
            cnt[len(pp)] += 1
            scores[s.score] += 1

        if verbose:
            print(
                "Parse time for {0} iterations was {1:.2f} seconds".format(
                    ITERATIONS, ptime
                )
            )

        # There should be 2 prepositions in all parse trees
        assert len(cnt) == 1
        assert 2 in cnt
        assert cnt[2] == ITERATIONS

        # The sum of all counts should be the number of iterations
        assert sum(scores.values()) == ITERATIONS
        if verbose:
            print(
                "There are {0} different scores in consistency check".format(
                    len(scores)
                )
            )
        # There should only be two different scores
        assert len(scores) == 2
        sc_set = set(scores.values())
        # The count for the scores should be 1/5 and 4/5 of the total, respectively
        assert ITERATIONS * 1 // 5 in sc_set
        assert ITERATIONS * 4 // 5 in sc_set


def test_long_parse(r, verbose=False):
    if verbose:
        print("Long parse test")
    txt = """
        [[ Reynt er að efla áhuga ungs fólks á borgarstjórnarmálum með framboðsfundum og skuggakosningum en þótt
        kjörstaðirnir í þeim séu færðir inn í framhaldsskólana er þátttakan lítil. Dagur B. Eggertsson nýtur mun
        meira fylgis í embætti borgarstjóra en fylgi Samfylkingarinnar gefur til kynna samkvæmt könnun Fréttablaðsins. ]]
        [[ Eins og fram kom í fréttum okkar í gær stefnir í met í fjölda framboða fyrir komandi borgarstjórnarkosningar
        í vor og gætu þau orðið að minnsta kosti fjórtán. Þá þarf minna fylgi nú en áður til að ná inn borgarfulltrúa,
        því borgarfulltrúum verður fjölgað úr fimmtán í tuttugu og þrjá. ]]
        [[ Kosningabaráttan fyrir borgarstjórnarkosningarnar í vor er hafin í framhaldsskólum borgarinnar. Samhliða
        framboðskynningum fara fram skuggakosningar til borgarstjórnar í skólunum. ]]
        [[ „Þetta er eiginlega æfing í því að taka þátt í lýðræðislegum kosningum. Við reynum að herma eftir því
        hvernig raunverulegar kosningar fara fram,“ segir Róbert Ferdinandsson kennari á félagsfræðibraut
        Fjölbrautaskólans við Ármúla. ]]
    """
    job = r.submit(txt)
    pg_count = 0
    sent_count = 0
    persons = []
    for pg in job.paragraphs():
        pg_count += 1
        if verbose:
            print("Paragraph {0}".format(pg_count))
        for sent in pg:
            sent_count += 1
            assert sent.parse(), "Could not parse sentence {0}".format(sent_count)
            persons.extend(sent.tree.persons)
    assert pg_count == 4
    assert sent_count == 8
    assert persons == ["Dagur B. Eggertsson", "Róbert Ferdinandsson"]

    if verbose:
        print("Number of sentences : {0}".format(job.num_sentences))
        print("Thereof parsed      : {0}".format(job.num_parsed))
        print("Ambiguity           : {0:.2f}".format(job.ambiguity))
        print("Parsing time        : {0:.2f}".format(job.parse_time))


def test_properties(r):
    s = r.parse("Þetta er prófun.")["sentences"][0]
    _ = s.score
    _ = s.tokens
    _ = s.tree.view  # Should not raise exception
    try:
        _ = s.tree.tree
        assert False, "Should have raised exception"
    except AttributeError:
        pass


def check_terminal(t, text, lemma, category, variants):
    assert t.text == text
    assert t.lemma == lemma
    assert t.category == category
    assert set(t.variants) == set(variants)


def check_terminals(t):
    assert len(t) == 7
    check_terminal(
        t[0], text="Jón", lemma="Jón", category="person", variants=["nf", "kk"]
    )
    check_terminal(
        t[1],
        text="greiddi",
        lemma="greiða",
        category="so",
        variants=["2", "þgf", "þf", "et", "p3", "fh", "gm", "þt"],
    )
    check_terminal(
        t[2],
        text="bænum",
        lemma="bær",
        category="no",
        variants=["et", "þgf", "kk", "gr"],
    )
    check_terminal(
        t[3],
        text="10 milljónir króna",
        lemma="10 milljónir króna",
        category="no",
        variants=["ft", "þf", "kvk"],
    )
    check_terminal(t[4], text="í", lemma="í", category="fs", variants=["þf"])
    check_terminal(
        t[5],
        text="skaðabætur",
        lemma="skaðabót",
        category="no",
        variants=["ft", "þf", "kvk"],
    )
    check_terminal(t[6], text=".", lemma=".", category="", variants=[])


def test_terminals(r):
    s = r.parse("Jón greiddi bænum 10 milljónir króna í skaðabætur.")["sentences"][0]
    check_terminals(s.terminals)


def test_amounts(r):
    s = r.parse_single("Tjónið nam 10 milljörðum króna.")
    t = s.terminals
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="10 milljörðum króna",
        lemma="10 milljörðum króna",
        category="no",
        variants=["ft", "þgf", "kk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    assert s.tokens[2].val[0] == 10e9
    assert s.tokens[2].val[1] == "ISK"

    s = r.parse_single("Tjónið þann 22. maí nam einum milljarði króna.")
    t = s.terminals
    assert len(t) == 6
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1], text="þann", lemma="sá", category="fn", variants=["et", "kk", "þf"]
    )
    check_terminal(
        t[2], text="22. maí", lemma="22. maí", category="dagsafs", variants=[]
    )
    check_terminal(
        t[3],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[4],
        text="einum milljarði króna",
        lemma="einum milljarði króna",
        category="no",
        variants=["ft", "þgf", "kk"],
    )
    check_terminal(t[5], text=".", lemma=".", category="", variants=[])
    assert s.tokens[2].val == (0, 5, 22)
    assert s.tokens[4].val[0] == 1e9
    assert s.tokens[4].val[1] == "ISK"

    s = r.parse_single("Tjónið þann 19. október 1983 nam 4,8 milljörðum dala.")
    t = s.terminals
    assert len(t) == 6
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1], text="þann", lemma="sá", category="fn", variants=["et", "kk", "þf"]
    )
    check_terminal(
        t[2],
        text="19. október 1983",
        lemma="19. október 1983",
        category="dagsföst",
        variants=[],
    )
    check_terminal(
        t[3],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[4],
        text="4,8 milljörðum dala",
        lemma="4,8 milljörðum dala",
        category="no",
        variants=["ft", "þgf", "kk"],
    )
    check_terminal(t[5], text=".", lemma=".", category="", variants=[])
    assert s.tokens[2].val == (1983, 10, 19)
    assert s.tokens[4].val[0] == 4.8e9
    assert s.tokens[4].val[1] == "USD"

    s = r.parse_single("Tjónið nam sautján milljörðum breskra punda.")
    t = s.terminals
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="sautján milljörðum breskra punda",
        lemma="sautján milljörðum breskra punda",
        category="no",
        variants=["ft", "þgf", "kk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    assert s.tokens[2].val[0] == 17e9
    assert s.tokens[2].val[1] == "GBP"

    s = r.parse_single("Tjónið nam 17 breskum pundum.")
    t = s.terminals
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="17 breskum pundum",
        lemma="17 breskum pundum",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    assert s.tokens[2].val[0] == 17
    assert s.tokens[2].val[1] == "GBP"

    s = r.parse_single("Tjónið nam 17 pólskum zloty.")
    t = s.terminals
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="17 pólskum zloty",
        lemma="17 pólskum zloty",
        category="no",
        variants=["ft", "þgf", "hk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    assert s.tokens[2].val[0] == 17
    assert s.tokens[2].val[1] == "PLN"

    s = r.parse_single("Tjónið nam 101 indverskri rúpíu.")
    t = s.terminals
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="101 indverskri rúpíu",
        lemma="101 indverskri rúpíu",
        category="no",
        variants=["et", "þgf", "kvk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    assert s.tokens[2].val[0] == 101
    assert s.tokens[2].val[1] == "INR"

    s = r.parse_single("Tjónið nam 17 milljónum indónesískra rúpía.")
    t = s.terminals
    assert len(t) == 4
    check_terminal(
        t[0],
        text="Tjónið",
        lemma="tjón",
        category="no",
        variants=["et", "nf", "hk", "gr"],
    )
    check_terminal(
        t[1],
        text="nam",
        lemma="nema",
        category="so",
        variants=["1", "þgf", "et", "p3", "gm", "þt", "fh"],
    )
    check_terminal(
        t[2],
        text="17 milljónum indónesískra rúpía",
        lemma="17 milljónum indónesískra rúpía",
        category="no",
        variants=["ft", "þgf", "kvk"],
    )
    check_terminal(t[3], text=".", lemma=".", category="", variants=[])
    assert s.tokens[2].val[0] == 17e6
    assert s.tokens[2].val[1] == "IDR"


def test_year_range(r):
    s = r.parse_single("Jón var Íslandsmeistari árin 1944-50.")
    t = s.terminals
    assert len(t) == 8
    check_terminal(
        t[0], text="Jón", lemma="Jón", category="person", variants=["nf", "kk"]
    ),
    check_terminal(
        t[1],
        text="var",
        lemma="vera",
        category="so",
        variants=["1", "nf", "et", "p3", "þt", "fh", "gm"],
    ),
    check_terminal(
        t[2],
        text="Íslandsmeistari",
        lemma="Íslandsmeistari",
        category="no",
        variants=["et", "nf", "kk"],
    ),
    check_terminal(
        t[3], text="árin", lemma="ár", category="no", variants=["hk", "gr", "ft", "þf"]
    ),
    check_terminal(t[4], text="1944", lemma="1944", category="ártal", variants=[]),
    check_terminal(t[5], text="–", lemma="–", category="", variants=[]),
    check_terminal(t[6], text="50", lemma="50", category="tala", variants=[]),
    check_terminal(t[7], text=".", lemma=".", category="", variants=[])


def test_single(r):
    s = r.parse_single("Jón greiddi bænum 10 milljónir króna í skaðabætur.")
    check_terminals(s.terminals)
    try:
        _ = r.parse_single("")
        assert False, "Should have raised StopIteration"
    except StopIteration:
        pass
    s = r.parse_single("kötturinn lömdu hesturinn")
    assert s.combinations == 0
    assert s.tree is None


def test_complex(r, verbose=False):
    if verbose:
        print("Complex, sentence 1", end="")
    d = r.parse(
        "ákæran var þingfest en fréttastofu er kunnugt um að maðurinn "
        "játaði þar sem þinghaldið er lokað"
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 2", end="")
    d = r.parse(
        "Viðar Garðarsson, sem setti upp vefsíður fyrir Sigmund Davíð "
        "Gunnlaugsson í kjölfar birtingu Panamaskjalanna, segist ekki vita "
        "hvers vegna ákveðið var að segja að vefjunum væri haldið úti af "
        "stuðningsmönnum Sigmundar."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 3", end="")
    d = r.parse(
        "Ákæran var þingfest í Héraðsdómi Reykjaness í dag "
        "en fréttastofu er ekki kunnugt um hvort maðurinn játaði eða neitaði "
        "sök þar sem þinghaldið í málinu er lokað."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 4", end="")
    d = r.parse(
        "Út úr stílfærðri túlkun listamannsins á gamla , litla og mjóa "
        "prófessornum kom búlduleitur beljaki sem þess vegna hefði getað verið "
        "trökkdræver að norðan."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 5", end="")
    d = r.parse(
        "Rétt hjá anddyrinu var ein af þessum höggnu andlitsmyndum "
        "af þjóðfrægum mönnum þar sem listamaðurinn hafði gefist upp við að ná "
        "svipnum og ákveðið að hafa þetta í staðinn stílfærða mynd sem túlkaði "
        "fremur innri mann fyrirmyndarinnar en þá ásjónu sem daglega blasti við "
        "samferðamönnum."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))
        print("Complex, sentence 6", end="")
    d = r.parse(
        "Sú fullyrðing byggist á því að ef hlutverk skólastarfs er eingöngu til þess "
        "að undirbúa nemendur fyrir skilvirka og afkastamikla þátttöku í atvinnu- og "
        "viðskiptalífi, skerðist það rými sem einstaklingar fá í gegnum menntun til "
        "þess að rækta með sér þá flóknu hæfni sem þarf til að lifa í lýðræðissamfélagi; "
        "að móta eigin skoðanir, þjálfa gagnrýna hugsun og læsi, læra að lifa í "
        "margbreytilegu samfélagi, mynda tengsl við aðra, mótast sem einstaklingur "
        "í hnattrænu samfélagi, og takast á við ólík viðhorf, skoðanir og gildi — svo "
        "fátt eitt sé nefnt."
    )
    assert d["num_parsed"] == 1
    if verbose:
        print(", time: {:.2f} seconds".format(d["parse_time"]))


def test_measurements(r):
    s = r.parse_single(
        "Ég vildi leggja rúm 220 tonn en hann vildi kaupa "
        "tæplega 3,8 km af efninu í yfir 32°F frosti."
    )
    assert (
        s.tree.flat == "S0 S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ "
        "VP VP-AUX so_et_p1 /VP-AUX VP VP so_1_þf_nh /VP NP-OBJ "
        "lo_þf_ft_hk tala_ft_þf_hk no_ft_þf_hk /NP-OBJ /VP /VP "
        "/IP /S-MAIN C st /C S-MAIN IP NP-SUBJ pfn_kk_et_nf "
        "/NP-SUBJ VP VP-AUX so_et_p3 /VP-AUX VP VP so_1_þf_nh "
        "/VP NP-OBJ NP-MEASURE ao tala mælieining "
        "/NP-MEASURE PP P fs_þgf /P NP no_et_þgf_hk PP P fs_þgf "
        "/P NP NP-POSS NP-MEASURE ao tala mælieining /NP-MEASURE "
        "/NP-POSS no_et_þgf_hk /NP /PP /NP /PP /NP-OBJ /VP /VP "
        "/IP /S-MAIN p /S0"
    )


def test_abbreviations(r):
    s = r.parse_single(
        "Ég borða köku BHM á laugard. í okt. nk. og mun þykja hún vond."
    )
    assert (
        s.tree.flat == "S0 S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ VP VP VP "
        "so_1_þf_et_p1 /VP NP-OBJ no_et_þf_kvk NP-POSS no_et_ef_hk "
        "/NP-POSS /NP-OBJ /VP ADVP-DATE-REL P fs_þf /P no_kk_þf_et "
        "/ADVP-DATE-REL ADVP-DATE-REL P fs_þgf /P dagsafs lo_þgf_et_kk "
        "/ADVP-DATE-REL C st /C VP VP-AUX so_et_p1 /VP-AUX VP VP "
        "so_1_nf_nh /VP NP-OBJ pfn_kvk_et_nf /NP-OBJ /VP /VP NP-PRD "
        "lo_sb_nf_et_kvk /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    # The following also tests augmented variants for personal pronouns,
    # i.e. pfn_et_nf_p1 for 'ég' and pfn_et_kvk_nf_p3 for 'hún'
    # (the person is added; it's not included in BÍN)
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_nf_p1 "
        "/NP-SUBJ VP VP VP so_1_þf_et_fh_gm_nt_p1 /VP NP-OBJ no_et_kvk_þf "
        "NP-POSS no_ef_et_hk /NP-POSS /NP-OBJ /VP ADVP-DATE-REL P fs_þf "
        "/P no_et_kk_þf /ADVP-DATE-REL ADVP-DATE-REL P fs_þgf /P dagsafs "
        "lo_et_kk_þgf /ADVP-DATE-REL C st /C VP VP-AUX so_et_fh_gm_nt_p1 "
        "/VP-AUX VP VP so_1_nf_gm_nh /VP NP-OBJ pfn_et_kvk_nf_p3 /NP-OBJ "
        "/VP /VP NP-PRD lo_et_kvk_nf_sb /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single(
        "T.d. var bréfið til KPMG dags. 10. júlí en hr. Friðgeir vildi senda það "
        "til ASÍ eða SÁÁ o.s.frv. áður en það birtist á mbl.is."
    )
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP ADVP ao /ADVP VP "
        "VP VP so_et_fh_gm_p3_þt /VP NP-SUBJ no_et_gr_hk_nf PP P fs_ef /P NP "
        "no_ef_et_hk /NP /PP /NP-SUBJ VP so_0_et_hk_lhþt /VP /VP "
        "ADVP-DATE-REL raðnr no_et_kk_þf /ADVP-DATE-REL "
        "/VP /IP /S-MAIN C st /C S-MAIN IP NP-SUBJ no_et_kk_nf "
        "person_kk_nf /NP-SUBJ VP VP VP-AUX so_et_fh_gm_p3_þt /VP-AUX "
        "VP VP so_1_þf_gm_nh /VP NP-OBJ pfn_et_hk_p3_þf /NP-OBJ /VP /VP PP "
        "P fs_ef /P NP no_ef_et_hk C st /C no_ef_et_hk ao /NP /PP /VP "
        "CP-ADV-TEMP C ao st /C IP NP-SUBJ pfn_et_hk_nf_p3 /NP-SUBJ "
        "VP VP so_0_et_fh_mm_nt_p3 /VP PP P fs_þgf /P NP lén_þgf "
        "/NP /PP /VP /IP /CP-ADV-TEMP /IP /S-MAIN p /S0"
    )


def test_attachment(r, verbose=False):
    """ Test attachment of prepositions to nouns and verbs """
    if verbose:
        print("Testing attachment of prepositions")
    for _ in range(20):
        # Test consistency for 20 iterations
        s = r.parse_single("Ég setti dæmi um þetta í bókina mína.")
        assert (
            s.tree.flat == "S0 S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ "  # Ég
            "VP VP VP so_1_þf_et_p1 /VP NP-OBJ no_et_þf_hk "  # setti dæmi
            "PP P fs_þf /P NP fn_et_þf_hk /NP /PP "  # um þetta
            "/NP-OBJ /VP PP P fs_þf /P NP no_et_þf_kvk fn_et_þf_kvk /NP /PP /VP "  # í bókina mína
            "/IP /S-MAIN p /S0"
        )  # .
        s = r.parse_single("Ég setti dæmi í bókina mína um þetta.")
        assert (
            s.tree.flat == "S0 S-MAIN IP NP-SUBJ pfn_et_nf /NP-SUBJ "  # Ég
            "VP VP VP so_1_þf_et_p1 /VP NP-OBJ no_et_þf_hk "  # setti dæmi
            "/NP-OBJ /VP PP P fs_þf /P NP no_et_þf_kvk fn_et_þf_kvk "  # í bókina mína
            "PP P fs_þf /P NP fn_et_þf_hk /NP /PP /NP /PP /VP /IP /S-MAIN p /S0"
        )  # um þetta .


def test_nominative(r):
    """ Test conversion of noun phrases to nominative/indefinite/canonical forms """

    s = r.parse_single("Frábærum bílskúrum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative) == "Frábærir bílskúrar"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite) == "Frábærir bílskúrar"
    )
    assert "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábær bílskúr"
    assert subj.nominative_np == "Frábærir bílskúrar"
    assert subj.indefinite_np == "Frábærir bílskúrar"
    assert subj.canonical_np == "Frábær bílskúr"

    s = r.parse_single("Frábærari bílskúrum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative)
        == "Frábærari bílskúrar"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite)
        == "Frábærari bílskúrar"
    )
    assert "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábærari bílskúr"
    assert subj.nominative_np == "Frábærari bílskúrar"
    assert subj.indefinite_np == "Frábærari bílskúrar"
    assert subj.canonical_np == "Frábærari bílskúr"

    s = r.parse_single("Frábærustum bílskúrum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative)
        == "Frábærastir bílskúrar"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite)
        == "Frábærastir bílskúrar"
    )
    assert (
        "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábærastur bílskúr"
    )
    assert subj.nominative_np == "Frábærastir bílskúrar"
    assert subj.indefinite_np == "Frábærastir bílskúrar"
    assert subj.canonical_np == "Frábærastur bílskúr"

    s = r.parse_single("Frábæru bílskúrunum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative)
        == "Frábæru bílskúrarnir"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite) == "Frábærir bílskúrar"
    )
    assert "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábær bílskúr"
    assert subj.nominative_np == "Frábæru bílskúrarnir"
    assert subj.indefinite_np == "Frábærir bílskúrar"
    assert subj.canonical_np == "Frábær bílskúr"

    s = r.parse_single("Frábærari bílskúrunum þykir þetta leiðinlegt.")
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1}".format(subj[0].nominative, subj[1].nominative)
        == "Frábærari bílskúrarnir"
    )
    assert (
        "{0} {1}".format(subj[0].indefinite, subj[1].indefinite)
        == "Frábærari bílskúrar"
    )
    assert "{0} {1}".format(subj[0].canonical, subj[1].canonical) == "Frábærari bílskúr"
    assert subj.nominative_np == "Frábærari bílskúrarnir"
    assert subj.indefinite_np == "Frábærari bílskúrar"
    assert subj.canonical_np == "Frábærari bílskúr"

    s = r.parse_single(
        "Ótrúlega frábærustu bílskúrunum þriggja góðglöðu alþingismannanna "
        "sem fóru út þykir þetta leiðinlegt."
    )
    subj = s.tree.S_MAIN.IP.NP_SUBJ
    assert (
        "{0} {1} {2}".format(subj[0].nominative, subj[1].nominative, subj[2].nominative)
        == "Ótrúlega frábærustu bílskúrarnir"
    )
    assert (
        "{0} {1} {2}".format(subj[0].indefinite, subj[1].indefinite, subj[2].indefinite)
        == "Ótrúlega frábærastir bílskúrar"
    )
    assert (
        "{0} {1} {2}".format(subj[0].canonical, subj[1].canonical, subj[2].canonical)
        == "Ótrúlega frábærastur bílskúr"
    )
    assert (
        subj.nominative_np
        == "Ótrúlega frábærustu bílskúrarnir þriggja góðglöðu alþingismannanna sem fóru út"
    )
    assert (
        subj.indefinite_np
        == "Ótrúlega frábærastir bílskúrar þriggja góðglöðu alþingismannanna sem fóru út"
    )
    assert subj.canonical_np == "Ótrúlega frábærastur bílskúr"
    subj = subj.NP_POSS
    assert subj.nominative_np == "þrír góðglöðu alþingismennirnir sem fóru út"
    assert subj.indefinite_np == "þrír góðglaðir alþingismenn sem fóru út"
    assert subj.canonical_np == "góðglaður alþingismaður"

    s = r.parse_single("Ég var í Hinu íslenska bókmenntafélagi.")
    subj = s.tree.S_MAIN.IP.VP.PP.NP
    assert subj.nominative_np == "Hið íslenska bókmenntafélag"
    assert subj.indefinite_np == "íslenskt bókmenntafélag"
    assert subj.canonical_np == "íslenskt bókmenntafélag"

    s = r.parse_single("Ég var með Páli Húnfjörð Jónssyni.")
    subj = s.tree.S_MAIN.IP.VP.PP.NP
    assert subj.nominative_np == "Páll Húnfjörð Jónsson"
    assert subj.indefinite_np == "Páll Húnfjörð Jónsson"
    assert subj.canonical_np == "Páll Húnfjörð Jónsson"

    s = r.parse_single("Ég var með Sigríði Sölku Kristínardóttur.")
    subj = s.tree.S_MAIN.IP.VP.PP.NP
    assert subj.nominative_np == "Sigríður Salka Kristínardóttir"
    assert subj.indefinite_np == "Sigríður Salka Kristínardóttir"
    assert subj.canonical_np == "Sigríður Salka Kristínardóttir"

    s = r.parse_single("Kristín málaði hús Hönnu Önfjörð Álfhildardóttur")
    assert (
        s.tree.first_match("NP-POSS").nominative_np == "Hanna Önfjörð Álfhildardóttir"
    )

    s = r.parse_single(
        "Stóri feiti Jólasveinninn beislaði "
        "fjögur sætustu hreindýrin og ók rauða VAGNINUM "
        "með fjölda gjafa til spenntu barnanna sem biðu "
        "milli vonar og ótta."
    )
    assert len(list(s.tree.all_matches("NP"))) == 6
    assert len(list(s.tree.top_matches("NP"))) == 3

    assert list(n.text for n in s.tree.all_matches("( no | lo)")) == [
        "Stóri",
        "feiti",
        "Jólasveinninn",
        "sætustu",
        "hreindýrin",
        "rauða",
        "VAGNINUM",
        "fjölda",
        "gjafa",
        "spenntu",
        "barnanna",
    ]
    assert list(n.nominative for n in s.tree.all_matches("( no | lo)")) == [
        "Stóri",
        "feiti",
        "Jólasveinninn",
        "sætustu",
        "hreindýrin",
        "rauði",
        "VAGNINN",
        "fjöldi",
        "gjafir",
        "spenntu",
        "börnin",
    ]
    assert list(n.canonical for n in s.tree.all_matches("( no | lo)")) == [
        "Stór",
        "feitur",
        "Jólasveinn",
        "sætast",
        "hreindýr",
        "rauður",
        "VAGN",
        "fjöldi",
        "gjöf",
        "spennt",
        "barn",
    ]
    assert list(
        n.canonical for t in s.tree.top_matches("NP") for n in t.all_matches("no")
    ) == ["Jólasveinn", "hreindýr", "VAGN", "fjöldi", "gjöf", "barn"]


def test_ifd_tag(r):
    """ Test IFD tagging """
    s = r.parse_single(
        "Að minnsta kosti stal Guðbjörn J. Óskarsson 200 krónum þann 19. júní 2003 "
        "og þyngdist um 300 kg."
    )
    assert s.ifd_tags == [
        "aþ",
        "lkeþve",
        "nkeþ",
        "sfg3eþ",
        "nken-m", "nken-m", "nken-m",  # Guðbjörn J. Óskarsson
        "tfvfþ",  "nvfþ",  # 200 krónum
        "fakeo",
        "ta", "nkeo", "ta",  # 19. júní 2003
        "c",
        "sfm3eþ",
        "ao",
        "ta", "x",  # 300 kg
        ".",
    ]
    s = r.parse_single(
        "Vestur-Þýskalandi bar blátt áfram að bjarga a.m.k. 284,47 börnum "
        "kl. 11:45 árið 374 f.Kr."
    )
    assert s.ifd_tags == [
        'nheþ-ö',
        'sfg3eþ',
        'lhensf',
        'aa',
        'cn',
        'sng',
        'aa',
        'tfkfn',  # 284,47
        'nhfþ',
        'nven', 'ta',  # kl. 11:45
        'nheo', 'ta', 'aa',  # árið 374 f.Kr
        '.'
    ]


def test_tree_flat(r, verbose=False):

    AMOUNTS = {
        "þf": [
            ("13", "þf", "tala"),
            ("1.234,5", "þf", "tala"),
            ("1,234.5", "þf", "tala"),
            ("13 þúsund", "þf", "tala töl"),
            ("13 þús.", "þf", "tala töl"),
            ("13 millj.", "þf", "tala töl"),
            ("13 mrð.", "þf", "tala töl"),
            ("3 þúsundir", "ef", "tala no_ft_kvk_þf"),
            ("1.234,5 milljónir", "ef", "tala no_ft_kvk_þf"),
            ("1.234,5 milljarða", "ef", "tala no_ft_kk_þf"),
            ("1,234.5 milljónir", "ef", "tala no_ft_kvk_þf"),
            ("1,234.5 milljarða", "ef", "tala no_ft_kk_þf"),
        ],
        "þgf": [
            ("13", "þgf", "tala"),
            ("1.234,5", "þgf", "tala"),
            ("1,234.5", "þgf", "tala"),
            ("13 þúsund", "þgf", "tala töl"),
            ("13 þús.", "þgf", "tala töl"),
            ("13 millj.", "þgf", "tala töl"),
            ("13 mrð.", "þgf", "tala töl"),
            ("3 þúsundum", "ef", "tala no_ft_hk_þgf"),
            ("1.234,5 milljónum", "ef", "tala no_ft_kvk_þgf"),
            ("1.234,5 milljörðum", "ef", "tala no_ft_kk_þgf"),
            ("1,234.5 milljónum", "ef", "tala no_ft_kvk_þgf"),
            ("1,234.5 milljörðum", "ef", "tala no_ft_kk_þgf"),
        ]
    }

    CURRENCIES = {
        "þf": (
            ("ISK", "no_ft_kvk_þf"),
            ("krónur", "no_ft_kvk_þf"),
            ("íslenskar krónur", "lo_ft_kvk_sb_þf no_ft_kvk_þf"),
            ("bresk pund", "lo_ft_hk_sb_þf no_ft_hk_þf"),
            ("danskar krónur", "lo_ft_kvk_sb_þf no_ft_kvk_þf"),
            ("bandaríkjadali", "no_ft_kk_þf"),
            ("bandaríska dali", "lo_ft_kk_sb_þf no_ft_kk_þf"),
            ("indónesískar rúpíur", "lo_ft_kvk_sb_þf no_ft_kvk_þf"),
            ("indverskar rúpíur", "lo_ft_kvk_sb_þf no_ft_kvk_þf"),
        ),
        "þgf": (
            ("ISK", "no_ft_kvk_þgf"),
            ("krónum", "no_ft_kvk_þgf"),
            ("íslenskum krónum", "lo_ft_kvk_sb_þgf no_ft_kvk_þgf"),
            ("breskum pundum", "lo_ft_hk_sb_þgf no_ft_hk_þgf"),
            ("dönskum krónum", "lo_ft_kvk_sb_þgf no_ft_kvk_þgf"),
            ("bandaríkjadölum", "no_ft_kk_þgf"),
            ("bandarískum dölum", "lo_ft_kk_sb_þgf no_ft_kk_þgf"),
            ("indónesískum rúpíum", "lo_ft_kvk_sb_þgf no_ft_kvk_þgf"),
            ("indverskum rúpíum", "lo_ft_kvk_sb_þgf no_ft_kvk_þgf"),
        ),
        "ef": (
            ("ISK", "no_ef_ft_kvk"),
            ("króna", "no_ef_ft_kvk"),
            ("íslenskra króna", "lo_ef_ft_kvk_sb no_ef_ft_kvk"),
            ("breskra punda", "lo_ef_ft_hk_sb no_ef_ft_hk"),
            ("danskra króna", "lo_ef_ft_kvk_sb no_ef_ft_kvk"),
            ("bandaríkjadala", "no_ef_ft_kk"),
            ("bandarískra dala", "lo_ef_ft_kk_sb no_ef_ft_kk"),
            ("indónesískra rúpía", "lo_ef_ft_kvk_sb no_ef_ft_kvk"),
            ("indverskra rúpía", "lo_ef_ft_kvk_sb no_ef_ft_kvk"),
        )
    }

    for verb_case, amounts in AMOUNTS.items():
        for amount, currency_case, t1 in amounts:
            for currency, t2 in CURRENCIES[currency_case]:
                if verb_case == "þf":
                    sent = "Hann skuldaði mér " + amount + " " + currency + "."
                elif verb_case == "þgf":
                    sent = "Hann tapaði " + amount + " " + currency + "."
                else:
                    assert False  # Unknown verb case
                if verbose:
                    print(sent)
                s = r.parse_single(sent)
                np_obj = s.tree.S.IP.VP.NP_OBJ.flat_with_all_variants
                expected = "NP-OBJ " + t1 + " " + t2 + " /NP-OBJ"
                assert np_obj == expected


def test_noun_lemmas(r):
    """ Test abbreviation lemmas ('Schengen' is an abbreviation), proper name
        lemmas ('Ísland'), and lemmas of literal terminals in the grammar
        ('munur:kk' in this case) """
    sent = "Schengen rekur mun öflugri gagnagrunn en Ísland gæti gert."
    s = r.parse_single(sent)
    assert s.tree.nouns == ["Schengen", "munur", "gagnagrunnur", "Ísland"]
    s = r.parse_single("Maður kom út úr húsinu.")
    leaves = list(s.tree.leaves)
    assert len(leaves) == len(s.tokens)
    assert leaves[0].fl == "alm"  # Not örn
    s = r.parse_single("Húsið var til sölu.")
    leaves = list(s.tree.leaves)
    assert len(leaves) == len(s.tokens)
    assert leaves[0].fl == "alm"  # Not göt
    s = r.parse_single("Ég keypti Húsið.")
    leaves = list(s.tree.leaves)
    assert len(leaves) == len(s.tokens)
    assert leaves[2].fl == "göt"  # In this case it's not alm


def test_composite_words(r):
    s = r.parse_single("Hann var mennta- og menningarmálaráðherra.")
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_1_nf_et_fh_gm_p3_þt /VP "
        "NP-PRD no_et_kk_nf st no_et_kk_nf /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hann var dómsmála-, mennta- og menningarmálaráðherra.")
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_1_nf_et_fh_gm_p3_þt /VP "
        "NP-PRD no_et_kk_nf no_et_kk_nf st no_et_kk_nf /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hann var dómsmála- ferðamála- mennta- og menningarmálaráðherra.")
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_1_nf_et_fh_gm_p3_þt /VP "
        "NP-PRD no_et_kk_nf no_et_kk_nf no_et_kk_nf st no_et_kk_nf /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hann var hálf-þýskur og fæddist í Vestur-Þýskalandi.")
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP VP so_et_fh_gm_p3_þt /VP "
        "NP-PRD lo_et_kk_nf_sb /NP-PRD /VP C st /C VP so_0_et_fh_mm_p3_þt /VP "
        "PP P fs_þgf /P NP no_et_hk_þgf /NP /PP /VP /IP /S-MAIN p /S0"
    )
    # Note that 'hálf - þýskur' is not the same as 'hálf-þýskur'
    # and 'Vestur  -  Þýskaland' is not the same as 'Vestur-Þýskaland'
    s = r.parse_single("Ég borðaði sykursaltan fiskinn")
    assert s.lemmas == ['ég', 'borða', 'sykur-saltur', 'fiskur']
    s = r.parse_single("Ég borðaði sykurinnsaltan fiskinn")
    assert s.lemmas == ['ég', 'borða', 'sykur-inn-saltur', 'fiskur']
    s = r.parse_single("Ég borðaði sykrisaltan fiskinn")
    # 'sykrisaltan' is not a valid composite word, so this should get parsed
    # as an unknown noun - causing 'fiskinn' to be parsed as an adjective
    assert s.lemmas == ['ég', 'borða', 'sykrisaltan', 'fiskinn']
    s = r.parse_single("Hann hjólaði kattspenntur á kvenbretti niður brekkuna")
    assert s.lemmas == ['hann', 'hjóla', 'katt-spenna', 'á', 'kven-bretti', 'niður', 'brekka']


def test_compressed_bin():
    import reynir.bincompress as bc
    binc = bc.BIN_Compressed()
    assert "gleraugu" in binc
    assert "Ísland" in binc
    assert "Vestur-Þýskaland" in binc
    assert "glerxaugu" not in binc
    assert "vextir" in binc
    assert "x" not in binc
    assert "X" not in binc
    assert (
        binc.lookup("aðförin") ==
        [('aðför', 123454, 'kvk', 'alm', 'aðförin', 'NFETgr')]
    )
    assert (
        binc.lookup("einkabílnum") ==
        [('einkabíll', 75579, 'kk', 'alm', 'einkabílnum', 'ÞGFETgr')]
    )
    nominal_forms = [m[4] for m in binc.nominative("einkabílnum") if m[5] == "NFETgr"]
    assert nominal_forms == ['einkabíllinn']
    # Test non-latin-1 code point (should not throw an exception)
    assert "Domino’s" not in binc
    # Test errata (BinErrata.conf)
    assert (
        binc.lookup("Hafnarfjörður") ==
        [('Hafnarfjörður', 303729, 'kk', 'örn', 'Hafnarfjörður', 'NFET')]
    )
    assert (
        binc.lookup("Gamli-Oddhóll") ==
        [('Gamli-Oddhóll', 430106, 'kk', 'örn', 'Gamli-Oddhóll', 'NFET')]
    )
    assert (
        binc.lookup("Árbæjarkirkja") ==
        [('Árbæjarkirkja', 453313, 'kvk', 'örn', 'Árbæjarkirkja', 'NFET')]
    )
    assert (
        binc.lookup("Litlihjalli") ==
        [('Litlihjalli', 282316, 'kk', 'göt', 'Litlihjalli', 'NFET')]
    )


def test_foreign_names(r):
    s = r.parse_single("Aristóteles uppgötvaði þyngdarlögmálið.")
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ person_kk_nf /NP-SUBJ VP VP so_1_þf_et_fh_gm_p3_þt /VP "
        "NP-OBJ no_et_gr_hk_þf /NP-OBJ /VP /IP /S-MAIN p /S0"
    )
    # Test to check whether 'Hafstein' works as a family name in nominative case
    s = r.parse_single("Þetta voru Ólafur Ísleifsson, Júlíus Hafstein og Ingibjörg Sólrún Gísladóttir.")
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP so_1_nf_fh_ft_gm_p3_þt /VP NP-PRD "
        "person_kk_nf person_kk_nf p person_kk_nf person_kk_nf C st /C person_kvk_nf person_kvk_nf person_kvk_nf "
        "/NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Þetta voru Ólafur Ísleifsson, Bára Hafstein og Ingibjörg Sólrún Gísladóttir.")
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP so_1_nf_fh_ft_gm_p3_þt /VP NP-PRD "
        "person_kk_nf person_kk_nf p person_kvk_nf person_kvk_nf C st /C person_kvk_nf person_kvk_nf person_kvk_nf "
        "/NP-PRD /VP /IP /S-MAIN p /S0"
    )


def test_vocabulary(r):
    """ Test words that should be in the vocabulary, coming from
        ord.auka.csv or ord.add.csv """
    s = r.parse_single("""
        Í gær gekk ég út frá ströndum og fékk mér ís.
        """)
    assert s.tree is not None
    assert "strönd" in s.tree.nouns
    s = r.parse_single("""
        Rekjanleikinn var enginn þegar ég spurði um hann.
        """)
    assert s.tree is not None
    assert "rekjanleiki" in s.tree.nouns
    s = r.parse_single("""
        Jón hafði áhyggjur af seljanleika bréfanna.
        """)
    assert s.tree is not None
    assert "seljanleiki" in s.tree.nouns
    s = r.parse_single("""
        Tvískráning bréfanna er á döfinni.
        """)
    assert s.tree is not None
    assert "tvískráning" in s.tree.nouns
    s = r.parse_single("""
        Hann vanrækti börnin alla tíð.
        """)
    assert s.tree is not None
    assert "vanrækja" in s.tree.verbs
    s = r.parse_single("""
        Milli deildanna voru kínamúrar en starfsandi var góður.
        """)
    assert s.tree is not None
    assert "kínamúr" in s.tree.nouns
    assert "starfsandi" in s.tree.nouns

    j = r.submit(
        "Ég fór í Landmannalaugar. Það var gaman í Landmannalaugum.",
        parse=True
    )
    cnt = 0
    for sent in j:
        assert sent.tree is not None
        lemma_set = set([lemma.replace("-", "") for lemma in sent.lemmas])
        assert "Landmannalaug" in lemma_set
        cnt += 1
    assert cnt == 2

    s = r.parse_single("Ég veipaði af miklum krafti og fór á marga vegu.")
    assert s.tree.flat_with_all_variants == (
        "S0 S-MAIN IP NP-SUBJ pfn_et_nf_p1 /NP-SUBJ VP VP so_0_et_fh_gm_p1_þt /VP "
        "PP P fs_þgf /P NP lo_et_kk_sb_þgf no_et_kk_þgf /NP /PP C st /C VP "
        "so_0_et_fh_gm_p1_þt /VP PP P fs_þf /P NP lo_ft_kk_sb_þf no_ft_kk_þf "
        "/NP /PP /VP /IP /S-MAIN p /S0"
    )


def test_adjective_predicates(r):
    """ Test adjectives with an associated predicate """

    # Accusative case (þolfall)
    s = r.parse_single("""
        Hundurinn var viðstaddur sýninguna sem fjallaði um hann.
        """)
    assert "NP-PRD lo_sb_nf_sþf_et_kk NP-ADP no_et_þf_kvk" in s.tree.flat

    # Dative case (þágufall)
    s = r.parse_single("""
        Hundurinn var málkunnugur kettinum frá fyrri tíð.
        """)
    assert "NP-PRD lo_sb_nf_sþgf_et_kk NP-ADP no_et_þgf_kk /NP-ADP /NP-PRD" in s.tree.flat

    # Possessive case (eignarfall)
    s = r.parse_single("""
        Kötturinn þóttist vera frjáls ferða sinna.
        """)
    assert "NP-PRD lo_sb_nf_sef_et_kk NP-ADP no_ft_ef_kvk fn_ft_ef_kvk /NP-ADP /NP-PRD" in s.tree.flat
    s = r.parse_single("""
        Kötturinn hafði verið fullur sjálfstrausts.
        """)
    assert "NP-PRD lo_sb_nf_sef_et_kk NP-ADP no_et_ef_hk /NP-ADP /NP-PRD" in s.tree.flat
    s = r.parse_single("""
        Verkamaðurinn er verður launa sinna.
        """)
    assert "NP-PRD lo_sb_nf_sef_et_kk NP-ADP no_ft_ef_hk fn_ft_ef_hk /NP-ADP /NP-PRD" in s.tree.flat


def test_subj_op(r):
    """ Test impersonal verbs """
    # langa
    s = r.parse_single("hestinn langaði í brauð")
    assert s.tree is not None
    assert s.tree.nouns == ["hestur", "brauð"]
    assert s.tree.verbs == ["langa"]
    s = r.parse_single("hesturinn langaði í brauð")
    assert s.tree is None
    s = r.parse_single("hestinum langaði í brauð")
    assert s.tree is None
    s = r.parse_single("hestsins langaði í brauð")
    assert s.tree is None
    # dreyma e-ð
    s = r.parse_single("hestinn dreymdi köttinn")
    assert s.tree is not None
    assert s.tree.nouns == ["hestur", "köttur"]
    assert s.tree.verbs == ["dreyma"]
    s = r.parse_single("hesturinn dreymdi köttinn")
    assert s.tree is None
    s = r.parse_single("hestinum dreymdi köttinn")
    assert s.tree is None
    s = r.parse_single("hestsins dreymdi köttinn")
    assert s.tree is None
    s = r.parse_single("hestinn dreymdi kettinum")
    assert s.tree is None
    s = r.parse_single("hestinn dreymdi kattarins")
    assert s.tree is None
    # hraka
    s = r.parse_single("hestinum hrakaði hratt")
    assert s.tree is not None
    assert s.tree.nouns == ["hestur"]
    assert s.tree.verbs == ["hraka"]
    s = r.parse_single("hesturinn hrakaði hratt")
    assert s.tree is None
    s = r.parse_single("hestinn hrakaði hratt")
    assert s.tree is None
    s = r.parse_single("hestsins hrakaði hratt")
    assert s.tree is None
    # blöskra e-ð
    s = r.parse_single("mér blöskraði vitleysan í Páli")
    assert s.tree is not None
    assert s.tree.nouns == ["vitleysa", "Páll"]
    assert s.tree.verbs == ["blöskra"]
    s = r.parse_single("ég blöskraði vitleysan í Páli")
    assert s.tree is None
    s = r.parse_single("mig blöskraði vitleysan í Páli")
    assert s.tree is None
    s = r.parse_single("mín blöskraði vitleysan í Páli")
    assert s.tree is None
    s = r.parse_single("mér blöskraði vitleysuna í Páli")
    assert s.tree is None
    s = r.parse_single("mér blöskraði vitleysunni í Páli")
    assert s.tree is None
    s = r.parse_single("mér blöskraði vitleysunnar í Páli")
    assert s.tree is None


def test_names(r):
    s = r.parse_single("Sýningarnar voru í Gamla bíói á þriðjudagskvöldum.")
    assert s.tree is not None
    assert s.tree.persons == []
    assert s.tree.nouns == ["sýning", "bíó", "þriðjudagskvöld"]


def test_prepositions(r):
    s = r.parse_single("Ég fór niðrá bryggjuna.")
    assert s.tree is not None
    assert s.tree.match("S0 >> { IP > { VP > { PP > { P > { fs } } } } } ")


def test_personally(r):
    s = r.parse_single("Mér persónulega þótti þetta ekki flott.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ pfn_et_p1_þgf ao /NP-SUBJ VP VP so_subj_op_þgf_et_fh_gm_þt /VP "
        "NP fn_et_hk_nf /NP NP-PRD ADVP eo /ADVP lo_et_hk_nf_sb /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Þetta mál varðar þig persónulega.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf no_et_hk_nf /NP-SUBJ VP VP "
        "so_1_þf_et_fh_gm_nt_p3 /VP NP-OBJ pfn_et_p2_þf ao /NP-OBJ /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Þetta kom illa við þær persónulega.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP so_0_et_fh_gm_p3_þt /VP "
        "ADVP ao /ADVP PP P fs_þf /P NP pfn_ft_kvk_p3_þf ao /NP /PP /VP /IP /S-MAIN p /S0"
    )


def test_adjectives(r):
    sents = [
        "Páll er skemmtilegur.",
        "Páll varð skemmtilegur.",
        "Páll má vera skemmtilegur.",
        "Páll mætti verða skemmtilegur.",
        "Páll skyldi vera skemmtilegur.",
        "Páll skal verða skemmtilegur.",
        "Páll hefur verið skemmtilegur.",
        "Páll hefur orðið skemmtilegur.",
        "Páll hefði viljað vera skemmtilegur.",
        "Páll hefði viljað verða skemmtilegur.",
        "Páll hefði getað verið skemmtilegur.",
        "Páll hefði getað orðið skemmtilegur.",
        # Of mikið af því góða?
        # "Páll hefði getað átt að vera skemmtilegur.",
        # "Páll hafði getað átt að verða skemmtilegur.",
        "Páll mætti hafa verið skemmtilegur.",
        "Páll má hafa orðið skemmtilegur.",
        "Páll skal hafa verið skemmtilegur.",
        "Páll skyldi hafa orðið skemmtilegur.",
        "Páll gæti hafa verið skemmtilegur.",
        "Páll gæti hafa orðið skemmtilegur.",
        "Páll ætti að vera skemmtilegur.",
        "Páll ætti að hafa verið skemmtilegur.",
        "Páll átti að verða skemmtilegur.",
        "Páll á að hafa orðið skemmtilegur.",
        "Páll gæti hafa átt að vera skemmtilegur.",
        "Páll getur hafa átt að verða skemmtilegur.",
    ]
    for sent in sents:
        s = r.parse_single(sent)
        assert s.tree is not None
        assert s.tree.nouns == ["Páll"]
        assert s.tree.S_MAIN.IP.VP.NP_PRD.lemmas == ["skemmtilegur"]


def test_all_mine(r):
    s = r.parse_single("Ég setti allt mitt í hlutabréfin.")
    assert s.tree is not None
    assert s.tree.nouns == ["hlutabréf"]
    assert s.tree.S.IP.VP.VP.NP_OBJ.lemmas == ["allur", "minn"]
    s = r.parse_single("Ég tapaði öllu mínu í spilakössum.")
    assert s.tree is not None
    assert s.tree.nouns == ["spilakassi"]
    assert s.tree.S.IP.VP.VP.NP_OBJ.lemmas == ["allur", "minn"]
    s = r.parse_single("Þú settir allt þitt í hlutabréfin.")
    assert s.tree is not None
    assert s.tree.nouns == ["hlutabréf"]
    assert s.tree.S.IP.VP.VP.NP_OBJ.lemmas == ["allur", "þinn"]
    s = r.parse_single("Þú tapaðir öllu þínu í spilakössum.")
    assert s.tree is not None
    assert s.tree.nouns == ["spilakassi"]
    assert s.tree.S.IP.VP.VP.NP_OBJ.lemmas == ["allur", "þinn"]
    s = r.parse_single("Hann setti allt sitt í hlutabréfin.")
    assert s.tree is not None
    assert s.tree.nouns == ["hlutabréf"]
    assert s.tree.S.IP.VP.VP.NP_OBJ.lemmas == ["allur", "sinn"]
    s = r.parse_single("Hún tapaði öllu sínu í spilakössum.")
    assert s.tree is not None
    assert s.tree.nouns == ["spilakassi"]
    assert s.tree.S.IP.VP.VP.NP_OBJ.lemmas == ["allur", "sinn"]


def test_company(r):
    s = r.parse_single("Hann réðst inn á skrifstofu Samherja hf. og rændi gögnum.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ pfn_et_kk_nf_p3 /NP-SUBJ VP VP so_0_et_fh_mm_p3_þt "
        "/VP PP ADVP-DIR ao /ADVP-DIR P fs_þf /P NP no_et_kvk_þf NP-POSS NP-COMPANY "
        "sérnafn_ef fyrirtæki /NP-COMPANY /NP-POSS /NP /PP C st /C VP VP "
        "so_1_þgf_et_fh_gm_p3_þt /VP NP-OBJ no_ft_hk_þgf /NP-OBJ /VP /VP /IP /S-MAIN p /S0"
    )
    # !!! Note that lemmas of words found in BÍN are in lower case
    assert [t.lemma for t in s.tree.all_matches("NP-COMPANY")] == ["samherji hf."]
    s = r.parse_single("Hands ASA er dótturfyrirtæki Celestial Inc.")
    assert s.tree is not None
    assert (
        s.tree.flat_with_all_variants ==
        "S0 S-MAIN IP NP-SUBJ NP-COMPANY sérnafn fyrirtæki /NP-COMPANY /NP-SUBJ "
        "VP VP so_1_nf_et_fh_gm_nt_p3 /VP NP-PRD no_et_hk_nf NP-POSS "
        "NP-COMPANY sérnafn fyrirtæki /NP-COMPANY /NP-POSS /NP-PRD /VP /IP /S-MAIN p /S0"
    )
    assert (
        [t.lemma for t in s.tree.all_matches("NP-COMPANY")] ==
        ['Hands Allmennaksjeselskap', 'Celestial Incorporated']
    )


def test_kludgy_ordinals():
    from reynir import Reynir, KLUDGY_ORDINALS_PASS_THROUGH
    r2 = Reynir(handle_kludgy_ordinals=KLUDGY_ORDINALS_PASS_THROUGH)
    s = r2.parse_single(
        "Hann keypti 3ja herbergja íbúð á 1stu hæð "
        "en hún átti 2ja strokka mótorhjól af 4ðu kynslóð."
    )
    assert s.tree is not None
    # þriggja herbergja
    assert "NP-POSS to_ft_ef_hk no_ft_ef_hk /NP-POSS" in s.tree.flat
    # á fyrstu hæð
    assert "PP P fs_þf /P NP lo_þf_et_kvk no_et_þf_kvk /NP /PP" in s.tree.flat
    # tveggja strokka
    assert "NP-POSS to_ft_ef_kk no_ft_ef_kk /NP-POSS" in s.tree.flat
    # af fjórðu kynslóð
    assert "PP P fs_þgf /P NP lo_þgf_et_kvk no_et_þgf_kvk /NP /PP" in s.tree.flat


def test_adjective_dative(r):
    s = r.parse_single(
        "Páli er í grundvallaratriðum óheimilt að gegna öðrum störfum "
        "meðan hann er þingmaður."
    )
    assert (
        s.tree.flat == "S0 S-MAIN IP IP NP-SUBJ person_þgf_kk /NP-SUBJ VP "
        "so_et_p3 /VP PP P fs_þgf /P NP no_ft_þgf_hk /NP /PP NP-PRD lo_nf_et_hk_sb "
        "/NP-PRD /IP IP-INF TO nhm /TO VP VP so_1_þgf_nh /VP "
        "NP-OBJ fn_ft_þgf_hk no_ft_þgf_hk /NP-OBJ /VP /IP-INF CP-ADV-TEMP "
        "C st /C IP NP-SUBJ pfn_kk_et_nf /NP-SUBJ VP VP so_1_nf_et_p3 /VP "
        "NP-PRD no_et_nf_kk /NP-PRD /VP /IP /CP-ADV-TEMP /IP /S-MAIN p /S0"
    )


def test_ambig_phrases(r):

    def has_verbs(s, v):
        return set(s.tree.verbs) == set(v)

    s = r.parse_single("Hann var sá sem ég treysti best.")
    assert has_verbs(s, ("vera", "treysta"))
    s = r.parse_single("Hún hefur verið sú sem ég treysti best.")
    assert has_verbs(s, ("hafa", "vera", "treysta"))
    s = r.parse_single("Hún væri sú sem ég treysti best.")
    assert has_verbs(s, ("vera", "treysta"))
    s = r.parse_single("Ég fór að kaupa inn en hún var að selja eignir.")
    assert has_verbs(s, ("vera", "fara", "kaupa", "selja"))
    s = r.parse_single("Ég setti gleraugun ofan á kommóðuna.")
    assert has_verbs(s, ("setja",))
    s = r.parse_single("Hugmynd Jóns varð ofan á í umræðunni.")
    assert has_verbs(s, ("verða",))
    s = r.parse_single("Efsta húsið er það síðasta sem var lokið við.")
    assert has_verbs(s, ("vera", "ljúka"))
    s = r.parse_single("Hún var fljót að fara út.")
    assert has_verbs(s, ("vera", "fara"))
    s = r.parse_single("Það var forsenda þess að hún var fljót að maturinn var góður.")
    assert has_verbs(s, ("vera",))
    s = r.parse_single("Peningarnir verða nýttir til uppbyggingar.")
    assert has_verbs(s, ("verða", "nýta"))
    s = r.parse_single("Ég vildi ekki segja neitt sem ræðan stangaðist á við.")
    assert has_verbs(s, ("vilja", "segja", "stanga"))
    s = r.parse_single("Reglurnar stönguðust á við raunveruleikann.")
    assert has_verbs(s, ("stanga",))
    s = r.parse_single("Hann braut gegn venju með því að hnerra.")
    assert has_verbs(s, ("brjóta", "hnerra"))
    s = r.parse_single("Hann braut gegn venju með því að ræðan var óhefðbundin.")
    assert has_verbs(s, ("brjóta", "vera"))


def test_relative_clause(r):
    s = r.parse_single(
        "Þetta eru lausnirnar sem kallað hefur verið eftir."
    )
    assert (
        s.tree.flat_with_all_variants =="S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP "
        "so_1_nf_fh_ft_gm_nt_p3 /VP NP-PRD no_ft_gr_kvk_nf CP-REL C stt /C "
        "S-MAIN NP-PRD VP so_et_hk_lhþt_nf_sb /VP /NP-PRD VP VP so_et_fh_gm_nt_p3 /VP "
        "VP so_gm_sagnb /VP /VP ADVP ao /ADVP /S-MAIN /CP-REL /NP-PRD /VP /IP "
        "/S-MAIN p /S0"
    )


def test_neutral_pronoun(r):
    s = r.parse_single("Hán var ánægt með hest háns.")
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 /NP-SUBJ "
        "VP VP so_et_fh_gm_p3_þt /VP NP-PRD NP-PRD lo_et_hk_nf_sb /NP-PRD "
        "PP P fs_þf /P NP no_et_kk_þf NP-POSS pfn_ef_et_hk_p3 /NP-POSS /NP /PP /NP-PRD "
        "/VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hán langaði að tala við hán um málið.")
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_p3_þf /NP-SUBJ "
        "VP VP so_1_þf_subj_op_þf_et_fh_gm_þt /VP IP-INF TO nhm /TO VP so_0_gm_nh "
        "/VP /IP-INF PP P fs_þf /P NP pfn_et_hk_p3_þf /NP /PP PP P fs_þf /P NP "
        "no_et_gr_hk_þf /NP /PP /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hán Alda var ánægt.")
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 "
        "person_kvk_nf /NP-SUBJ VP VP so_et_fh_gm_p3_þt /VP NP-PRD lo_et_hk_nf_sb "
        "/NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hán Halldór var ánægt.")
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 "
        "person_kk_nf /NP-SUBJ VP VP so_et_fh_gm_p3_þt /VP NP-PRD lo_et_hk_nf_sb "
        "/NP-PRD /VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Hán Auður leitaði álits háns Ilmar.")
    # 'Auður' er bæði í kk og kvk í BÍN
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 "
        "person_kvk_nf /NP-SUBJ VP VP so_1_ef_et_fh_gm_p3_þt /VP NP-OBJ "
        "no_ef_et_hk NP-POSS pfn_ef_et_hk_p3 person_ef_kvk /NP-POSS /NP-OBJ "
        "/VP /IP /S-MAIN p /S0"
    ) or (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_nf_p3 "
        "person_kk_nf /NP-SUBJ VP VP so_1_ef_et_fh_gm_p3_þt /VP NP-OBJ "
        "no_ef_et_hk NP-POSS pfn_ef_et_hk_p3 person_ef_kvk /NP-POSS /NP-OBJ "
        "/VP /IP /S-MAIN p /S0"
    )
    s = r.parse_single("Háni féll illa að talað var af vanvirðingu um hán.")
    assert (
        s.tree.flat_with_all_variants == "S0 S-MAIN IP NP-SUBJ pfn_et_hk_p3_þgf "
        "/NP-SUBJ VP VP so_1_nf_subj_op_þgf_et_fh_gm_þt /VP NP-OBJ eo CP-THT C st /C "
        "IP VP VP so_gm_sagnb /VP VP so_et_fh_gm_p3_þt /VP PP P fs_þgf /P NP "
        "no_et_kvk_þgf PP P fs_þf /P NP pfn_et_hk_p3_þf /NP /PP /NP /PP /VP /IP "
        "/CP-THT /NP-OBJ /VP /IP /S-MAIN p /S0"
    )

if __name__ == "__main__":
    # When invoked as a main module, do a verbose test
    from reynir import Reynir
    r = Reynir()
    test_compressed_bin()
    test_parse(r, verbose=True)
    test_properties(r)
    test_long_parse(r, verbose=True)
    test_consistency(r, verbose=True)
    test_terminals(r)
    test_single(r)
    test_year_range(r)
    test_amounts(r)
    test_complex(r, verbose=True)
    test_attachment(r, verbose=True)
    test_measurements(r)
    test_abbreviations(r)
    test_nominative(r)
    test_ifd_tag(r)
    test_tree_flat(r, verbose=True)
    test_noun_lemmas(r)
    test_composite_words(r)
    test_foreign_names(r)
    test_vocabulary(r)
    test_adjective_predicates(r)
    test_subj_op(r)
    test_names(r)
    test_prepositions(r)
    test_personally(r)
    test_company(r)
    test_adjectives(r)
    test_all_mine(r)
    test_kludgy_ordinals()
    test_adjective_dative(r)
    test_ambig_phrases(r)
    test_relative_clause(r)
    test_neutral_pronoun(r)
    r.__class__.cleanup()
