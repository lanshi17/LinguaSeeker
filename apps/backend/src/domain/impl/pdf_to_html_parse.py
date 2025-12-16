# 将pdf解析为html 
from abc.base_parse import BaseParse
from utils.logger import Logger
from utils.exceptions import ParseException
from typing import Any
import pdfplumber

class PDFToHTMLParse(BaseParse):
