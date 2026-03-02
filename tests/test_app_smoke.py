import unittest


class AppSmokeTests(unittest.TestCase):
    def test_import_or_skip(self):
        try:
            from whosat.app import WhosatApp  # noqa: F401
        except ModuleNotFoundError as exc:
            if exc.name == 'textual':
                self.skipTest('textual not installed in local environment')
            raise


if __name__ == '__main__':
    unittest.main()
