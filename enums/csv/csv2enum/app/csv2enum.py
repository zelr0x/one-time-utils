import argparse
import csv
import sys

from stringcase import constcase

"""
Workflow: 
    1. execute sql
    2. export results to .csv
    3. feed csv to this and optionally redirect results
    4. complete formatting manually 
       (impossible to avoid without adding 
       a formatting dictionary by the user).

uprint() tends to add one leading underscore.
If you don't need redirection (piping) - change to simple print().
"""


def remove_leading_underscore(s):
    return s if s[0] != '_' else s[1:]


def format_as_enum_attr(s):
    return remove_leading_underscore(constcase(s).replace('__', '_'))


# An example formatting function.
# Converts RUB currency symbol into similar ASCII symbol.
def changeRubSign(x):
    return x.replace('₽', 'Р')


def quote(x):
    return '"' + changeRubSign(x) + '"'


def uprint(*objects, sep=' ', end='\n', file=sys.stdout):
    enc = file.encoding
    if enc == 'UTF-8':
        print(*objects, sep=sep, end=end, file=file)
    else:
        # change 'ignore' to 'backslashreplace' if replacing on error is needed
        f = lambda obj: str(obj).encode(enc, errors='ignore').decode(enc)
        print(*map(f, objects), sep=sep, end=end, file=file)


FILE_PARAM = 'file'
parser = argparse.ArgumentParser()
parser.add_argument(FILE_PARAM, help='input csv file')
args = vars(parser.parse_args())
filename = args[FILE_PARAM]

# If utf-8, change to open(filename, encoding='utf-8')
with open(filename, 'r', encoding='utf8', errors='ignore') as csvfile:
    reader = csv.reader(csvfile, delimiter=';')
    for row in reader:
        enum_var = format_as_enum_attr(row[0])
        formatted = f'''{enum_var}({', '.join([quote(x) for x in row[1:]])}),'''
        uprint(formatted)
