import os, platform
def _data_dir():
    s = platform.system()
    if s == 'Windows': return os.path.join(os.environ.get('APPDATA','~'),'PsychAid')
    elif s == 'Darwin': return os.path.expanduser('~/Library/Application Support/PsychAid')
    return os.path.expanduser('~/.psychaid')
DATA_DIR = _data_dir()
def init_db(): os.makedirs(DATA_DIR, exist_ok=True)
