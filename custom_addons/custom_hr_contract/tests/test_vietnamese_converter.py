# Part of custom_hr_contract. See LICENSE file for full copyright and licensing details.

import unittest

from odoo.addons.custom_hr_contract.tools.vietnamese_converter import num_to_words_vi


class TestVietnameseConverter(unittest.TestCase):
    """Unit tests for pure Python Vietnamese number-to-words currency reader."""

    def test_zero(self):
        self.assertEqual(num_to_words_vi(0), "Không đồng chẵn")

    def test_single_digits(self):
        self.assertEqual(num_to_words_vi(5), "Năm đồng chẵn")
        self.assertEqual(num_to_words_vi(9), "Chín đồng chẵn")

    def test_tens(self):
        self.assertEqual(num_to_words_vi(10), "Mười đồng chẵn")
        self.assertEqual(num_to_words_vi(11), "Mười một đồng chẵn")
        self.assertEqual(num_to_words_vi(15), "Mười lăm đồng chẵn")
        self.assertEqual(num_to_words_vi(20), "Hai mươi đồng chẵn")
        self.assertEqual(num_to_words_vi(21), "Hai mươi mốt đồng chẵn")
        self.assertEqual(num_to_words_vi(24), "Hai mươi tư đồng chẵn")
        self.assertEqual(num_to_words_vi(25), "Hai mươi lăm đồng chẵn")

    def test_hundreds(self):
        self.assertEqual(num_to_words_vi(100), "Một trăm đồng chẵn")
        self.assertEqual(num_to_words_vi(105), "Một trăm lẻ năm đồng chẵn")
        self.assertEqual(num_to_words_vi(115), "Một trăm mười lăm đồng chẵn")
        self.assertEqual(num_to_words_vi(500), "Năm trăm đồng chẵn")

    def test_thousands_and_millions(self):
        self.assertEqual(num_to_words_vi(1000), "Một nghìn đồng chẵn")
        self.assertEqual(num_to_words_vi(1500), "Một nghìn năm trăm đồng chẵn")
        self.assertEqual(num_to_words_vi(1005), "Một nghìn không trăm lẻ năm đồng chẵn")
        self.assertEqual(num_to_words_vi(15000000), "Mười lăm triệu đồng chẵn")
        self.assertEqual(
            num_to_words_vi(25450000),
            "Hai mươi lăm triệu bốn trăm năm mươi nghìn đồng chẵn",
        )
        self.assertEqual(num_to_words_vi(100000000), "Một trăm triệu đồng chẵn")

    def test_billions(self):
        self.assertEqual(num_to_words_vi(1000000000), "Một tỷ đồng chẵn")
        self.assertEqual(
            num_to_words_vi(1250000000),
            "Một tỷ hai trăm năm mươi triệu đồng chẵn",
        )

    def test_negative_numbers(self):
        self.assertTrue(num_to_words_vi(-15000000).startswith("Âm"))

    def test_custom_currency_and_suffix(self):
        self.assertEqual(
            num_to_words_vi(15000000, currency="VNĐ", suffix=""),
            "Mười lăm triệu VNĐ",
        )
        self.assertEqual(
            num_to_words_vi(10, currency="", suffix=""),
            "Mười",
        )

    def test_invalid_types(self):
        with self.assertRaises(TypeError):
            num_to_words_vi("15000000")
        with self.assertRaises(TypeError):
            num_to_words_vi(None)

    def test_overflow(self):
        with self.assertRaises(ValueError):
            num_to_words_vi(10**18)
