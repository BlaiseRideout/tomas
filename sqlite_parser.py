#!/usr/bin/env python3

__doc__ = """
These utilities parse SQLite DDL statements and create records that
can be compared to the pragma records that SQLite produces (see
sqlite_pragma).  It's not designed to parse and process all SQLite
DDL.  Instead, it uses a combination of SQLite syntax with extensions.

The primary function is to parse the CREATE TABLE SQL DDL and create
records describing the table columns and their associated constraints.
The data description language (DDL) is enahanced with extensions for
renamed columns and associated indices.  The CREATE TABLE statments
must be stored as lists of field descriptions, table constraints, and
index creation statements; one string per column/field, constraint, or
index.  See mytable_schema below for an example.  The list of strings
forms a table specification that can be joined with commas to form a
table definition, followed by optional index creation statements.  The
individual strings are very important since it is not designed to
parse complete CREATE TABLE statements; it needs the string boundaries
to determine when a column definition or table constraint ends.

A column definition can have an optional suffix of the form:
"[FORMERLY field1, field2]".  This is used when renaming columns.  The
suffix is removed from the SQL stoed in the output record.  The SQL
in these fields are "pure" SQLite phrases that can be combined to
generate a full CREATE TABLE statement.

Groups of table specifications are kept in a dictionary with a key for
each table that maps to a list of specification statements as in the
database_spec below.  The CREATE TABLE prefix does not appear in
strings; it is implicit in the structure. Also, the WITHOUT ROWID
suffix cannot be handled by these specifications.
"""

mytable_schema = [  # Example table specification in separate lines
    'ID INTEGER PRIMARY KEY AUTOINCREMENT',
    'Name TEXT NOT NULL',
    'School TEXT REFERENCES AnotherTable(ID) ON DELETE CASCADE',
    'Score REAL [FORMERLY Field3]',
    'Date DATETIME DEFAULT CURRENT_TIMESTAMP',
    'CONSTRAINT KeepItReal UNIQUE(Score, Date)',
    'CREATE INDEX IF NOT EXISTS mytable_name_school ON mytable(Name, School)',
]
anothertable_schema = [
    'ID INTEGER PRIMARY KEY NOT NULL',
    'Name TEXT',
    "CHECK (Name != 'Voldemort')",
]
database_spec = {'MyTable': mytable_schema, 
                 'AnotherTable': anothertable_schema}

import sys, collections, sqlite3, re, argparse

from sqlite_pragma import *

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
    r'\s*\b(?!(CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK|CREATE)\b\s*)'
    r'(?P<name>\w+)\s+'
    r'(?P<type>(?P<typename>\w+)(\s*\([+-]?\d+\s*(,\s*[+-]?\d+\s*)?\))?)?',
    re.IGNORECASE)

constraint_name_pattern = re.compile(
    r'\s*(CONSTRAINT\s+(?P<cname>\w+)\s*\b)?', re.IGNORECASE)

col_pk_constraint_pattern = re.compile(
    r'\s*\bPRIMARY\s+(?P<pk>KEY)(\s+(ASC|DESC))?\b',
    re.IGNORECASE)

col_conflict_clause_pattern = re.compile(
    r'\s*\b(ON\s+CONFLICT\s+(?P<cresolution>\w+))?\b',
    re.IGNORECASE)

col_autoincrement_pattern = re.compile(
    r'\s*\b(?P<autoincrement>AUTOINCREMENT)?\b',
    re.IGNORECASE)

col_notnull_constraint_pattern = re.compile(
    r'\s*\b(?P<notnull>NOT\s+NULL)\b',
    re.IGNORECASE)

col_unique_constraint_pattern = re.compile(
    r'\s*\b(?P<unique>UNIQUE)\b',
    re.IGNORECASE)

col_check_constraint_pattern = re.compile( # Can't handle nested parentheses
    r"\s*\bCHECK\s*\((?P<checkexpr>[\w\s,'.+/*-]+)\)\s*\b",
    re.IGNORECASE)

col_default_constraint_pattern = re.compile(
    r"\s*\bDEFAULT\b\s*(?P<dflt_value>"
    r"[+-]?\d+(\.\d*\b)?|'[^']*'|"
    r"(TRUE|FALSE|NULL|CURRENT_(DATE|TIME|TIMESTAMP)\b)|"
    r"\((?P<expr>[\w\s,'.+/*-]+)\))",
    re.IGNORECASE)

col_collate_constraint_pattern = re.compile(
    r'\s*\bCOLLATE\s+(?P<collate>\w+)\b',
    re.IGNORECASE)

fkey_constraint_pattern = re.compile(
    r'\s*\bFOREIGN\s+KEY\s*\((?P<columns>(?P<column1>\w+)(\s*,\s*\w+)*\s*)\)',
    re.IGNORECASE)

fkey_clause_ref_pattern = re.compile(
    r'\s*\bREFERENCES\s+(?P<table>\w+)\s*'
    r'\((?P<columns>(?P<column1>\w+)(\s*,\s*\w+)*\s*)\)',
    re.IGNORECASE)

fkey_clause_conflict_pattern = re.compile(
    r'\s*\b((ON\s+(?P<action>DELETE|UPDATE|)\s+'
    r'(?P<reaction>SET\s+(NULL|DEFAULT)|CASCADE|RESTRICT|NO\s+ACTION))|'
    r'MATCH\s+(?P<match>\w+))\b',
    re.IGNORECASE)

fkey_clause_defer_pattern = re.compile(
    r'\s*\b(NOT\s+)?DEFERABLE(\s+INITIALLY\s+(DEFERRED|IMMEDIATE))?\b',
    re.IGNORECASE)

# This is the SQLite CREATE INDEX statement pattern
# (from https://www.sqlite.org/lang_createindex.html)
# This allows anything past the WHERE keyword to be accepted as the where
# expression
create_index_pattern = re.compile(
    r'\s*CREATE\s+INDEX(?P<exists>\s+IF\s+NOT\s+EXISTS)?\s+'
    r'(?P<name>(\w+\.)?\w+)\s+ON\s+(?P<tname>\w+)\s*'
    r'\((?P<cnames>(\w+(\s*,\s*)?)+)\s*\)(?P<partial>\s+WHERE\s+.*)?', 
    re.IGNORECASE)

# This is the special suffix pattern to identify a column formerly known by
# other names
former_name_pattern = re.compile(
    r'\s*\[FORMERLY\s+(?P<cnames>(\w+(\s*,\s*)?)+)\s*\]\s*$',
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
        (former_name_pattern, False, []),
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

# The tree for the things that come after column definitions, table
# constraints and create index statements, is similar to that for
# column definitions, except it will produce foreign key, primary key,
# uniqueness, check constraint, and table index records.
# Each node in the tree has the form (regex, repeat, next_tree)
post_column_spec_patterns = [
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
    (create_index_pattern, False, []),
]

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
    create_index_pattern: base_index_record._replace(origin='c', unique=0),
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

def words(spec):
    return re.findall(r'\w+', spec)
    
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
            create_table_sql_from_spec(
                table, [former_name_pattern.sub('', line)
                        for line in database_spec[table]
                        if create_index_pattern.match(line) is None]),
            create_index_sqls_from_spec(
                [line for line in database_spec[table]
                 if create_index_pattern.match(line) is not None],
                pragma_records))
    return db_schema

def create_table_sql_from_spec(table, table_spec):
    return 'CREATE TABLE {}({})'.format(table, ', '.join(table_spec))

def create_index_sqls_from_spec(index_specs, table_pragma_records):
    result = {}
    col_dict = dict_by_col_name(table_pragma_records)
    for s in index_specs:
        m = create_index_pattern.match(s)
        if m is None:
            raise Exception('Invalid index spec "{}"'.format(s))
        name = m.group('name').strip()
        if any(w.strip().lower() not in col_dict 
               for w in words(m.group('cnames'))):
            raise Exception('Index spec "{}" refers to unknown columns'
                            .format(s))
        result[name] = 'CREATE INDEX{} {} ON {}({}){}'.format(
            m.group('exists') or '', name, m.group('tname').strip(), 
            m.group('cnames'), m.group('partial') or '')
    return result
            
multi_whitespace = re.compile(r'\s\s+')
sql_delims = re.compile(r'\s*([,()])\s*')
optional_declarations = re.compile(
    r'^CREATE( TEMP(ORARY)?)? TABLE( IF NOT EXISTS)?', re.IGNORECASE)
dbname_declaration = re.compile(r'^CREATE TABLE (\w+)\.', re.IGNORECASE)

def standardize_create_table_sql(sql):
    """Standardize create table SQL whitespace usage and simplify for
    comparison purposes.
    Convert multiple whitespace characters to single spaces.
    Replace space around delimiters with no space.
    Remove TEMP[ORARY] between CREATE and TABLE.
    Remove IF NOT EXISTS after TABLE.
    Remove schema name from table name.
    """
    return dbname_declaration.sub(
        'CREATE TABLE ',
        optional_declarations.sub(
            'CREATE TABLE',
            sql_delims.sub(r'\1', multi_whitespace.sub(' ', sql.strip()))))
    
def table_pragma_records(
        table_spec, tablename='',
        patterns_to_try = column_def_patterns + post_column_spec_patterns,
        throwexceptions=True, printto=sys.stderr):
    """Parse a table specification that is a list of strings with exactly
    one column definition, one table constraint, or one create index
    specification per string.  The tablename should be the name of the
    table in SQLite and will be used in naming constraints.  The
    patterns_to_try is the grammar to use in parsing (in the form of a
    tree of regex tuples).  If grammar errors are found, they can
    either cause exceptions, or be printed to a file (or be silently
    ignored if printto is None).
    """
    pragmas = []
    for spec in table_spec:
        pragmas.extend(
            column_def_or_constraint_to_pragma_records(
                spec, pragmas, tablename,
                # TODO: Find a better test to determine when all column def's
                # have been processed and only table constraints and
                # index creation statements remain in the table specification
                # patterns_to_try=(column_def_patterns 
                #                  if len(pragmas) == 0 or 
                #                  isinstance(pragmas[-1], sqlite_column_record)
                #                  else []) + post_column_spec_patterns,
                throwexceptions=throwexceptions, printto=printto))
    return pragmas
    
def column_def_or_constraint_to_pragma_records(
        spec, context=[], tablename='',
        patterns_to_try = column_def_patterns + post_column_spec_patterns,
        throwexceptions=True, printto=sys.stderr):
    """Parse a single column definition, table constraint or index
    creation statement within a table specification.  The context
    variable should have all the pragma records that have been parsed
    before this line, so references to columns that are defined
    earlier can be resolved.  Some pragma records in the context can
    be modified by later constraints such as PRIMARY KEY constraints.
    """
    global base_record_prototype
    # Walk the tree of patterns, find matching regex's,
    # Create corresponding records while inserting values into named fields
    # as regex's match
    # Return a list of pragma records built from the spec
    pragmas = []
    indices = 0
    past_indices = 0
    pk_counter = 1
    spec = spec.strip()
    spec_line = spec
    for p in context:
        if isinstance(p, sqlite_index_record):
            past_indices += 1
    stack = [(patterns_to_try, spec)]
    while stack:
        patterns_to_try, spec = stack[-1]
        if patterns_to_try:
            pattern, repeat, next_patterns = patterns_to_try[0]
            m = pattern.match(spec)
        else:
            m = None
        if tablename in (None,):
            print("="*30, "Table", tablename, "="*30)
            print("Stack depth =", len(stack), " ", 
                  len(patterns_to_try), "patterns to try")
            print("Current pattern", pattern, m)
            print("Remaining specification", repr(spec))
        if m:
            if pattern in base_record_prototype and (
                len(pragmas) == 0 or 
                not isinstance(pragmas[-1], 
                               type(base_record_prototype[pattern]))):
                pragmas.append(
                    base_record_prototype[pattern]._replace(
                        spec_line=spec_line))
            if len(pragmas) > 0:
                record_fields = dict([
                    (field, m.group(field)) for field in pattern.groupindex
                    if m.group(field) is not None and 
                    field in pragmas[-1]._fields])
                if record_fields:
                    pragmas[-1] = pragmas[-1]._replace(**record_fields)
                # Handle special case matches
                pragmas = update_pragma_record_stack_with_match(
                    context, pragmas, pattern, m, spec_line)
            remaining = spec[m.end():]
            # If this match consumed the whole specification, then done
            if len(remaining) == 0 or remaining.isspace():
                stack, spec = [], remaining
            else: # When there remains some specification to process,
                # ensure stack can return to this pattern if repeat is enabled
                # and some spec was matched, otherwise go to next pattern
                stack[-1] = (patterns_to_try if repeat and m.end() > 0
                             else patterns_to_try[1:],
                             remaining)
                stack.append((next_patterns, remaining))
        elif patterns_to_try: # Try next pattern, if any, after match fails
            stack[-1] = (patterns_to_try[1:], spec)
        if stack and len(stack[-1][0]) == 0: # No more patterns on top?
            patterns_to_try, spec = stack.pop() # then pop stack
    result = []
    if len(spec) > 0 and not spec.isspace():
        msg = ('Unable to parse this part of the column definition: "{}" '
               'in table {} where the full line is "{}"').format(
                   spec, tablename, spec_line)
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
                if isinstance(pragma.seq, list): # Is this a multi-field PK?
                    for col in pragma.seq: # then find matching columns
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
                if pragma.origin in ('pk', 'u'):
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
            if ('action' in pattern.groupindex and
                'reaction' in pattern.groupindex):
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
        elif pattern == former_name_pattern and match.group('cnames'):
            # For the former names of columns, update the column record
            # to store the list of former column names and remove the suffix
            # from the specification line used to create the table
            top_record = top_record._replace(
                formerly=[n.lower() for n in words(match.group('cnames'))],
                spec_line=top_record.spec_line[: - len(match.group(0))])

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
              top_record.origin == 'pk' and
              len(pragma_record_stack) > 0 and
              isinstance(pragma_record_stack[-1], sqlite_column_record) and
              sqlite_integer_type_affinity(pragma_record_stack[-1].type)):
            pragma_record_stack[-1] = pragma_record_stack[-1]._replace(pk=1)
            top_record = None
    if top_record:
        pragma_record_stack.append(top_record)
    return pragma_record_stack

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'schema', nargs='+', type=argparse.FileType('r'),
        help='File containing SQLite database description to parse.  '
        'The file should contain the source code for a Python dictionary '
        'where each key in the dictionary is a table name and its value '
        'is a list of strings with one string per column definition, table '
        'constraint, or index creation statement.' )
    parser.add_argument(
        '-t', '--tables', nargs='*', default=[],
        help='Tables to display.  If none provided, all are printed.')

    args = parser.parse_args()

    linesep = '=' * 78
    tablesep = '--<' + '=' * 15 + '>--'

    for specfile in args.schema:
        if not os.path.exists(specfile.name):
            print("Schema file, {}, doesn't exist".format(specfile.name))
        else:
            print(linesep)
            print('Database schema in {}:'.format(specfile.name))
            try:
                db_spec = eval(specfile.read())
                db_schema = parse_database_schema(db_spec)
                for table in db_spec:
                    if args.tables == [] or table.lower() in [
                            t.lower() for t in args.tables]:
                        print(tablesep, table, 'Specification', tablesep)
                        for line in db_spec[table]:
                            print('  ', line)
                        print(tablesep, table, 'Pragma Records', tablesep)
                        pprint_table_pragmas(db_schema[table], tablename=table)
                print(linesep)
            except Exception as e:
                print('Unable to read database specification. ', e)
