from pathlib import Path
import os

ROOT=Path(os.environ.get('GOUXU_PROJECT_ROOT',Path(__file__).resolve().parents[3])).resolve()
STATE=Path(os.environ.get('GOUXU_STATE_ROOT',ROOT/'data/state')).resolve()
DATA=Path(os.environ.get('GOUXU_DATA_ROOT',ROOT/'data/processed')).resolve()
VERSION='request-item-pair-v1'
PALETTE=[('#7362DF','#534397'),('#4DB692','#286A56'),('#4286D8','#2D5C94'),('#EAB74B','#806020'),('#D678AD','#844465'),('#E78C64','#8D4B2F'),('#4CB9C3','#2C7177')]
