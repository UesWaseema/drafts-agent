from analysis_interspire.scoring.rules_subject import (
    analyse_subject, caps_score, length_score
)

def test_length_good():
    assert length_score("A"*40) == 30
def test_length_bad():
    assert length_score("short") == -25
def test_caps_penalty():
    assert caps_score("THIS IS BAD") < 0
def test_keyword_bonus():
    d = analyse_subject("Call for papers – submit now")
    assert d["subject_keyword_score"] == 8
def test_overall_varies():
    good = analyse_subject("Call for papers by June (AI)")
    bad  = analyse_subject("FREE MONEY!!!")
    assert good["subject_overall_score"] != bad["subject_overall_score"]
