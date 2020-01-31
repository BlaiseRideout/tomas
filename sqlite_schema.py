#!/usr/bin/env python3

__doc__ = """
This tool compares actual SQLite tables to a description of their
schema, and can create a new database with the new schema if it finds
differences.

sqlite_schema.py does this by parsing a version of the CREATE TABLE
SQL as described in sqlite_parser.py that create records describing
the table columns and their associated constraints.  The description
language is an enahanced version of the SQLite version with extensions
for renamed columns and associated indices.  The tool also reads the
pragma information from a SQLite database using the sqlite_pragma.py
utitilies to determine its schema.  Then it compares the pragma
records and SQL describing fields, constraints, and indices to
determine what parts of the schema match and what don't.

The schema descriptions are stored as lists of field descriptions,
table constraints, and index creation statements; one string per
column/field, constraint, or index.  The list of strings forms a table
specification that can be joined with commas to form a table
definition, followed by optional index creation statements.  The
individual strings are very important since sqlite_parser was not
designed to parse complete CREATE TABLE statements; it needs the
string boundaries to determine when a column definition or table
constraint ends.

A column definition can have an optional suffix of the form:
"[FORMERLY field1, field2]".  This is used when renaming
columns. Without having this suffix, the mechanism that compares the
schemas will drop the old field and create a new one instead of
renaming an existing field that could have data in it.  The suffix is
removed from the SQL actually used to create the table.
"""

import sys
import os
import collections
import sqlite3
import re
import argparse
import tempfile
import datetime

from sqlite_pragma import *
from sqlite_parser import *

std_create_table_pattern = re.compile(
    r'\s*CREATE TABLE \w+\((.*)\)\s*', re.IGNORECASE)
single_quotes = re.compile(r"'[^']*'")

def compare_constraints(new_table, old_table, rename={}):
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
    Note that new table specifications parsed by sqlite_parser may contain
    pragma records for creating indices.  The CREATE INDEX statements are
    not compared by compare_constraints; only those indices created by
    primary key and unique constraints are compared here.
    The rename dictionary maps old field names to new ones.
    """
    old_sql = std_create_table_pattern.sub( # Get column def section of
        r'\1',                 # create table statement
        translate_old_field_names(
            standardize_create_table_sql(old_table['table_sql']), rename))
    new_constraints = []
    deleted_constraints = []
    for kind in ['column', 'fkey', 'index']: # Loop over constraint kinds in
        for constraint in new_table[kind]: # order and loop over pragma records
            if kind == 'fkey' or (
                    kind == 'index' and constraint.origin != 'c'):
                if len(old_table[kind]) == 0 or not any(
                        len(record_differences(
                            constraint, oldc, 
                            exclude=('id', 'seq', 'spec_line'), 
                            rename=rename)) == 0
                        for oldc in old_table[kind]):
                    new_constraints.append(constraint)
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
                
    # Parse remaining SQL for pragma records.
    # The constraints should be separated by commas, but we need to avoid
    # splitting on commas embedded in singly quoted expressions
    quoted = {}
    for i, m in enumerate(single_quotes.finditer(old_sql)): # Find all pairs
        quoted[i] = (m.start(), m.end(), m.group(0)) # of single quotes
    noparens = old_sql             # Start with old sql
    for i in range(len(quoted) - 1, -1, -1): # Go backwards through quoted
        start, end, string = quoted[i]   # strings, replacing them with a
        name = 'singlequoted{}'.format(i) # format variable name 
        noparens = noparens[0:start] + '{' + name + '}' + noparens[end:]
        quoted[name] = string      # Keep a dictionary to translate back
    parts = [part.format(**quoted) for part in noparens.split(',')]
    for pragma in table_pragma_records(
            parts, 'unknown_constraints', throwexceptions=False, printto=None):
        if isinstance(pragma, (sqlite_fkey_record, sqlite_index_record)):
            deleted_constraints.append(pragma)
    return new_constraints, deleted_constraints

parenthetical_expression = re.compile(r'\(.+\)')
word = re.compile(r'\w+')

def translate_old_field_names(old_sql, rename={}, only_within_parens=True):
    """Translate all references to old field names into their renamed
    counterparts in a table or index creation SQL statement.
    This translation could translate some non-field names since it
    does not fully parse the SQL.
    When only_within_parens is true, it only translates field names
    within the outermost parentheses
    """
    paren_match = parenthetical_expression.search(old_sql)
    if only_within_parens and paren_match:
        return (old_sql[:paren_match.start()] + '(' +
                translate_old_field_names(
                    old_sql[paren_match.start()  + 1:paren_match.end() - 1],
                    rename, False) +
                ')' + old_sql[paren_match.end():])
    result = ''
    last = 0
    for match in word.finditer(old_sql):
        result += old_sql[last:match.start()] + rename.get(
            match.group(), match.group())
        last = match.end()
    return result + old_sql[last:]
        
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

def compare_db_schema(new_schema, old_schema, verbose=0, ordermatters=False):
    """Compare 2 database schema's table by table.  Returns a dictionary
    with the following key: value pairs - 
    same: list of tables that are the same in both
    new_tables: list of tables in the new_schema that don't appear in the old
    drop_tables: list of tables in the old but not in the new_schema
    add_fields: list of tables where only new fields are added
    renamed_fields: dictionary of tables where old field names must be
      mapped to new field names (dictionary of dictionaries: outer dictionary
      maps table name to inner dictionary, inner dictionary maps old name to
      new name)
    different_table: list of tables with more complex differences
    add_index: list of tables with indices to add
    drop_index: list of tables with indices to drop
    """
    result = {
        'same_tables': [],
        'new_tables': [],
        'drop_tables': [],
        'add_fields': [],
        'renamed_fields': {},
        'different_table': [],
        'add_index': [],
        'drop_index': [],
        'different_index': [],
    }
    sep = '=' * 16
    for table in new_schema:
        if table not in old_schema:
            result['new_tables'].append(table)
        else:
            if verbose > 1:
                print(sep, 'Comparing schemas for table', table, sep)
            kind = compare_table_schema(new_schema[table], old_schema[table],
                                        table, ordermatters=ordermatters,
                                        verbose=verbose)
            index_kind = compare_table_indices(
                new_schema[table], old_schema[table], table, verbose=verbose)
            categorized = False
            for k in [kind, index_kind]:
                if k in ('add_fields', 'same', 'different_table', 
                         'add_index', 'drop_index', 'different_index'):
                    result['same_tables' if k == 'same' else k].append(table)
                    categorized = True
            if isinstance(kind, dict):
                result['renamed_fields'][table] = kind
                categorized = True
            if not categorized:
                raise Exception(
                    'Unknown difference types "{}, {}" for table {}'.format(
                        str(kind), str(index_kind), table))
    for table in old_schema:
        if table not in new_schema:
            result['drop_tables'].append(table)
    return result

def compare_table_schema(
        new_table, old_table, tablename, ordermatters=False, verbose=0):
    """Compare 2 tables described by their pragma dictionaries.  Return
    'same' if they are same, 'add_fields' if the new table has just
    added some fields to the table, a dictionary mapping old field
    names to new ones if the new table only renames some fields, or
    'different_table' if they differ in some other way.
    """
    if new_table['table_sql'] and old_table['table_sql']:
        new = standardize_create_table_sql(new_table['table_sql']).lower()
        old = standardize_create_table_sql(old_table['table_sql']).lower()
        if new == old:
            if verbose > 1:
                print('SQL for creating table {} is equivalent'.format(
                    tablename))
            return 'same'
        if verbose > 1:
            print('SQL for creating table {} differs'.format(tablename))
            if verbose > 2:
                print('  SQL for new:\n    ', new_table['table_sql'],
                      '\n  SQL for old:\n    ', old_table['table_sql'])
    elif verbose > 1:
        print('SQL for one or both versions of table {} is missing'.format(
            tablename))
        
    actual_cols =  dict_by_col_name(old_table['column'])
    fields_to_rename = renamed_fields(new_table['column'], old_table['column'],
                                      actual_cols=actual_cols)
    fields_to_add = missing_fields(
        new_table['column'], old_table['column'], actual_cols=actual_cols,
        rename=fields_to_rename)
    deleted = deleted_fields(
        new_table['column'], old_table['column'], rename=fields_to_rename)
    altered = altered_fields(
        new_table['column'], old_table['column'], ordermatters,
        actual_cols=actual_cols, rename=fields_to_rename)
    constraints_to_add, constraints_deleted = compare_constraints(
        new_table, old_table, rename=fields_to_rename)
    changed = len(fields_to_rename) + len(
        fields_to_add + deleted + altered + constraints_to_add +
        constraints_deleted) > 0
    if changed and verbose > 1:
        print('Pragma records have {}changed'.format('' if changed else 'not '))
        for name, value in [('Fields to rename', fields_to_rename),
                            ('Fields to add', fields_to_add),
                            ('Deleted fields', deleted),
                            ('Altered fields', altered),
                            ('Added constraints', constraints_to_add),
                            ('Deleted constraints', constraints_deleted)]:
            print('  {}:'.format(name))
            for r in value:
                print('   ', r,
                      '-> {}'.format(value[r]) if isinstance(value, dict)
                      else '')
    return 'same' if not changed else (
        'add_fields' if len(fields_to_add) > 0 and
        len(deleted + altered + constraints_to_add + constraints_deleted) == 0
        else fields_to_rename if len(fields_to_rename) > 0 and
        len(deleted + altered + constraints_to_add + constraints_deleted) == 0
        else 'different_table')

def renamed_fields(table_pragmas, actual_pragmas, actual_cols=None):
    """Return a mapping of columns in actual_pragmas whose name matches
    a former name of a column in table_pragmas."""
    if actual_cols is None:
        actual_cols = dict_by_col_name(actual_pragmas)
    result = {}
    for p in table_pragmas:
        name = p.name.lower()
        if isinstance(p, sqlite_column_record) and name not in actual_cols:
            for f in actual_pragmas:
                if f.name.lower() in p.formerly:
                    result[f.name.lower()] = name
                    result[f.name] = p.name
                    break
    return result

def missing_fields(table_pragmas, actual_pragmas, actual_cols=None, rename={}):
    if actual_cols is None:
        actual_cols = dict_by_col_name(actual_pragmas)
    return [p for p in table_pragmas if 
            isinstance(p, sqlite_column_record) and 
            p.name.lower() not in actual_cols and
            p.name.lower() not in rename.values()]

def common_fields(table_pragmas, actual_pragmas, actual_cols=None, rename={}):
    if actual_cols is None:
        actual_cols = dict_by_col_name(actual_pragmas)
    return [p for p in table_pragmas if 
            isinstance(p, sqlite_column_record) and 
            p.name.lower() in actual_cols]

def deleted_fields(table_pragmas, actual_pragmas, rename={}):
    return [p for p in actual_pragmas if 
            isinstance(p, sqlite_column_record) and
            p.name.lower() not in rename and
            p.name.lower() not in [f.name.lower() for f in table_pragmas
                                   if isinstance(f, sqlite_column_record)]]

def altered_fields(
        table_pragmas, actual_pragmas, ordermatters=False, actual_cols=None,
        rename={}):
    if actual_cols is None:
        actual_cols = dict_by_col_name(actual_pragmas)
    result = []
    for col in table_pragmas:
        new_column = col.name.lower()
        if isinstance(col, sqlite_column_record):
            renamed = False
            if new_column in actual_cols:
                actual = actual_cols[new_column]
            elif new_column in rename.values():
                for old_column in rename:
                    if rename[old_column] == new_column:
                        actual = actual_cols[old_column]
                        renamed = True
                        break
            else:   # This is an added column, not altered
                break
            diff = record_differences(
                col, actual, rename=rename,
                exclude=([] if ordermatters else ['cid']) + (
                    ['name'] if renamed else []) + ['formerly', 'spec_line'])
            if diff:
                result.append((col, ["{} for field '{}'".format(d, col.name)
                                     for d in diff]))
    return result

def compare_table_indices(new_table, old_table, tablename, verbose=0):
    """Compare the indices for 2 tables described by their pragma
    dictionaries.  This compares only the indices built from CREATE
    INDEX statements, not the ones automatically built by SQLite for
    primary keys or UNIQUE constraints.  Return 'same_index' if they are
    same, 'add_index' if the new table has some added indices,
    'drop_index' if the new table drops an index, or 'different_index' when
    they differ in some other way.
    """
    indices_to_add = missing_indices(new_table, old_table)
    indices_to_drop = deleted_indices(new_table, old_table)
    indices_to_change = altered_indices(new_table, old_table, verbose=verbose)
    differ = len(indices_to_change) > 0 or (
        len(indices_to_add) > 0 and len(indices_to_drop) > 0)
    if verbose > 1:
        print('Indices for table {}'.format(tablename), 
              'differ' if differ else
              'have been added' if len(indices_to_add) > 0 else
              'have been dropped' if len(indices_to_drop) > 0 else
              'are the same')
        if verbose > 2 and len(indices_to_add + indices_to_drop +
                               indices_to_change) > 0:
            print('  to add:', indices_to_add,
                  '\n  to drop:', indices_to_drop,
                  '\n  altered:', indices_to_change)
    return ('different_index' if differ else 
            'add_index' if len(indices_to_add) > 0 else
            'drop_index' if len(indices_to_drop) > 0 else
            'same_index')

def missing_indices(new_table, old_table):
    return [ni for ni in new_table['index']
            if ni.origin == 'c' and ni.name.lower() not in
            [oi.name.lower() for oi in old_table['index'] if oi.origin == 'c']]

def deleted_indices(new_table, old_table):
    return [oi for oi in old_table['index']
            if oi.origin == 'c' and oi.name.lower() not in
            [ni.name.lower() for ni in new_table['index'] if ni.origin == 'c']]

def altered_indices(new_table, old_table, verbose=0):
    new_indices = [p for p in new_table['index'] if p.origin == 'c']
    old_indices = [p for p in old_table['index'] if p.origin == 'c']
    old_index_dict = dict([(oi.name.lower(), oi) for oi in old_indices])
    result = []
    for new_index in new_indices:
        if new_index.name.lower() in old_index_dict:
            diff = record_differences(
                new_index, old_index_dict[new_index.name.lower()],
                exclude = ['seq'])
            if diff:
                result.append(
                    (new_index, ["{} for index '{}'".format(d, new_index.name)
                                 for d in diff]))
                if verbose > 1:
                    print('Index {} was altered: {}'.format(
                        new_index.name, diff))
    return result
    
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
                new_cols = new_db_schema[table]['column'] if in_new else []
                in_old = table in old_db_schema
                old_cols = old_db_schema[table]['column'] if in_old else []
                if table in done:
                    return
                rename = {}
                if in_new and in_old:
                    old_dict = dict_by_col_name(old_cols)
                    rename = renamed_fields(new_cols, old_cols, old_dict)
                    for name in [n for n in rename if n not in old_dict]:
                            del rename[name]  # Remove case variations
                if in_new:
                    if verbose > 1:
                        print('{} {} table ...'.format(
                            'Creating new' if in_new else 'Preserving', table))
                        if len(rename) > 0:
                            print('Renaming fields as follows:')
                            for name in rename:
                                print(' ', name, '->', rename[name])
                    cur.execute(pd['table_sql'])
                    if verbose > 1:
                        print(' {} Done.'.format(table))
                    if pd['index_sqls']:
                        if verbose > 1:
                            print('Creating indices for {}'.format(table))
                        for index_name in pd['index_sqls']:
                            cur.execute(pd['index_sqls'][index_name])
                old_col_names = [c.name for c in
                    (common_fields(pd['column'], old_cols)
                     if in_new and in_old else pd['column'])]
                new_col_names = old_col_names + list() # copy of names
                for name in rename:
                    old_col_names.append(name)
                    new_col_names.append(rename[name])
                if in_old and in_new:
                    if verbose > 1:
                        print('Copying old data... ', end='')
                    cur.execute(
                        'INSERT INTO main.{0} ({1}) SELECT {2} FROM {3}.{0}'
                        .format(table, ','.join(new_col_names), 
                                ','.join(old_col_names), old_name))
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

def upgrade_database(new_db_schema, old_db_schema, delta, dbfile, verbose=0):
    """Try upgrading database to create new tables, adding fields, and
    renaming fields.
    This method ignores any tables with more complex changes.
    Return True for success, false otherwise."""
    try:
        with sqliteCur(DBfile=dbfile) as cur:
            def alter_table(table, pd):
                if table in old_db_schema:
                    rename = {}
                    if table in delta['renamed_fields']:
                        rename = delta['renamed_fields'][table]
                        old_cols = [
                            p.name for p in old_db_schema[table]['column']
                            if p.name in rename]
                        if verbose > 1:
                            print('Altering {} table to rename column{} {}'
                                  .format(table,
                                          '' if len(old_cols) == 1 else 's',
                                          old_cols))
                        for field in old_cols:
                            cur.execute(
                                'ALTER TABLE {} RENAME COLUMN {} TO {}'
                                .format(table, field, rename[field]))
                    new_fields = [
                        p for p in missing_fields(
                            pd['column'], old_db_schema[table]['column'])
                        if p.name not in rename.values()]
                    if new_fields and verbose > 1:
                        print('Altering {} table to add field{} {}'.format(
                            table, '' if len(new_fields) == 1 else 's',
                            new_fields))
                    for field in new_fields:
                        if verbose > 2:
                            print('Adding column {}'.format(field.name))
                        cur.execute('ALTER TABLE {} ADD COLUMN {}'.format(
                            table, field.spec_line))
                    for kind in ['drop', 'add']:
                        if table in delta[kind + '_index']:
                            indices = (deleted_indices(pd, old_db_schema[table])
                                       if kind == 'drop' else
                                       missing_indices(pd, old_db_schema[table]))
                            if indices and verbose > 1:
                                print('{} {} table ind{} {}'.format(
                                    kind.capitalize(), table,
                                    'ex' if len(indices) == 1 else 'ices',
                                    indices))
                            for idx in indices:
                                cur.execute(
                                    'DROP INDEX {}'.format(idx.name) 
                                    if kind == 'drop' else
                                    idx.spec_line)
                else:
                    if verbose > 1:
                        print('Creating new {} table'.format(table))
                    cur.execute(pd['table_sql'])
            walk_tables(new_db_schema, alter_table, verbose=verbose)
        return True
    except sqlite3.DatabaseError as e:
        print('Error while trying to update {} in place:'.format(dbfile), e)
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
                cur.execute(pd['table_sql'])
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
    are not in the desired database schema will be migrated unchanged.  Tables
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
        print("="*20, 'Database Schema Difference Summary', "="*20)
        for k in sorted(delta.keys()):
            print('{}:'.format(k))
            for table in delta[k]:
                print(' ', table)
    simple_change_keys = [key for key in delta if key.split('_')[0] in 
                          ('new', 'add', 'renamed')]
    simple_changes = sum(len(delta[k]) for k in simple_change_keys)
    migrate_only_changes = sum(len(delta[k]) for k in
                               ['different_table', 'different_index'] + 
                               ([] if preserve_unspecified else
                                ['drop_tables', 'drop_index']))

    # If there are no changes or the forced response is no upgrade,
    # then no more work needs to be done
    if (simple_changes + migrate_only_changes == 0 or
        interpret_response(force_response, response_dict) is False):
        return True
    
    # Here, there are some desired schema changes.  Try altering the existing
    # database if conditions are right
    if migrate_only_changes == 0:
        description = ',\n'.join('{}: {}'.format(
            kind.replace('_', ' ').capitalize(), delta[kind])
                                 for kind in simple_change_keys if delta[kind])
        resp = interpret_response(force_response, response_dict)
        while resp is None:
            resp = interpret_response(
                input('{}Would you like to try changing tables as follows:\n'
                      '{}? [y/n] '.format(prompt_prefix, description)),
                response_dict)
            if resp is None:
                print('Unrecognized response.  Please answer yes or no.')
        if resp and upgrade_database(
                desired_db_schema, actual_db_schema, delta, dbfile,
                verbose=verbose):
            if verbose > 0:
                print('Successfully performed', description)
            simple_changes = 0
        else:
            if resp and verbose > 0:
                print('Altering database failed')
                
    # Here, we check again if there are remaining schema changes.  If so,
    # try migrating the database, backing up the existing one if it works
    if simple_changes + migrate_only_changes > 0:
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
        'constraint, or index createion statement.  '
        'If none specified, it uses the built-in MyTable specification.')
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
        '-d', '--drop-unused', default=False, action='store_true',
        help='Drop any tables and indices not mentioned in the schema '
        'when upgrading.')
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
        print('Text of desired database specification:')
        for table in database_spec:
            print('  Table specification ', tablesep, table, tablesep)
            for spec in database_spec[table]:
                print('   ', spec)
        print(linesep)

    desired_db_schema = parse_database_schema(database_spec)

    if args.verbose > 2:
        print('Parsed pragma records for database in {}:'.format(
            args.schema or 'sqlite_parser.py'))
        walk_tables(desired_db_schema,
                    lambda table, pragma_dict:
                    (print('  Desired table', tablesep, table, tablesep),
                     pprint_table_pragmas(pragma_dict, indent='    ',
                                          tablename=table)),
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
                         pprint_table_pragmas(pragma_dict, indent='    ',
                                              tablename=table)),
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
                    preserve_unspecified=not args.drop_unused,
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
                    preserve_unspecified=not args.drop_unused,
                    verbose=args.verbose):
                sys.exit(-1)
