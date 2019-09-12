import ptvsd
ptvsd.enable_attach()

from reynir import Reynir
r = Reynir()
s = r.parse_single("Hann var sá sem ég treysti best.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Hún hefur verið sú sem ég treysti best.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Hún væri sú sem ég treysti best.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Ég fór að kaupa inn en hún var að selja eignir.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Ég setti gleraugun ofan á kommóðuna.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Hugmynd Jóns varð ofan á í umræðunni.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Efsta húsið er það síðasta sem var lokið við.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Hún var fljót að fara út.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Það var forsenda þess að hún var fljót að maturinn var góður.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Peningarnir verða nýttir til uppbyggingar.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Ég vildi ekki segja neitt sem ræðan stangaðist á við.")
print(s.tree.flat_with_all_variants)
s = r.parse_single("Reglurnar stönguðust á við raunveruleikann.")
print(s.tree.flat_with_all_variants)
