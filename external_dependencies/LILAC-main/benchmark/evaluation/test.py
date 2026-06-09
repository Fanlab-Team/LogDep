import sys
import os

print("Before:", sys.path)
sys.path.append('../')
print("After:", sys.path)

from benchmark.logparser.LILAC import LogParser
from settings import benchmark_settings
from utils.common import common_args
from utils.evaluator_main import evaluator, prepare_results
from utils.postprocess import post_average
print("当前工作目录:", os.getcwd())