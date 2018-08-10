from pylivetrader.misc.configloader import load_config
import pylivetrader
from pathlib import Path

base = str(Path(pylivetrader.__file__).parent.parent)


def get_config(name):
    return base + '/tests/test_misc/sample/' + name


def test_load_config():
    files = ['config.yml', 'config.json']
    for f in files:
        o = load_config(get_config(f))
        print('xxx', list(o.items()))
        assert o['api_key_id'] == 'key_id'
        assert o['api_secret'] == 'secret'
