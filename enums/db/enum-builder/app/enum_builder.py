import argparse
from enum import Enum
from getpass import getpass
import logging
from typing import Dict, Any

from stringcase import constcase
import sqlalchemy as sa
import toml


logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)


class Toml:
    """Contains constants mirroring .toml
     configuration file contents."""
    class Header:
        """Contains names of Table Headers of .toml
        configuration file."""
        DATABASE = 'database'
        QUERY = 'query'

    DBMS = 'dbms'
    ADDRESS = 'address'
    USER = 'user'
    PASSWORD = 'password'
    DB = 'db'
    COLUMNS = 'columns'
    EXCLUDE = 'exclude'
    EXCLUDE_BY = 'exclude_by'
    TABLE = 'table'
    REMOVE_PREFIX = 'remove_prefix'
    REMOVE_SUFFIX = 'remove_suffix'
    ATTR = 'attr_column'


class Dbms(Enum):
    """Represents DBMS names and according URI schemas."""
    POSTGRES = 'postgresql',
    MSSQL = 'mssql+pyodbc'

    def scheme(self):
        return self.value[0]


def get_dbms(dbms: str) -> Dbms:
    """Resolves uniform DBMS name for DBMS alias."""
    dbms_dict = {
        ('sql-server', 'ms', 'mssql', 'ms-sql',
         'ms-sql-server', 'sqlserver', 'sql_server'): Dbms.MSSQL,
        ('postgres', 'postgresql', 'psql',
         'pg', 'pgsql', 'posgres'): Dbms.POSTGRES,
    }
    for aliases, uniform_name in dbms_dict.items():
        if dbms in aliases:
            return uniform_name
    raise KeyError(f'DBMS {dbms} not found')


def get_uri(db_params: Dict[str, str]) -> str:
    """Creates DB URI for specified parameters."""
    def format_uri(scheme: str) -> str:
        auth = f'''{db_params[Toml.USER]}:{db_params[Toml.PASSWORD]}'''
        return f'''{scheme}://{auth}@{db_params[Toml.ADDRESS]}/{db_params[Toml.DB]}'''

    try:
        uniform_dbms = get_dbms(db_params[Toml.DBMS])
        return format_uri(uniform_dbms.scheme())
    except KeyError as err:
        LOG.exception(err)
        exit()


def get_engine(db_params: Dict[str, str]) -> sa.engine:
    """Creates SQLAlchemy engine for a specified database."""
    db_uri = get_uri(db_params)
    return sa.create_engine(db_uri)


def query(engine: sa.engine, query_params: Dict[str, Any]) -> sa.engine.ResultProxy:
    """Queries a DB with SELECT... according to parameters
    specified in the configuration file."""
    with engine.connect() as con:
        attr_col = [query_params[Toml.ATTR]]
        cols = [sa.Column(x) for x in attr_col + query_params[Toml.COLUMNS]]
        table = query_params[Toml.TABLE]
        s = sa.select(cols)
        s.append_from(sa.text(table))
        s.append_whereclause(sa.text(query_params[Toml.EXCLUDE_BY] + ' not in :exclude')
                             .bindparams(sa.bindparam('exclude', expanding=True)))
        return con.execute(s, {
            'exclude': query_params[Toml.EXCLUDE]
        })


def print_formatted(rows: sa.engine.ResultProxy, query_params: Dict[str, str]) -> None:
    """Prints specified rows as Java enums."""

    def format_attr(attr: str) -> str:
        """Formats enum attribute name."""
        prefix = query_params[Toml.REMOVE_PREFIX]
        suffix = query_params[Toml.REMOVE_SUFFIX]
        prefix_len = len(prefix)
        suffix_len = len(suffix)
        stripped = attr.strip()
        if stripped[:prefix_len] == prefix:
            stripped = stripped[prefix_len:]
        if stripped[-suffix_len:] == suffix:
            stripped = stripped[:-suffix_len]
        return constcase(stripped).replace('__', '_')

    def enum_format(row: sa.engine.RowProxy) -> str:
        """Formats row as Java enum attribute with constructor."""
        return f'''{format_attr(row[0])}({','.join('"' + x + '"' for x in row[1:])})'''

    print(*[enum_format(row) for row in rows], sep=',\n', end=';')


def ask_password(db_params: Dict[str, str]) -> None:
    """Prompts user for password and saves it into db_params."""
    db_params[Toml.PASSWORD] = getpass('DB Password: ')


if __name__ == '__main__':
    DEFAULT_DB_CONFIG_FILE = 'db.toml'

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        help='.toml file with default DB configuration. '
                             'db.toml is the default file name',
                        default=DEFAULT_DB_CONFIG_FILE)
    args = vars(parser.parse_args())

    filename = args['config']
    try:
        config = toml.load(filename)
        db_params = config[Toml.Header.DATABASE]
        query_params = config[Toml.Header.QUERY]
    except EnvironmentError as err:
        LOG.exception(err)
        exit()
    else:
        queried = False
        attempts_left = 3
        while not queried:
            try:
                ask_password(db_params)
                engine = get_engine(db_params)
                rows = query(engine, query_params)
                print_formatted(rows, query_params)
                queried = True
            except sa.exc.OperationalError:
                attempts_left -= 1
                if attempts_left > 0:
                    print('Wrong password! Attempts left:', attempts_left)
                else:
                    print('Better luck next time!')
                    exit()
