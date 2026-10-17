from unittest import TestCase

from robingraph.api.question_entities import extract_name
from robingraph.retrieval.species_questions import bounded_korean_name, parse_species_question


class SpacedKoreanNameTest(TestCase):
    def test_source_spaces_are_one_bounded_span(self):
        for question, label in (("흰뺨 검둥 오리에 대해 알고 싶어", "profile"), ("흰뺨 검둥 오리 정보 알려줘", "profile"),
                                ("흰뺨 검둥 오리는 뭘 먹어?", "diet"), ("흰뺨 검둥 오리 아종 알려줘", "subspecies"),
                                ("'흰뺨 검둥 오리' 소개해줘", "profile")):
            with self.subTest(question=question):
                self.assertEqual("흰뺨 검둥 오리", extract_name(question, label))
        result = parse_species_question("흰뺨 검둥 오리는 뭘 먹어")
        self.assertEqual(("흰뺨 검둥 오리", "diet", None), (result.name, result.topic, result.category))
        result = parse_species_question("흰뺨 검둥 오리와 비슷한 종은 어떤게 있니?")
        self.assertEqual(("흰뺨 검둥 오리", "related"), (result.name, result.topic))

    def test_raw_multi_space_mention_is_preserved(self):
        self.assertEqual("흰뺨  검둥   오리", extract_name("흰뺨  검둥   오리에 대해 알고 싶어", "profile"))
        self.assertEqual("흰뺨  검둥 오리", parse_species_question("흰뺨  검둥 오리는 뭘 먹어?").name)
        self.assertEqual("Anas  zonorhyncha", parse_species_question("Anas  zonorhyncha는 어디 살아?").name)

    def test_multi_name_lists_and_phrases_are_not_one_name(self):
        for question, label in (("청둥오리와 왜가리 정보 알려줘", "profile"), ("청둥오리랑 왜가리 소개", "profile"),
                                ("곤줄박이 말고 박새 설명해줘", "profile"), ("그 새 아종 알려줘", "subspecies"),
                                ("어제 본 새 정보 알려줘", "profile"), ("청둥오리 그리고 왜가리 아종 알려줘", "subspecies"),
                                ("청둥오리, 왜가리 정보", "profile")):
            with self.subTest(question=question):
                self.assertIsNone(extract_name(question, label))
        for question in ("청둥오리와 왜가리는 뭘 먹어", "혹시 왜가리는 뭘 먹어", "곤줄박이 말고 박새는 어디 살아",
                         "가 나 다 라 마는 뭘 먹어", "왜" * 250 + "는 뭘 먹어"):
            with self.subTest(question=question):
                self.assertIsNone(parse_species_question(question))
        self.assertFalse(bounded_korean_name("가 나 다 라 마"))
        self.assertFalse(bounded_korean_name("청둥오리와 왜가리"))
        self.assertTrue(bounded_korean_name("흰뺨 검둥 오리"))

    def test_family_suffix_is_not_stripped_to_a_species(self):
        self.assertEqual("황새과", extract_name("황새과 정보 알려줘", "profile"))
        self.assertEqual("황새과", extract_name("황새과는 무슨 목이야", "taxonomy"))
        self.assertEqual("까마귀과", extract_name("까마귀과 특징 알려줘", "profile"))
        self.assertEqual("황새과", extract_name("황새과와 비슷한 새", "related"))
        self.assertEqual("황새", extract_name("황새의 과는 뭐야", "taxonomy"))
        # consonant + 과 is family-or-particle: only a comparison resolves it
        self.assertIsNone(extract_name("꿩과 정보 알려줘", "profile"))
        self.assertEqual("꿩", extract_name("꿩과 비슷한 새 알려줘", "related"))
        self.assertEqual("청둥오리", extract_name("청둥오리와 비슷한 새", "related"))
        self.assertEqual("청둥오리", extract_name("청둥오리와 서식 환경이 비슷한 새", "ecological_habitat"))

    def test_canonical_scientific_english_and_final_i_names_unchanged(self):
        for question, label, name in (("흰뺨검둥오리에 대해 알고 싶어", "profile", "흰뺨검둥오리"),
                                      ("부엉이 정보 알려줘", "profile", "부엉이"),
                                      ("오목눈이에 대해 알려줘", "profile", "오목눈이"),
                                      ("Anas zonorhyncha에 대해 알려줘", "profile", "Anas zonorhyncha"),
                                      ("List subspecies of Anas platyrhynchos", "subspecies", "Anas platyrhynchos"),
                                      ("Tell me about Cinereous Tit", "profile", "Cinereous Tit"),
                                      ("혹시 왜가리 정보", "profile", "왜가리")):
            with self.subTest(question=question):
                self.assertEqual(name, extract_name(question, label))
        self.assertEqual("Anas platyrhynchos conboschas",
                         parse_species_question("Anas platyrhynchos conboschas는 어디 살아?").name)
        self.assertIsNone(parse_species_question("왜가리에 대해 알려줘"))  # general profile stays with the API
