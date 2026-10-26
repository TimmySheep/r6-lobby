import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('daily_reset', ROOT / 'daily_reset.py')
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)

class DailyResetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.data, self.game, self.marker = root/'people.json', root/'game-status.json', root/'last-reset-date'
        self.original = reset.DATA, reset.GAME_STATUS, reset.MARKER
        reset.DATA, reset.GAME_STATUS, reset.MARKER = self.data, self.game, self.marker
    def tearDown(self):
        reset.DATA, reset.GAME_STATUS, reset.MARKER = self.original
        self.temp.cleanup()
    def test_daily_reset_sets_roster_undecided_and_game_status_false(self):
        people = [{'name':'Player Alpha','status':'yes','time':'any'}, {'name':'Player Beta','status':'no','time':'21:15'}]
        self.data.write_text(json.dumps(people))
        self.game.write_text('{"playing":true}')
        self.marker.write_text('2000-01-01\n')
        self.assertEqual(reset.main(), 0)
        saved = json.loads(self.data.read_text())
        self.assertEqual([p['status'] for p in saved], ['maybe','maybe'])
        self.assertEqual([p['time'] for p in saved], ['any','21:15'])
        self.assertEqual(json.loads(self.game.read_text()), {'playing':False})
        self.assertEqual(reset.main(), 0)
        self.assertEqual(json.loads(self.game.read_text()), {'playing':False})
    def test_invalid_roster_does_not_reset_game_status(self):
        self.data.write_text('{broken')
        self.game.write_text('{"playing":true}')
        self.marker.write_text('2000-01-01\n')
        with self.assertRaises(SystemExit): reset.main()
        self.assertEqual(json.loads(self.game.read_text()), {'playing':True})

if __name__ == '__main__': unittest.main()
