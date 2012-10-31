from getty import GettyImage
from datetime import datetime
import unittest
import pytz


class DateTests(unittest.TestCase):

    def test_parse_simple_date(self):
        json_date = '/Date(1267643668000)/'
        python_date = GettyImage.to_datetime(json_date)
        expected_date = datetime(2010, 3, 3, 19, 14, 28, 0, pytz.UTC)
        self.assertEqual(python_date, expected_date)

    def test_unknown_date_format(self):
        json_date = 'Wed Mar  3 20:14:28 2010'
        python_date = GettyImage.to_datetime(json_date)
        self.assertEqual(python_date, None)

    def test_timezone_aware_datetime(self):
        json_date = '/Date(1297286970531-0800)/"'
        python_date = GettyImage.to_datetime(json_date)
        expected_date = datetime(2011, 2, 9, 13, 29, 30,
                                 tzinfo=pytz.FixedOffset(-480))
        self.assertEqual(python_date, expected_date)


if __name__ == '__main__':
    unittest.main()
