import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from whosat.config import WhosatConfig, load_config, save_config
from whosat.theme import get_theme, next_theme_name


class ThemeConfigTests(unittest.TestCase):
    def test_save_and_load_theme(self):
        with TemporaryDirectory() as td:
            p = Path(td) / 'config.toml'
            save_config(WhosatConfig(theme='nord'), p)
            cfg = load_config(p)
            self.assertEqual(cfg.theme, 'nord')

    def test_next_theme_cycles(self):
        self.assertNotEqual(next_theme_name('matrix'), 'matrix')
        self.assertEqual(get_theme('nope').name, 'matrix')


if __name__ == '__main__':
    unittest.main()
