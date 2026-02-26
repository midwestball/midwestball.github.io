import sys
import unittest
from trade import clean_name

class TestTrade(unittest.TestCase):
    def test_clean_name(self):
        self.assertEqual(clean_name("LeBron James"), "lebronjames")
        self.assertEqual(clean_name("O.G. Anunoby"), "oganunoby")
        self.assertEqual(clean_name("Marcus Morris Sr."), "marcusmorrissr")

if __name__ == '__main__':
    unittest.main()
