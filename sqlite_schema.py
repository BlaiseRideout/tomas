#!/usr/bin/env python3

__doc__ = """
This collection of utilities compares actual SQLite tables to a
description of their schema, and can create a new database with
the new schema if it finds differences.

It does this by parsing the CREATE TABLE SQL accepted by SQLite to
create records describing the table columns and their associated
constraints.  It reads the pragma information from a SQLite database
to determine the existing schema.  Then it compares the records and
SQL describing fields, constraints, and indices to determine what
parts of the schema match and what don't.  It is designed to be used
with schema descriptions stored as lists of field descriptions and
table constraints, one string per column/field or constraint.  See
mytable_schema below for an example.  The list of strings forms a
table specification that can be joined with commas to form a table
definition.  The individual strings are very important since it is not
designed to parse complete CREATE TABLE statements; it needs the
string boundaries to determine when a column definition or table
constraint ends.  A group of table specifications is kept in a
dictionary with a key for each table as in the database_spec below."""

mytable_schema = [  # Example table specification in separate lines
    'ID INTEGER PRIMARY KEY AUTOINCREMENT',
    'Field1 TEXT NOT NULL',
    'Field2 TEXT REFERENCES AnotherTable(ID) ON DELETE CASCADE',
    'Field3 REAL',
    'Field4 DATETIME DEFAULT CURRENT_TIMESTAMP',
    'CONSTRAINT KeepItReal UNIQUE(Field3, Field4)',
]
anothertable_schema = [
    'ID INTEGER PRIMARY KEY NOT NULL',
    'Name TEXT',
    "CHECK (Name != 'Voldemort')",
]
database_spec = {'MyTable': mytable_schema, 
                 'AnotherTable': anothertable_schema}

import sys
import os
import collections
import sqlite3
import re
import argparse
import tempfile
import datetime

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

# Below are the regular expressions used in the CREATE TABLE column defintion
# and table constraint grammar for SQLite.
# (see https://www.sqlite.org/lang_createtable.html)
# These regex's cover most of the grammar, but are not 100% accurate.
# The column definition starts off with the name of a field and an optional
# data type.  Both of those names are arbitrary stings.  The regex below
# has a Python do-not-match pattern (?!...) to avoid allowing the name of the
# column to match a keyword that starts a table constraint definition that
# occurs after the column definitions.
col_def_pattern = re.compile(
    r'\b(?!(CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK)\b)(?P<name>\w+)\s+(?P<type>(?P<typename>\w+)(\s*\([+-]?\d+\s*(,\s*[+-]?\d+\s*)?\))?)?',
    re.IGNORECASE)

constraint_name_pattern = re.compile(
    r'\b(CONSTRAINT\s+(?P<cname>\w+)\s*\b)?', re.IGNORECASE)

col_pk_constraint_pattern = re.compile(
    r'\bPRIMARY\s+(?P<pk>KEY)(\s+(ASC|DESC))?\b',
    re.IGNORECASE)

col_conflict_clause_pattern = re.compile(
    r'\b(ON\s+CONFLICT\s+(?P<cresolution>\w+))?\b',
    re.IGNORECASE)

col_autoincrement_pattern = re.compile(
    r'\b(?P<autoincrement>AUTOINCREMENT)?\b',
    re.IGNORECASE)

col_notnull_constraint_pattern = re.compile(
    r'\b(?P<notnull>NOT\s+NULL)\b',
    re.IGNORECASE)

col_unique_constraint_pattern = re.compile(
    r'\b(?P<unique>UNIQUE)\b',
    re.IGNORECASE)

col_check_constraint_pattern = re.compile( # Can't handle nested parentheses
    r"\bCHECK\s*\((?P<checkexpr>[\w\s,'.+/*-]+)\)\s*\b",
    re.IGNORECASE)

col_default_constraint_pattern = re.compile(
    r"\bDEFAULT\b\s*(?P<dflt_value>[+-]?\d+(\.\d*\b)?|'[^']*'|(TRUE|FALSE|NULL|CURRENT_(DATE|TIME|TIMESTAMP)\b)|\((?P<expr>[\w\s,'.+/*-]+)\))",
    re.IGNORECASE)

col_collate_constraint_pattern = re.compile(
    r'\bCOLLATE\s+(?P<collate>\w+)\b',
    re.IGNORECASE)

fkey_constraint_pattern = re.compile(
    r'\bFOREIGN\s+KEY\s*\((?P<columns>(?P<column1>\w+)(\s*,\s*\w+)*\s*)\)',
    re.IGNORECASE)

fkey_clause_ref_pattern = re.compile(
    r'\bREFERENCES\s+(?P<table>\w+)\s*\((?P<columns>(?P<column1>\w+)(\s*,\s*\w+)*\s*)\)',
    re.IGNORECASE)

fkey_clause_conflict_pattern = re.compile(
    r'\b((ON\s+(?P<action>DELETE|UPDATE|)\s+(?P<reaction>SET\s+(NULL|DEFAULT)|CASCADE|RESTRICT|NO\s+ACTION))|MATCH\s+(?P<match>\w+))\b',
    re.IGNORECASE)

fkey_clause_defer_pattern = re.compile(
    r'\b(NOT\s+)?DEFERABLE(\s+INITIALLY\s+(DEFERRED|IMMEDIATE))?\b',
    re.IGNORECASE)

# This tree specifies sequences of regexes to try in parsing column
# definitions.  Table constraints are in a separate tree, which can be
# combined with this one.
# Each node in the tree has the form (regex, repeat, next_tree)
# The regex will be tested on the beginning of a string ignoring leading
# whitespace.  If it succeeds, the next_tree of patterns will be tried.
# If it fails, the next node is tried.
# If repeat is true in a node, after trying the next_tree, this node
# (and any successors) will be tried again until it fails or the string
# is fully parsed.
# The tree and next_tree are lists.  Each list is the children of a
# a parent node. Failing a node in the tree moves on to
# the next element of the list which is a sibling node in the tree.
column_def_patterns = [
    (col_def_pattern, False,
     [(constraint_name_pattern, True,
       [(col_pk_constraint_pattern, False, [
            (col_conflict_clause_pattern, False, [
                (col_autoincrement_pattern, False, [])
            ]),
       ]),
        (col_notnull_constraint_pattern, False, [
            (col_conflict_clause_pattern, False, []),
        ]),
        (col_unique_constraint_pattern, False, [
            (col_conflict_clause_pattern, False, []),
        ]),
        (col_check_constraint_pattern, False, []),
        (col_default_constraint_pattern, False, []),
        (col_collate_constraint_pattern, False, []),
        (fkey_clause_ref_pattern, False, [
            (fkey_clause_conflict_pattern, True, []),
            (fkey_clause_defer_pattern, False, []),
        ]),
       ]
     ),
     ]
    ),
]

table_pkey_constraint_pattern = re.compile(
    r'\bPRIMARY\s+KEY\s*\((?P<columns>(?P<column1>\w+)(\s*,\s*\w+)*\s*)\)',
    re.IGNORECASE)

table_unique_constraint_pattern = re.compile(
    r'\bUNIQUE\s*\((?P<columns>(?P<column1>\w+)(\s*,\s*\w+)*\s*)\)',
    re.IGNORECASE)

# This can't handle nested parentheses well.
table_check_constraint_pattern = re.compile( 
    r"\bCHECK\s*\((?P<expr>[\w\s<!='>,%()*/+-]+)\)", 
    re.IGNORECASE)

# The tree for table constraints below is similar to that for column
# definitions, except it will produce foreign key, primary key, uniqueness,
# and check constraint records
table_constraint_patterns = [
    (constraint_name_pattern, False,
     [(table_pkey_constraint_pattern, False,
       [(col_conflict_clause_pattern, False, [])
       ],
     ),
      (table_unique_constraint_pattern, False,
       [(col_conflict_clause_pattern, False, [])
       ],
      ),
      (table_check_constraint_pattern, False, []),
      (fkey_constraint_pattern, False,
        [(fkey_clause_ref_pattern, False, 
          [(fkey_clause_conflict_pattern, True, []),
           (fkey_clause_defer_pattern, False, []),
          ]
        ),
        ]
      ),
     ]
    ),
]

# Parsed table specifications produce records like those produced by the
# SQLite's pragma commands (table_info, foreign_key_list, index_list)
# These are defined as named tuples in Python.
# The last field in each record, spec_line, holds the specification line
# of text that generated the record (and will be None for records produced
# from SQLite pragma commands).
sqlite_column_record = collections.namedtuple(
    'Column',
    'cid, name, type, notnull, dflt_value, pk, spec_line'
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
# Make sample records with default values filled in
base_column_def_record = sqlite_column_record(None, None, None, 0, None, 0, '')
base_fkey_record = sqlite_fkey_record(
    None, None, None, None, None, 'NO ACTION', 'NO ACTION', 'NONE', '')
base_index_record = sqlite_index_record(None, None, 1, None, 0, '')

# This dictionary is used to map regex's to the pragma record that needs
# to be created when the parser discovers a match to the regex.
# We create a pragma record for CHECK constraints even though SQLite
# doesn't have a pragma command that shows records for check constraints;
# they only show up in the overall table SQL.
base_record_prototype = {
    col_def_pattern: base_column_def_record,
    col_unique_constraint_pattern: base_index_record._replace(origin='u'),
    col_pk_constraint_pattern: base_index_record._replace(origin='pk'),
    fkey_constraint_pattern: base_fkey_record,
    table_pkey_constraint_pattern: base_index_record._replace(origin='pk'),
    table_unique_constraint_pattern: base_index_record._replace(origin='u'),
    table_check_constraint_pattern: base_index_record._replace(
        origin='c', unique=0),
}

# For table columns of integer types that are marked as PRIMARY KEY,
# sqlite does not create an index pragma record for the uniqueness of
# the field.  It does create an index pragma record with origin of
# 'pk' for other types.  The function below returns true for type
# names that sqlite maps to integers.  In other words, all types whose
# 'affinity' is INTEGER.  See https://www.sqlite.org/datatype3.html
# for "Type Affinity"
def sqlite_integer_type_affinity(typename):
    return "INT" in typename.upper()

def get_sqlite_db_schema(DBfile='sample_sqlite.db'):
    "Create a database schema dictionary from an existing sqlite database"
    db_schema = {}
    with sqliteCur(DBfile=DBfile) as cur:
        cur.execute(
            "SELECT tbl_name, sql FROM SQLITE_MASTER"
            "  WHERE type = 'table' AND tbl_name NOT LIKE 'sqlite_%'")
        for row in cur.fetchall():
            db_schema[row[0]] = row[1]
    for table in db_schema:
        sql = db_schema[table]
        db_schema[table] = pragma_dict_from_pragma_records(
            pragma_records_for_table(table, DBfile), sql)
    return db_schema

def pragma_records_for_table(tablename, DBfile='sample_sqlite.db'):
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
            records.extend(extend_record_with_defaults(sqlite_index_record, row)
                           for row in cur.fetchall())
    return records

def extend_record_with_defaults(record_type, data, default=None):
    record_fields = record_type._fields
    record_len = len(record_fields)
    data_len = len(data)
    if data_len < record_len:
        return record_type(*(data + (default,) * (record_len - data_len)))
    record = record_type(*data[:len(record_fields)])
    other_fields = {}
    for i in range(len(data), len(record_fields)):
        other_fields[record_fields[i]] = default
    if other_fields:
        record = record._replace(**other_fields)
    return record

def words(spec):
    return re.findall(r'\w+', spec)

def dict_by_col_name(pragmas):
    "Dictionary keyed by lowercase version of column names defined in pragmas"
    result = {}
    for pragma in pragmas:
        if isinstance(pragma, sqlite_column_record):
            result[pragma.name.lower()] = pragma
    return result

def missing_fields(table_pragmas, actual_pragmas):
    actual_cols = dict_by_col_name(actual_pragmas)
    return [p for p in table_pragmas if 
            isinstance(p, sqlite_column_record) and 
            p.name.lower() not in actual_cols]

def deleted_fields(table_pragmas, actual_pragmas):
    return missing_fields(actual_pragmas, table_pragmas)

def common_fields(table_pragmas, actual_pragmas):
    actual_cols = dict_by_col_name(actual_pragmas)
    return [p for p in table_pragmas if 
            isinstance(p, sqlite_column_record) and 
            p.name.lower() in actual_cols]

def altered_fields(table_pragmas, actual_pragmas, ordermatters=False):
    result = []
    actual_cols = dict_by_col_name(actual_pragmas)
    for col in table_pragmas:
        if (isinstance(col, sqlite_column_record) and
            col.name.lower() in actual_cols):
            actual = actual_cols[col.name.lower()]
            diff = record_differences(
                col, actual, 
                exclude=([] if ordermatters else ['cid']) + ['spec_line'])
            if diff:
                result.append((col, ["{} for field '{}'".format(d, col.name)
                                     for d in diff]))
    return result

std_create_table_pattern = re.compile(
    r'\s*CREATE TABLE \w+\((.*)\)\s*', re.IGNORECASE)

def compare_constraints(new_table, old_table):
    """Compare a new table's definition of constraints to that of an
    existing (old) table.  The new table has SQL snippets for each
    constraint (in the spec_line field of the pragma records), while
    the old table has only the full SQL for the whole table (the
    spec_line fields aren't filled in).  The algorithm matches up the
    snippets with the whole table SQL to determine what's the same and
    what changed.  After removing the matching parts, it parses what
    remains of the old table SQL to find any deleted constraints.
    Returns new constraints and deleted constraints as lists of pragma records
    (a modify is a new + a deleted constraint).
    """
    old_sql = std_create_table_pattern.sub(
        r'\1', standardize_create_table_sql(old_table['sql']))
    new_constraints = []
    deleted_constraints = []
    for kind in ['column', 'fkey', 'index']:
        for constraint in new_table[kind]:
            if constraint.spec_line:
                new_sql = standardize_create_table_sql(constraint.spec_line)
                length = len(new_sql)
                pos = old_sql.lower().find(new_sql.lower())
                if pos == -1 and kind == 'column':
                    pos = old_sql.lower().find(
                        ' '.join(words(new_sql.lower())[0:2]))
                    if pos >= 0:
                        comma = old_sql.find(',', pos+1)
                        if comma > pos:
                            length = comma - pos
                        else:
                            length = len(old_sql) - pos
                if pos >= 0:
                    if (len(old_sql) > pos + length and
                        old_sql[pos + length] == ','):
                        length += 1
                    elif 0 < pos and old_sql[pos] == ',':
                        pos -= 1
                        length += 1
                    old_sql = old_sql[:pos] + old_sql[pos + length:]
                elif kind in ['fkey', 'index']:
                    new_constraints.append(constraint)
            elif kind in ['fkey', 'index']:
                new_constraints.append(constraint)
                
    # Parse remaining SQL for pragma records.
    # The constraints should be separated by commas, but we need to avoid
    # splitting on commas embedded in parentheses
    parentheticals = {}
    for i, m in enumerate(re.finditer(r"'[^']*'", old_sql)):
        parentheticals[i] = (m.start(), m.end(), m.group(0))
    noparens = old_sql
    for i in range(len(parentheticals) - 1, -1, -1):
        start, end, string = parentheticals[i]
        name = 'parenthetical{}'.format(i)
        noparens = noparens[0:start] + '{' + name + '}' + noparens[end:]
        parentheticals[name] = string
    parts = [part.format(**parentheticals) for part in noparens.split(',')]
    for pragma in table_pragma_records(
            parts, 'unknown_constraints', throwexceptions=False, printto=None):
        if isinstance(pragma, (sqlite_fkey_record, sqlite_index_record)):
            deleted_constraints.append(pragma)
    return new_constraints, deleted_constraints
    
def parse_database_schema(
        database_spec, throwexceptions=True, printto=sys.stderr):
    """Parse all the table specifications in a database specification.
    Return a dictionary with a key for each table name.  The key's value
    is a dictionary with the keys: column, fkey, index, and sql.  The column
    key's value is all the column pragma records for the table (in order).
    Similarly, the fkey and index values hold the foreign key and index
    pragma records.  The sql key holds the CREATE TABLE SQL command that
    is used to create the table from the specification.
    """
    db_schema  = {}
    for table in database_spec:
        pragma_records = table_pragma_records(
            database_spec[table], table, throwexceptions=throwexceptions,
            printto=printto)
        db_schema[table] = pragma_dict_from_pragma_records(
            pragma_records, 
            create_table_sql_from_spec(table, database_spec[table]))
    return db_schema

def pragma_dict_from_pragma_records(pragma_records, sql):
    return {
        'column': [p for p in pragma_records 
                   if isinstance(p, sqlite_column_record)],
        'fkey': [p for p in pragma_records 
                 if isinstance(p, sqlite_fkey_record)],
        'index': [p for p in pragma_records 
                  if isinstance(p, sqlite_index_record)],
        'sql': sql,
    }

def create_table_sql_from_spec(table, table_spec):
    return 'CREATE TABLE {}({})'.format(table, ', '.join(table_spec))

multi_whitespace = re.compile(r'\s\s+')
sql_delims = re.compile(r'\s*([,()])\s*')
temp_declaration = re.compile(r'^CREATE(\sTEMP(ORARY)?)\sTABLE',
                              re.IGNORECASE)
dbname_declaration = re.compile(r'^CREATE\sTABLE\s(\w+)\.', re.IGNORECASE)

def standardize_create_table_sql(sql):
    "Standardize create table SQL whitespace usage"
    return dbname_declaration.sub(
        'CREATE TABLE ',
        temp_declaration.sub(
            'CREATE TABLE',
            sql_delims.sub(r'\1', multi_whitespace.sub(' ', sql))))

def walk_tables(db_schema, func, verbose=0, ignore=[]):
    """Walk the tables in a datbase schema in their foreign key dependence
    order.  The tables with no foreign key dependencies will come
    first.  Tables that only only depend on other tables that have no
    foreign keys or themselves come next.  Continue until all tables
    are visited choosing only tables whose foreign key tables have
    already been visited (or are self-referetial) and that are not in
    the ignore list.  Tables in the ingnore list are assumed to exist
    for the purpose of making foreign keys.  The function should take
    2 arguments, a table name and pragma record dictionary produced by
    parse_database_schema.
    """
    visited = [tbl.lower() for tbl in ignore]
    to_visit = collections.deque(
        [tbl for tbl in db_schema.keys() if tbl.lower() not in visited])
    skipped = 0
    count = 0
    if verbose > 2:
        print('Walking {} table{} calling {}...'.format(
            len(to_visit), '' if len(to_visit) == 1 else 's', func))
    while skipped < len(to_visit):
        table = to_visit.popleft()
        pragma_dict = db_schema[table]
        fkeys = pragma_dict['fkey']
        count += 1
        if any(fkey_rec.table.lower() not in visited + [table.lower()] 
               for fkey_rec in fkeys):
            if verbose > 2:
                print(('Table {} has {} foreign key{} but not all visited yet;'
                       ' deferring.').format(
                           table, len(fkeys), '' if len(fkeys) == 1 else 's'))
            to_visit.append(table)
            skipped += 1
        else:
            func(table, pragma_dict)
            visited.append(table.lower())
            skipped = 0
    if len(to_visit):
        raise Exception(
            ('Unable to visit {} tables out of {} in {} tries.  Circular or '
             'incomplete references in tables {}').format(
                 len(to_visit), len(db_schema), count, to_visit))
    elif verbose > 2:
        print('Walk complete')
    
def table_pragma_records(
        table_spec, tablename='',
        patterns_to_try = column_def_patterns + table_constraint_patterns,
        throwexceptions=True, printto=sys.stderr):
    """Parse a table specification that is a list of strings with exactly
    one column definition or one table constraint specification per string.
    The tablename should be the name of the table in SQLite and will be
    used in naming constraints.
    The patterns_to_try is the grammar to use in parsing (in the form of a
    tree of regex tuples).
    If grammar errors are found, they can either cause exceptions, or be
    printed to a file (or be silently ignored if printto is None).
    """
    pragmas = []
    for spec in table_spec:
        pragmas.extend(
            column_def_or_constraint_to_pragma_records(
                spec, pragmas, tablename,
                # TODO: Find a better test to determine when all column def's
                # have been processed and only table constraints remain in
                # the table specification
                # patterns_to_try=(column_def_patterns 
                #                  if len(pragmas) == 0 or 
                #                  isinstance(pragmas[-1], sqlite_column_record)
                #                  else []) + table_constraint_patterns,
                patterns_to_try=column_def_patterns + table_constraint_patterns,
                throwexceptions=throwexceptions, printto=printto))
    return clean_table_pragmas(pragmas, tablename)
    
def column_def_or_constraint_to_pragma_records(
        spec, context=[], tablename='',
        patterns_to_try = column_def_patterns + table_constraint_patterns,
        throwexceptions=True, printto=sys.stderr):
    """Parse a single column definition or table constraint within a table.
    The context variable should have all the pragma records that have been
    parsed before this line, so references to columns that are defined
    earlier can be resolved.  Some pragma records in the context can be
    modified by later constraints such as PRIMARY KEY constraints.
    """
    global base_record_prototype
    # Walk the tree of patterns, find matching regex's,
    # Create corresponding records while inserting values into named fields
    # as regex's match
    # Return a list of pragma records built from the spec
    pragmas = []
    stack = []
    indices = 0
    past_indices = 0
    pk_counter = 1
    spec_line = spec
    for p in context:
        if isinstance(p, sqlite_index_record):
            past_indices += 1
    while patterns_to_try and len(spec) > 0:
        pattern, repeat, next_patterns = patterns_to_try[0]
        m = pattern.search(spec)  # Look for match at beginning of string
        if m and (m.start() == 0 or spec[0:m.start()].isspace()):
            if pattern in base_record_prototype and (
                len(pragmas) == 0 or 
                not isinstance(pragmas[-1], 
                               type(base_record_prototype[pattern]))):
                pragmas.append(
                    base_record_prototype[pattern]._replace(spec_line=spec_line))
            if len(pragmas) > 0:
                for field in pattern.groupindex:
                    if (m.group(field) is not None and
                        field in pragmas[-1]._fields):
                        kwargs = {field: m.group(field)}
                        pragmas[-1] = pragmas[-1]._replace(**kwargs)
                # Handle special case matches
                pragmas = update_pragma_record_stack_with_match(
                    context, pragmas, pattern, m, spec_line)
            if repeat:
                state = (patterns_to_try, len(spec))
                if state not in stack:
                    stack.append(state)
            patterns_to_try = next_patterns
            spec = spec[m.end():]
        else:
            patterns_to_try = patterns_to_try[1:]
        if len(patterns_to_try) == 0 and stack and stack[-1][1] > len(spec):
            patterns_to_try, l = stack.pop()
    result = []
    if len(spec) > 0 and not spec.isspace():
        msg = 'Unable to parse this part of the column definition: "{}"'.format(
            spec)
        if throwexceptions:
            raise Exception(msg)
        else:
            if printto:
                print(msg, file=printto)
    else:
        # After first pass through specifications to build pragmas,
        # clean up pragmas where multiple columns were specified
        # and fix constraint names
        for i, pragma in enumerate(pragmas):
            if isinstance(pragma, sqlite_column_record):
                result.append(pragma)
            elif isinstance(pragma, sqlite_fkey_record):
                if (isinstance(pragma.from_, str) and i+1 < len(pragmas) and
                    isinstance(pragmas[i+1], sqlite_column_record) and
                    pragma.from_ == pragmas[i+1].name):
                    if len(pragma.to) > 1:
                        msg = (('Foreign key refers to multiple columns '
                                '{} in table {} for field {}').format(
                                    pragma.to, pragma.table, pragma.from_))
                        if throwexceptions:
                            raise Exception(msg)
                        elif printto:
                            print(msg, file=printto)
                    else:
                        pragma = pragma._replace(to=pragma.to[0])
                    result.append(pragma)
                elif isinstance(pragma.from_, list):
                    if not (isinstance(pragma.to, list) and
                            len(pragma.from_) == len(pragma.to)):
                        msg = (('Foreign key constraint has mismatched number '
                                'of keys, {} vs. {} in table {}').format(
                                    pragma.from_, pragma.to, pragma.table))
                        if throwexceptions:
                            raise Exception(msg)
                        elif printto:
                            print(msg, file=printto)
                    else:
                        for i in range(len(pragma.from_)):
                            result.append(pragma._replace(
                                from_=pragma.from_[i], to=pragma.to[i]))
            elif isinstance(pragma, sqlite_index_record):
                if isinstance(pragma.seq, list):
                    for col in pragma.seq:
                        matching_col = [
                            p for p in context + pragmas[:i] if
                            isinstance(p, sqlite_column_record) and
                            col.lower() == p.name.lower()]
                        if len(matching_col) != 1:
                            msg = ('{} constraint clause mentions {} which has '
                                   '{} matches among the fields of {}').format(
                                       'UNIQUE' if pragma.origin == 'u' else
                                       'PRIMARY KEY',
                                       col, len(matching_col), tablename)
                            if throwexceptions:
                                raise Exception(msg)
                            elif printto:
                                print(msg, file=printto)
                        elif pragma.origin == 'pk': # Force PK flag to true
                            pk_field = matching_col[0]
                            pos = context.index(pk_field)
                            context[pos] = pk_field._replace(pk=pk_counter)
                            pk_counter += 1
                pragma = pragma._replace(
                    seq=past_indices + indices,
                    name='sqlite_autoindex_{}_{}'.format(
                        tablename, past_indices + indices + 1))
                result.append(pragma)
                indices += 1
    return result

def update_pragma_record_stack_with_match(
        context, pragma_record_stack, pattern, match, spec_line):
    """During parsing, the context and pragma record stack holds all the
    pragma records generated by the different clauses found so far in a
    specification. The context holds the list up to the current line in
    in the specification while pragma_record_stack holds just those pragma
    records from the current line. 
    This routine handles all the special value conversions for particular
    fields and manipulations between clauses.  The result is a revised stack
    for the current line.
    """
    top_record = pragma_record_stack.pop()
    if isinstance(top_record, sqlite_column_record):
        # Clean up values extracted via regexes
        for field in ['notnull', 'pk']:     # Coerce boolean fields to 0 or 1
            if field in pattern.groupindex:
                kwargs = {field: 1 if len(match.group(field)) > 0 else 0}
                top_record = top_record._replace(**kwargs)
        if top_record.cid is None:
            max_cid = -1
            for pragma in context + pragma_record_stack:
                if isinstance(pragma, sqlite_column_record):
                    max_cid = max(max_cid, pragma.cid)
            top_record = top_record._replace(cid=max_cid + 1)
        if 'dflt_value' in pattern.groupindex:
            val = match.group('dflt_value')
            kwargs = {'dflt_value': val}
            if val.upper() == 'NULL':
                kwargs['dflt_value'] = None
            elif val[0] == '(' and val[-1] == ')':
                kwargs['dflt_value'] = val[1:-1]
            if kwargs['dflt_value'] != top_record.dflt_value:
                top_record = top_record._replace(**kwargs)
        elif 'table' in pattern.groupindex and 'columns' in pattern.groupindex:
            if len(pragma_record_stack) == 0 or not isinstance(
                    pragma_record_stack[-1], sqlite_fkey_record):
                pragma_record_stack.append(
                    base_fkey_record._replace(
                        table=match.group('table'),
                        from_=top_record.name,
                        to=words(match.group('columns')),
                        spec_line=spec_line))
        elif (('match' in pattern.groupindex or
               ('action' in pattern.groupindex and 
                'reaction' in pattern.groupindex)
               and len(pragma_record_stack) > 0 and 
               isinstance(pragma_record_stack[-1], sqlite_fkey_record))):
            if 'action' in pattern.groupindex and 'reaction' in pattern.groupindex:
                reaction = ' '.join([x.upper() 
                                     for x in words(match.group('reaction'))])
                if match.group('action').upper() == 'DELETE':
                    pragma_record_stack[-1] = pragma_record_stack[-1]._replace(
                        on_delete=reaction)
                else:
                    pragma_record_stack[-1] = pragma_record_stack[-1]._replace(
                        on_update=reaction)
            elif 'match' in pattern.groupindex:
                    pragma_record_stack[-1] = pragma_record_stack[-1]._replace(
                        match=match.group('match'))

    elif isinstance(top_record, sqlite_fkey_record):
        if 'columns' in pattern.groupindex and 'column1' in pattern.groupindex:
            clean_cols = words(match.group('columns'))
            if pattern == fkey_constraint_pattern:
                top_record = top_record._replace(from_=clean_cols)
            elif pattern == fkey_clause_ref_pattern:
                top_record = top_record._replace(to=clean_cols)
        elif 'action' in pattern.groupindex and 'reaction' in pattern.groupindex:
            reaction = ' '.join([x.upper() 
                                 for x in words(match.group('reaction'))])
            if match.group('action').upper() == 'DELETE':
                top_record = top_record._replace(on_delete=reaction)
            else:
                top_record = top_record._replace(on_update=reaction)
    elif isinstance(top_record, sqlite_index_record):
        if 'columns' in pattern.groupindex and 'column1' in pattern.groupindex:
            clean_cols = words(match.group('columns'))
            top_record = top_record._replace(seq=clean_cols)
        elif (pattern is col_unique_constraint_pattern and 
              len(pragma_record_stack) > 0 and
              isinstance(pragma_record_stack[-1], sqlite_column_record)):
            top_record = top_record._replace(seq=[pragma_record_stack[-1].name])
        elif (pattern is col_pk_constraint_pattern and
              isinstance(top_record, sqlite_index_record) and
              top_record.origin == 'pk' and
              len(pragma_record_stack) > 0 and
              isinstance(pragma_record_stack[-1], sqlite_column_record) and
              sqlite_integer_type_affinity(pragma_record_stack[-1].type)):
            top_record = None
    if top_record:
        pragma_record_stack.append(top_record)
    return pragma_record_stack

def record_differences(record1, record2, include=None, exclude=None,
                       exactfields=False):
    """Compare records by comparing some or all fields, ignoring case
    of fields with string values. Ignore missing fields if exactfields is
    false. Record types must be the same, otherwise the string 'record types
    differ is returned'
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
            str1 = isinstance(v1, str)
            str2 = isinstance(v2, str)
            if ((v1.lower() != v2.lower()) if (str1 and str2) else v1 != v2):
                result.append("Field '{}' differs".format(field))
    return result

def clean_table_pragmas(pragmas, tablename=''):
    "Adjust table pragmas after all columns and constraints are defined"
    return pragmas

def pprint_table_pragmas(pragma_dict, indent='', tablename=''):
    for kind in ['Column', 'FKey', 'Index']:
        print(indent, '{} pragmas:'.format(kind))
        for pragma in pragma_dict[kind.lower()]:
            print(indent, '  {', end='')
            fields = pragma._fields
            for field in fields:
                if field == 'spec_line':
                    print('\n{}    {}: {!r}, '.format(
                        indent, field, pragma[fields.index(field)]),
                          end='}\n')
                else:
                    print('{}: {!r}, '.format(
                        field, pragma[fields.index(field)]),
                          end='')

def compare_db_schema(new_schema, old_schema, verbose=0, ordermatters=False):
    """Compare 2 database schema's table by table.  Returns a dictionary
    with the following key: value pairs - 
    same: list of tables that are the same in both
    new_tables: list of tables in the new_schema that don't appear in the old
    dropped_tables: list of tables in the old but not in the new_schema
    add_fields: list of tables where only new fields are added
    different: list of tables with more complex differences or dropped fields
    """
    result = {
        'same': [],
        'new_tables': [],
        'dropped_tables': [],
        'add_fields': [],
        'different': [],
    }
    sep = '=' * 16
    for table in new_schema:
        if table not in old_schema:
            result['new_tables'].append(table)
        else:
            if verbose > 1:
                print(sep, 'Comparing schemas for table', table, sep)
            kind = compare_table_schema(new_schema[table], old_schema[table],
                                        ordermatters=ordermatters,
                                        verbose=verbose)
            if kind == 'add_fields':
                result['add_fields'].append(table)
            elif kind == 'same':
                result['same'].append(table)
            else:
                result['different'].append(table)
    for table in old_schema:
        if table not in new_schema:
            result['dropped_tables'].append(table)
    return result

def compare_table_schema(new_table, old_table, ordermatters=False, verbose=0):
    """Compare 2 tables described by their pragma dictionaries.
    Return 'same' if they are same, 'add_fields' if the new table has just
    added some fields to the table, or 'differ' if they differ in some
    other way.
    """
    if new_table['sql'] and old_table['sql']:
        new = standardize_create_table_sql(new_table['sql']).lower()
        old = standardize_create_table_sql(old_table['sql']).lower()
        if new == old:
            if verbose > 1:
                print('SQL for tables is equivalent')
            return 'same'
        if verbose > 1:
            print('SQL for tables differs')
            if verbose > 2:
                print('  SQL for new:\n    ', new_table['sql'],
                      '\n  SQL for old:\n    ', old_table['sql'])
    elif verbose > 1:
        print('SQL for one or both tables is missing')
        
    fields_to_add = missing_fields(new_table['column'], old_table['column'])
    deleted = deleted_fields(new_table['column'], old_table['column'])
    altered = altered_fields(new_table['column'], old_table['column'],
                             ordermatters)
    constraints_to_add, constraints_deleted = compare_constraints(
        new_table, old_table)
    changed = len(fields_to_add + deleted + altered + 
                  constraints_to_add + constraints_deleted) > 0
    if changed and verbose > 1:
        print('Pragma records have {}changed'.format('' if changed else 'not '))
        for name, value in [('Fields to add', fields_to_add),
                            ('Deleted fields', deleted),
                            ('Altered fields', altered),
                            ('Added constraints', constraints_to_add),
                            ('Deleted constraints', constraints_deleted)]:
            print('  {}:'.format(name))
            for r in value:
                print('   ', r)
    return 'same' if not changed else (
        'add_fields' if len(fields_to_add) > 0 and
        len(deleted + altered + constraints_to_add + constraints_deleted) == 0
        else 'differ')

def backup_db_and_migrate(
        new_db_schema, old_db_schema, dbfile, backup_dir, backup_prefix, 
        preserve_unspecified=True, verbose=0):
    if not os.path.isdir(backup_dir):
        print('Creating directory for backup files: {}'.format(backup_dir))
        os.mkdir(backup_dir)
    filename, ext = os.path.splitext(os.path.basename(dbfile))
    newdbfile = tempfile.NamedTemporaryFile(delete=False)
    newdbfile.close()
    if verbose > 1:
        print('Temporary database file to be created in {}'.format(
            newdbfile.name))
    try:
        with sqliteCur(DBfile=newdbfile.name) as cur:
            old_name = "Old"
            cur.execute("ATTACH DATABASE '{}' AS {}".format(dbfile, old_name))
            done = []
            def copy_table(table, pd):
                in_new = table in new_db_schema
                in_old = table in old_db_schema
                if table in done:
                    return
                if verbose > 1:
                    print('{} {} table ...'.format(
                        'Creating new' if in_new else 'Preserving', table),
                          end='')
                cur.execute(pd['sql'])
                if verbose > 1:
                    print(' Done.')
                fields = [c.name for c in (
                    common_fields(pd['column'], old_db_schema[table]['column'])
                    if in_new and in_old else pd['column'])]
                if in_old:
                    if verbose > 1:
                        print('Copying... ', end='')
                    cur.execute(
                        'INSERT INTO main.{0} ({1}) SELECT {1} FROM {2}.{0}'
                        .format(table, ','.join(fields), old_name))
                    if verbose > 1:
                        print('Copied {} row{} into {}'.format(
                            cur.rowcount, '' if cur.rowcount == 1 else 's',
                            table))
                done.append(table)
            walk_tables(new_db_schema, copy_table, verbose=verbose)
            if preserve_unspecified:
                walk_tables(old_db_schema, copy_table, verbose=verbose,
                            ignore=done)
        if verbose > 1:
            print('Database successfully migrated to {}'.format(newdbfile.name))
        dbfile_stat = os.stat(dbfile)
        backupfile = os.path.join(
            backup_dir,
            datetime.datetime.now().strftime(backup_prefix) +
            os.path.basename(dbfile))
        os.replace(dbfile, backupfile)
        os.replace(newdbfile.name, dbfile)
        os.chmod(dbfile, dbfile_stat.st_mode)
        if verbose > 0:
            print(('Existing database backed up to {} and migrated database '
                   'now in {}').format(backupfile, dbfile))
        return True
    except sqlite3.DatabaseError as e:
        print('Error during database migration to {}:'.format(newdbfile.name),
              e)
        return False

def upgrade_database(new_db_schema, old_db_schema, dbfile, verbose=0):
    """Try upgrading database to create new tables and adding fields.
    This method ignores any tables with more complex changes.
    Return True for success, false otherwise."""
    try:
        with sqliteCur(DBfile=dbfile) as cur:
            def alter_table(table, pd):
                if table in old_db_schema:
                    new_fields = missing_fields(
                        pd['column'], old_db_schema[table]['column'])
                    if new_fields and verbose > 1:
                        print('Altering {} table'.format(table))
                    for field in new_fields:
                        if verbose > 2:
                            print('Adding column {}'.format(field.name))
                        cur.execute('ALTER TABLE {} ADD COLUMN {}'.format(
                            table, field.spec_line))
                else:
                    if verbose > 1:
                        print('Creating new {} table'.format(table))
                    cur.execute(pd['sql'])
            walk_tables(new_db_schema, alter_table, verbose=verbose)
        return True
    except sqlite3.DatabaseError as e:
        print('Error while trying to add column or create table in {}:'.format(
            dbfile), e)
        return False

def create_database(db_schema, dbfile, verbose=0):
    "Create a database with the given specification."
    if os.path.exists(dbfile):
        raise Exception("Will not overwrite existing file, {}".format(dbfile))
    try:
        with sqliteCur(DBfile=dbfile) as cur:
            def create_table(table, pd):
                if verbose > 1:
                    print('Creating new {} table'.format(table))
                cur.execute(pd['sql'])
            walk_tables(db_schema, create_table, verbose=verbose)
        if verbose > 0:
            print('Created empty database in {}'.format(dbfile))
        return True
    except sqlite3.DatabaseError as e:
        print('Error while trying to create table in database {}:'.format(
            dbfile), e)
        return False

def interpret_response(
        response, 
        response_dict={True: ['y', 'yes', '1'], False: ['n', 'no', '0']}, 
        default=None):
    if isinstance(response, str):
        response = response.lower()
    for outcome in response_dict:
        if response in response_dict[outcome]:
            return outcome
    return default
    
def compare_and_prompt_to_upgrade_database(
        desired_db_schema, actual_db_schema, dbfile,
        ordermatters=False, prompt_prefix='SCHEMA CHANGE: ',
        force_response=None, backup_dir='./backups',
        response_dict={True: ['y', 'yes', '1'], False: ['n', 'no', '0']}, 
        backup_prefix="%Y-%m-%d-%H-%M-%S-", preserve_unspecified=True,
        verbose=0):
    """Compare an actual SQLite database schema to a desired one and
    prompt user to upgrade if differences are found.  If the
    differences are simple, new tables or new fields without new
    constraints, it will attempt to alter the existing database.  If
    that fails or the differences are more complex, it will backup the
    existing database and migrate the data into a new database that
    will be placed in the file for the current database.
    If ordermatters is True, reordering columns in a database table
    is considered a change that requires migration.
    The prompt prefix will come before each yes/no question about upgrades.
    By setting force_response to 'y' or 'n', all user prompts will
    be answered with the given response without prompting.
    The backup_dir will be created to hold backup databases, if necessary.
    The backup_prefix will be filled in via datetime.strftime with the
    current local time and placed before the database file name in naming
    any backup files.
    If preserve_unspecified is True, tables in the actual database that
    are not in the desired database schema will be migrated.  Tables
    are only dropped if migration is performed and preserve_unspecifed is
    false (not if tables are simply altered in the existing database).
    With higher verbosity levels, more debugging information is printed.
    """
    if force_response and interpret_response(
            force_response, response_dict) is None:
        raise Exception("Invalid forced response provided: {}".format(
            force_response))

    delta = compare_db_schema(desired_db_schema, actual_db_schema, 
                              verbose=verbose, ordermatters=ordermatters)
    if verbose > 0:
        print('Tables whose schema matches the one in {}:'.format(dbfile))
        for table in delta['same']:
            print(' ', table)
        print('New tables:')
        for table in delta['new_tables']:
            print(' ', table)
        print('Dropped tables:')
        for table in delta['dropped_tables']:
            print(' ', table)
        print('Tables with only added fields:')
        for table in delta['add_fields']:
            print(' ', table)
        print('Tables with other differences:')
        for table in delta['different']:
            print(' ', table)
    total_changed_tables = len(
        delta['new_tables'] + delta['add_fields'] + delta['different'] +
        ([] if preserve_unspecified else delta['dropped_tables']))
    migrate_only_changes = len(
        delta['different'] + 
        ([] if preserve_unspecified else delta['dropped_tables']))

    # If there are no changes or the forced response is no upgrade,
    # then no more work needs to be done
    if (total_changed_tables == 0 or
        interpret_response(force_response, response_dict) is False):
        return True
    
    # Here, there are some schema changes needed.  Try altering the existing
    # database if conditions are right
    if migrate_only_changes == 0:
        resp = interpret_response(force_response, response_dict)
        while resp is None:
            resp = interpret_response(
                input('{}Would you like try altering these tables: {}? [y/n] '
                      .format(prompt_prefix, ', '.join(delta['new_tables'] +
                                                       delta['add_fields']))),
                response_dict)
            if resp is None:
                print('Unrecognized response.  Please answer yes or no.')
        if resp and upgrade_database(
                desired_db_schema, actual_db_schema, dbfile, verbose=verbose):
            if verbose > 0:
                if delta['new_tables']:
                    print('Created tables: {}'.format(
                        ', '.join(delta['new_tables'])))
                if delta['add_fields']:
                    print('Added fields to: {}'.format(
                        ', '.join(delta['add_fields'])))
            total_changed_tables -= len(
                    delta['new_tables'] + delta['add_fields'])
        else:
            if resp and verbose > 0:
                print('Altering database failed')
                
    # Here, we check again if there are remaining schema changes.  If so,
    # try migrating the database, backing up the existing one if it works
    if total_changed_tables + migrate_only_changes > 0:
        resp = interpret_response(force_response, response_dict)
        dbexists = os.path.exists(dbfile)
        while resp is None:
            resp = interpret_response(
                input('{}Would you like try {} the database? [y/n] '.format(
                    prompt_prefix, 'migrating' if dbexists else 'creating')),
                response_dict)
            if resp is None:
                print('Unrecognized response.  Please answer yes or no.')
                
        # If the migration is not approved, then no more work is needed
        if resp is False:
            return True
        
        # Here, changes are needed and approved.
        # If there is an existing database, we migrate into a database in
        # a temporary file and swap the files if it succeeds
        if dbexists:
            if backup_db_and_migrate(
                    desired_db_schema, actual_db_schema, dbfile, backup_dir,
                    backup_prefix, preserve_unspecified, verbose=verbose):
                
                # Backup and migration succeed, print something if no other
                # verbose messages were already printed
                if verbose == 0 and (
                        force_response is None or 
                        interpret_response(force_response, response_dict)):
                    print(('Backed up {} to {} and replaced with '
                           'migrated version').format(dbfile, backup_dir))
                return True    
            else:
                print('Backup and migration of database {} failed'.format(
                    dbfile))
                return False

        # Here no database existed, so we create one
        else:
            if create_database(desired_db_schema, dbfile, verbose=verbose):
                if verbose == 0:
                    print('Created empty database in {}'.format(dbfile))
                return True
            else:
                return False
            
    # Here no work remains to be done since altering tables reduced the
    # number of tables that need work to 0
    else:
        return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'database', nargs='?',
        help='SQLite3 database file to check.  '
        'If none provided, only parse the schema specification.')
    parser.add_argument(
        '-s', '--schema', type=argparse.FileType('r'),
        help='File containing schema specification in Python dictionary '
        'format.  Each key in the dictionary is a table name and its value '
        'is a list of strings with one string per column definition or table '
        'constraint.  If none specified, it uses the built-in MyTable '
        'specication.')
    parser.add_argument(
        '-o', '--order-matters', default=False, action='store_true',
        help='Pay attention to column ordering in tables when comparing.')
    parser.add_argument(
        '-u', '--upgrade', default=False, action='store_true',
        help='Enable upgrade of database instead of printing differences')
    parser.add_argument(
        '-f', '--force-response', choices=['y', 'n'],
        help='Force a yes or no response to all questions instead of '
        'prompting whether to upgrade')
    parser.add_argument(
        '-F', '--force-migration', default=False, action='store_true',
        help='Force a database migration without prompting even if schema '
        'differences are not detectable.  Requires --upgrade option.')
    parser.add_argument(
        '-b', '--backup-dir', default='./backups',
        help='Directory to hold backups of databases before upgrading.  '
        'This will be created if needed and non-existent.')
    parser.add_argument(
        '-p', '--backup-file-prefix', default="%Y-%m-%d-%H-%M-%S-",
        help='Prefix of backup file name.  Percent values are filled in '
        "using Python's datetime.strftime on the current local time.  "
        "The prefix goes before the input database's filename")
    parser.add_argument(
        '-d', '--drop-unused-tables', default=False, action='store_true',
        help='Drop any tables not mentioned in the schema when upgrading.')
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help='Add verbose comments.')

    args = parser.parse_args()

    if args.force_migration and not args.upgrade:
        print('The -F/--force-migration option can only be used with '
              'the -u/--upgrade option.')
        parser.print_help()
        sys.exit(-1)
        
    if args.schema:
        try:
            print('Reading', args.schema.name, '...', end='', flush=True)
            database_spec = eval(args.schema.read())
        except Exception as e:
            print('Unable to parse database schema in {}. Error = {}'
                  .format(args.schema, e))
            sys.exit(-1)
        print()

    linesep = '=' * 78
    tablesep = '--<' + '=' * 15 + '>--'
    if args.verbose > 0:
        print(linesep)
        print('Database specification:')
        for table in database_spec:
            print('  Table specification ', tablesep, table, tablesep)
            for spec in database_spec[table]:
                print('   ', spec)
        print(linesep)

    desired_db_schema = parse_database_schema(database_spec)

    if args.verbose > 2:
        print('Parsed pragma records for database:')
        walk_tables(desired_db_schema,
                    lambda table, pragma_dict:
                    (print('  New table', tablesep, table, tablesep),
                     pprint_table_pragmas(pragma_dict, indent='    ')),
                    verbose=args.verbose)
        print(linesep)
                
    if args.database:
        if not os.path.exists(args.database):
            print("Database file, {}, doesn't exist".format(args.database))
            actual_db_schema = {}
        else:
            actual_db_schema = get_sqlite_db_schema(args.database)

        if args.verbose > 2:
            print('Pragma records for current database in {}:'
                  .format(args.database))
            walk_tables(actual_db_schema,
                        lambda table, pragma_dict:
                        (print('  Existing table', tablesep, table, tablesep),
                         pprint_table_pragmas(pragma_dict, indent='    ')),
                        verbose=args.verbose)
            print(linesep)
            
    if desired_db_schema and args.database:
        if not os.path.exists(args.database):
            if not create_database(desired_db_schema, args.database,
                                   verbose=args.verbose):
                sys.exit(-1)
        elif args.force_migration:
            if not backup_db_and_migrate(
                    desired_db_schema, actual_db_schema, args.database,
                    args.backup_dir, args.backup_file_prefix,
                    preserve_unspecified=not args.drop_unused_tables,
                    verbose=args.verbose):
                sys.exit(-1)
        else:
            if args.force_response is None and not args.upgrade:
                args.force_response = 'n'
            if not compare_and_prompt_to_upgrade_database(
                    desired_db_schema, actual_db_schema, args.database,
                    ordermatters=args.order_matters,
                    prompt_prefix='SCHEMA CHANGE: ', 
                    force_response=args.force_response,
                    backup_dir=args.backup_dir, 
                    backup_prefix=args.backup_file_prefix,
                    preserve_unspecified=not args.drop_unused_tables,
                    verbose=args.verbose):
                sys.exit(-1)
