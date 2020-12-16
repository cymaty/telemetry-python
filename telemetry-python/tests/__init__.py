import logging
import sys

logging.root.addHandler(logging.StreamHandler(sys.stdout))
logging.root.setLevel(logging.DEBUG)
