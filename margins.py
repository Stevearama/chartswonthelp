#margins.py

import pandas as pd
import numpy as np
import bberg

ref_margin_tickers = {
    "USGC Bakken Cracking": "NANM0054 Index",
    "USGC LLS Cracking": "NANM00A2 Index",
    "USGC Mars Coking": "NANM00CC Index",
    "USGC EF Cracking": "NANM007E Index",
    "USGC Maya Coking": "NANM00DE Index",
    "USGC WCS Coking": "NANM0120 Index",
    "USGC Agbami Cracking": "NANM013E Index",
    "USAC Saharan Cracking": "NANV004A Index",
    "USAC Bakken": "NANV0026 Index",
    "Midcon Bakken Cracking": "NANK0023 Index",
    "Midcon Syncrude Cracking": "NANK0029 Index",
    "Midcon WTI Cracking": "NANK0041 Index",
    "Midcon WCS Coking": "NANK002F Index",
    "USWC ANS Coking": "NANU004F Index",
    "USWC Maya Coking": "NANU0031 Index",
    "USWC Oriente Coking": "NANU003D Index",
    "USWC Arab Light Coking": "PNT1CM25 Index",
    "USWC Arab Medium Coking": "NANU002B Index",
    "USWC Basrah Heavy Coking": "NANU0055 Index",
    "USWC Napo Coking": "NANU0037 Index",
    "NWE Agbami Cracking": "NANW0039 Index",
    "NWE CPC Cracking": "NANW0100 Index",
    "NWE Forties Cracking": "NANW0043 Index",
    "NWE Johan Sverdrup Cracking": "NANW0049 Index",
    "NWE Sarahan Blend Cracking": "NANW0079 Index",
    "NWE WTIM Cracking": "NANW0085 Index",
    "NWE Arab Light Cracking": "NANW0055 Index",
    "Med Abgami Cracking": "NANQ002A Index",
    "Med Sarahan Cracking": "NANQ007E Index",
    "Med CPC Cracking": "NANQ0100 Index",
    "Med Forties Cracking": "NANQ0054 Index",
    "Med Johan Svendrup Cracking": "NANQ005A Index",
    "Med Arab Light Cracking": "NANQ0066 Index",
    "SG Agbami Cracking": "NANX0039 Index",
    "SG Arab Light Cracking": "NANX0087 Index",
    "SG Cabinda Cracking": "NANX0051 Index",
    "SG Kimanis Cracking": "NANX0081 Index",
    "SG WTIM Cracking": "NANX00D5 Index",
    "SG Mars Cracking": "NANX00A5 Index",
    "SG Sarahan Cracking": "NANX00C3 Index"
}

