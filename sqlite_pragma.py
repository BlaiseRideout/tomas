#!/usr/bin/env python3

__doc__ = """
This is a collection of utilities for working with SQLite pragma
records.  It creates named tuples for many of the pragma records that
can be queried from SQLite.
"""

import sys, os, collections, sqlite3, argparse

class sqliteCur():
    con = None
    cur = None
    def __init__(self, DBfile="sample_sqlite.db", autoCommit=True):
        self.__DBfile = DBfile
        self.__autoCommit = autoCommit
    def __enter__(self):
        self.con = sqlite3.connect(self.__DBfile)
        self.cur = self.con.cursor()
        self.cur.execute("PRAGMA foreign_keys = 1;")
        return self.cur
    def __exit__(self, type, value, traceback):
        if self.cur and self.con and not value:
            self.cur.close()
            if self.__autoCommit:
               self.con.commit()
            self.con.close()

        return False
     
# The following namedtuples match the records for SQLite's pragma
# commands (table_info, foreign_key_list, index_list) but extended a
# bit for schema comparisons.  The last field in each record,
# spec_line, is used for the specification line of text that generated
# the record (which is entered by sqlite_schema).
# We also add a 'formerly' filed to column pragma records to store
# former names for the column

sqlite_column_record = collections.namedtuple(
    'Column',
    'cid, name, type, notnull, dflt_value, pk, formerly, spec_line'
)
sqlite_fkey_record = collections.namedtuple(
    'Foreign_Key',
    # SQLite uses the field name 'from' but that's a Python keyword
    'id, seq, table, from_, to, on_update, on_delete, match, spec_line'
)
sqlite_index_record = collections.namedtuple(
    'Index',
    'seq, name, unique, origin, partial, spec_line'
)
sqlite_index_info_record = collections.namedtuple(
    'Index_Info',
    'idx_rank, tbl_rank, cname'
)
# Make sample records with default values filled in
base_column_def_record = sqlite_column_record(
    None, None, None, 0, None, 0, [], '')
base_fkey_record = sqlite_fkey_record(
    None, None, None, None, None, 'NO ACTION', 'NO ACTION', 'NONE', '')
base_index_record = sqlite_index_record(None, None, 1, None, 0, '')

def get_sqlite_db_schema(DBfile='sample_sqlite.db'):
    "Create a database schema dictionary from an existing sqlite database"
    db_schema = {}
    master_info = collections.defaultdict(
       lambda: collections.defaultdict(lambda: dict()))
    with sqliteCur(DBfile=DBfile) as cur:
        cur.execute(
            "SELECT tbl_name, name, type, sql FROM SQLITE_MASTER"
            "  WHERE type in ('table', 'index') AND "
            "        tbl_name NOT LIKE 'sqlite_%' AND sql NOT NULL")
        for tbl_name, name, type_, sql in cur.fetchall():
            if type_ == 'table':
               master_info[tbl_name][type_] = sql
            else:
               master_info[tbl_name][type_][name] = sql
    for table in master_info:
        db_schema[table] = pragma_dict_from_pragma_records(
            pragma_records_for_table(table, master_info, DBfile), 
            master_info[table]['table'], master_info[table]['index'])
    return db_schema

def pragma_records_for_table(tablename, master_info, DBfile='sample_sqlite.db'):
    "Get pragma records for a particular table in a SQLite database"
    records = []
    with sqliteCur(DBfile=DBfile) as cur:
        cur.execute("PRAGMA table_info('{0}')".format(tablename))
        records = [extend_record_with_defaults(sqlite_column_record, row)
                   for row in cur.fetchall()]
        if records:
            cur.execute("PRAGMA foreign_key_list('{0}')".format(tablename))
            records.extend(extend_record_with_defaults(sqlite_fkey_record, row)
                           for row in cur.fetchall())
            cur.execute("PRAGMA index_list('{0}')".format(tablename))
            records.extend(
               extend_record_with_defaults(
                  sqlite_index_record, row, 
                  spec_line=(master_info[tablename]['index'][row[1]] 
                             if row[3] == 'c' else ''))
               for row in cur.fetchall())
            indices = [p.name for p in records 
                       if isinstance(p, sqlite_index_record) and
                       p.origin == 'c']
            for ind in indices:
                cur.execute("PRAGMA index_info('{0}')".format(ind))
                records.extend(extend_record_with_defaults(
                    sqlite_index_info_record, row)
                               for row in cur.fetchall())
    return records

def extend_record_with_defaults(record_type, data, default=None, **kwargs):
    record_fields = record_type._fields
    return record_type(*(data[i] if i < len(data) else 
                         kwargs.get(record_fields[i], default)
                         for i in range(len(record_fields))))

def pragma_dict_from_pragma_records(pragma_records, table_sql, index_sqls):
    return {
        'column': [p for p in pragma_records 
                   if isinstance(p, sqlite_column_record)],
        'fkey': [p for p in pragma_records 
                 if isinstance(p, sqlite_fkey_record)],
        'index': [p for p in pragma_records 
                  if isinstance(p, sqlite_index_record)],
        'index_info': [p for p in pragma_records 
                       if isinstance(p, sqlite_index_info_record)],
        'table_sql': table_sql,  # 1 SQL string for CREATE TABLE
        'index_sqls': index_sqls, # Map index names to CREATE INDEX strings
    }

def dict_by_col_name(pragma_records, lower=True):
    """Retun a dictionary of SQLite column pragma records keyed by their
    column names.  Use the lowercase version of the name if lower is true.
    """
    return dict([(pragma.name.lower() if lower else pragma.name, pragma)
                 for pragma in pragma_records
                 if isinstance(pragma, sqlite_column_record)])

def record_differences(record1, record2, include=None, exclude=None,
                       exactfields=False, rename={}):
    """Compare records by comparing some or all fields, ignoring case
    of fields with string values. Ignore missing fields if exactfields is
    false. Record types must be the same, otherwise the string 'record types
    differ is returned'.  The rename parameter contains a dictionary mapping
    values for the 'name' field of record2 to those of record1.
    Returns a list of strings describing field differences.  The list is
    empty if no differences were found.
    """
    if not type(record1) == type(record2):
        return ['Record types differ']
    result = []
    fields = set(include if include else record1._fields)
    if exactfields:
        fields |= set(record2._fields)
    if exclude:
        fields -= set(exclude)
    for field in fields:
        in1 = field in record1._fields
        in2 = field in record2._fields
        if not (in1 and in2):
            if exactfields:
                if in1:
                    result.append("Field '{}' in first but not second".format(
                        field))
                else:
                    result.append("Field '{}' in second but not first".format(
                        field))
        else:
            v1 = getattr(record1, field)
            v2 = getattr(record2, field)
            if field == 'name':
               v2 = rename.get(v2, v2)
            str1 = isinstance(v1, str)
            str2 = isinstance(v2, str)
            if ((v1.lower() != v2.lower()) if (str1 and str2) else v1 != v2):
                result.append("Field '{}' differs".format(field))
    return result

def pprint_table_pragmas(pragma_dict, indent='', tablename=''):
    print('{}Table SQL for {}: "{}"'.format(
       indent, tablename, pragma_dict['table_sql']))
    for kind in ['Column', 'FKey', 'Index']:
        print(indent, '{} pragmas:{}'.format(
           kind, 'NONE' if len(pragma_dict[kind.lower()]) == 0 else ''))
        for pragma in pragma_dict[kind.lower()]:
            print(indent, '  {', end='')
            for i, field in enumerate(pragma._fields):
                if field == 'spec_line':
                    print('\n{}    {}: {!r}, '.format(indent, field, pragma[i]),
                          end='}\n')
                else:
                    print('{}: {!r}, '.format(field, pragma[i]), end='')
    if pragma_dict['index_sqls']:
       print('{}Index SQLs for {}:'.format(indent, tablename))
       for index_name in pragma_dict['index_sqls']:
          print('{}  {} -> {}'.format(indent, index_name,
                                      pragma_dict['index_sqls'][index_name]))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'database', nargs='+',
        help='SQLite3 database file to check.')
    parser.add_argument(
        '-t', '--tables', nargs='*', default=[],
        help='Tables to display.  If none provided, all are printed.')

    args = parser.parse_args()

    linesep = '=' * 78
    tablesep = '--<' + '=' * 15 + '>--'

    for dbfile in args.database:
        if not os.path.exists(dbfile):
            print("Database file, {}, doesn't exist".format(dbfile))
        else:
            print(linesep)
            print('Pragma records for database in {}:'.format(dbfile))
            db_schema = get_sqlite_db_schema(dbfile)
            for table in db_schema:
               if args.tables == [] or table.lower() in [
                     t.lower() for t in args.tables]:
                  print(tablesep, table, tablesep)
                  pprint_table_pragmas(db_schema[table], tablename=table)
            print(linesep)
