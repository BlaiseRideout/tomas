#!/usr/bin/env python3

import warnings
import sqlite3
import random
import datetime
import csv
import collections
import re
import os
import shutil

import util
import settings

class getCur():
    con = None
    cur = None
    def __enter__(self):
        self.con = sqlite3.connect(settings.DBFILE)
        self.cur = self.con.cursor()
        self.cur.execute("PRAGMA foreign_keys = 1;")
        return self.cur
    def __exit__(self, type, value, traceback):
        if self.cur and self.con and not value:
            self.cur.close()
            self.con.commit()
            self.con.close()

        return False

schema = collections.OrderedDict({
    'Countries': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Name TEXT",
        "Code TEXT",
        "IOC_Code TEXT",
        "IOC_Name TEXT",
        "Flag_Image TEXT"
    ],
    'Rounds': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Ordering INTEGER",
        "Algorithm INTEGER",
        "Seed TEXT",
        "Cut TINYINT",
        "SoftCut TINYINT",
        "CutSize INTEGER DEFAULT NULL",
        "Duplicates TINYINT DEFAULT 1",
        "Diversity TINYINT DEFAULT 1",
        "UsePools TINYINT DEFAULT 1",
        "Winds TINYINT DEFAULT 1",
        "Games INTEGER DEFAULT 1"
    ],
    'Seating': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Round INTEGER",
        "Player INTEGER",
        "TableNum INTEGER",
        "Wind TINYINT",
        "FOREIGN KEY(Player) REFERENCES Players(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Round) REFERENCES Rounds(Id) ON DELETE CASCADE"
    ],
    'Players': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Name TEXT NOT NULL",
        "Number INTEGER",
        "Country INTEGER",
        "Association TEXT",
        "Pool TEXT",
        "Type TINYINT DEFAULT 0",
        "FOREIGN KEY(Country) REFERENCES Countries(Id) ON DELETE CASCADE",
        "UNIQUE(Number)"
    ],
    'Scores': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "GameId INTEGER",
        "Round INTEGER",
        "PlayerId INTEGER",
        "Rank TINYINT",
        "RawScore INTEGER",
        "Score REAL",
        "FOREIGN KEY(Round) REFERENCES Rounds(Id) ON DELETE CASCADE",
        "FOREIGN KEY(PlayerId) REFERENCES Players(Id) ON DELETE CASCADE",
        "CONSTRAINT OneScorePerPlayerPerGame UNIQUE (Round, GameId, PlayerId)"
    ],
    'Penalties': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "ScoreId INTEGER",
        "Penalty INTEGER",
        "Description TEXT NOT NULL",
        "Referee TEXT",
        "FOREIGN KEY(ScoreId) REFERENCES Scores(Id) ON DELETE CASCADE",
    ],
    'Users': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Email TEXT NOT NULL",
        "Password TEXT NOT NULL",
        "UNIQUE(Email)"
    ],
    'Admins': [
        'Id INTEGER PRIMARY KEY NOT NULL',
        'FOREIGN KEY(Id) REFERENCES Users(Id) ON DELETE CASCADE'
    ],
    'ResetLinks': [
        'Id CHAR(32) PRIMARY KEY NOT NULL',
        'User INTEGER',
        'Expires DATETIME',
        'FOREIGN KEY(User) REFERENCES Users(Id)'
    ],
    'VerifyLinks': [
        'Id CHAR(32) PRIMARY KEY NOT NULL',
        'Email TEXT NOT NULL',
        'Expires DATETIME'
    ],
    'Preferences': [
        'UserId INTEGER',
        'Preference TEXT NOT NULL',
        'Value SETTING NOT NULL',
        'FOREIGN KEY(UserId) REFERENCES Users(Id)'
    ],
})

# Decode table for Players.Type values
playertypes = ['', 'Inactive', 'Substitute']

def init(force=False):
    warnings.filterwarnings('ignore', r'Table \'[^\']*\' already exists')

    global schema
    independent_tables = []
    dependent_tables = []
    for table in schema:
        if len(parent_tables(schema[table])) == 0:
            independent_tables.append(table)
        else:
            dependent_tables.append(table)

    to_check = collections.deque(independent_tables + dependent_tables)
    checked = set()
    max_count = len(independent_tables) + len(dependent_tables) ** 2 / 2
    count = 0
    while count < max_count and len(to_check) > 0:
        table = to_check.popleft()
        # If this table's parents haven't been checked yet, defer it
        if set(parent_tables(table)) - checked:
            to_check.append(table)
        else:
            check_table_schema(table, force=force)
            checked.add(table)
        count += 1

    with getCur() as cur:
        cur.execute("SELECT COUNT(*) FROM Countries")
        if cur.fetchone()[0] == 0:
            with open("countries.csv", "r") as countriesfile:
                reader = csv.reader(countriesfile)
                for row in reader:
                    cur.execute(
                        "INSERT INTO Countries"
                        " (Name, Code, IOC_Code, IOC_Name, Flag_Image)"
                        " VALUES(?, ?, ?, ?, ?)", row)

def make_backup():
    backupdb = datetime.datetime.now().strftime(settings.DBDATEFORMAT) + "-" + os.path.split(settings.DBFILE)[1]
    backupdb = os.path.join(settings.DBBACKUPS, backupdb)
    print("Making backup of database {0} to {1}".format(settings.DBFILE, backupdb))
    if not os.path.isdir(settings.DBBACKUPS):
        os.mkdir(settings.DBBACKUPS)
    shutil.copyfile(settings.DBFILE, backupdb)

fkey_pattern = re.compile(
    r'.*FOREIGN\s+KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\s*\((\w+)\).*',
    re.IGNORECASE)

def parent_tables(table_spec):
    global fkey_pattern
    parents = []
    for spec in table_spec:
        match = fkey_pattern.match(spec)
        if match:
            parents.append(match.group(2))
    return parents

def check_table_schema(tablename, force=False, backupname="_backup"):
    """Compare existing table schema with that specified in schema above
    and make corrections as needed.  This checks for new tables, new
    fields, new (foreign key) constraints, and altered field specificaitons.
    For schema changes beyond just adding fields, it renames the old table
    to a "backup" table, and then copies its content into a freshly built
    new version of the table.
    For really complex schema changs, move the old database aside and
    either build from scratch or manually alter it.
    """
    table_fields = schema[tablename]
    with getCur() as cur:
        cur.execute("PRAGMA table_info('{0}')".format(tablename))
        actual_fields = cur.fetchall()
        cur.execute("PRAGMA foreign_key_list('{0}')".format(tablename))
        actual_fkeys = cur.fetchall()
        if len(actual_fields) == 0:
            cur.execute("CREATE TABLE IF NOT EXISTS {0} ({1});".format(
                tablename, ", ".join(table_fields)))
        else:
            fields_to_add = missing_fields(table_fields, actual_fields)
            fkeys_to_add = missing_constraints(table_fields, actual_fkeys)
            altered = altered_fields(table_fields, actual_fields)
            deleted = deleted_fields(table_fields, actual_fields)
            if (len(fields_to_add) > 0 and len(fkeys_to_add) == 0 and
                len(altered) == 0 and len(deleted) == 0):
                # Only new fields to add
                if force or util.prompt(
                        "SCHEMA CHANGE: Add {0} to table {1}".format(
                            ", ".join(fields_to_add), tablename)):
                    for field_spec in fields_to_add:
                        cur.execute("ALTER TABLE {0} ADD COLUMN {1};".format(
                            tablename, field_spec))
            elif len(fkeys_to_add) > 0 or len(altered) > 0 or len(deleted) > 0:
                # Fields have changed significantly; try copying old into new
                if force or util.prompt(
                        ("SCHEMA CHANGE: Backup and recreate table {0} "
                         "to add {1}, impose {2}, correct {3}, and delete {4}))").format(
                             tablename, fields_to_add, fkeys_to_add,
                             altered, deleted)):
                    make_backup()
                    backup = tablename + backupname
                    sql = "ALTER TABLE {0} RENAME TO {1};".format(
                        tablename, backup)
                    cur.execute(sql)
                    sql = "CREATE TABLE {0} ({1});".format(
                        tablename, ", ".join(table_fields))
                    cur.execute(sql)
                    # Copy all actual fields that have a corresponding field
                    # in the new schema
                    common_fields = [
                        f[1] for f in actual_fields if
                        find_field_spec_for_pragma(table_fields, f)]
                    sql = "INSERT INTO {0} ({1}) SELECT {1} FROM {2};".format(
                        tablename, ", ".join(common_fields), backup)
                    cur.execute(sql)
                    sql = "DROP TABLE {0};".format(backup)
                    cur.execute(sql)

def words(spec):
    return re.findall(r'\w+', spec)

def missing_fields(table_fields, actual_fields):
    return [ field_spec for field_spec in table_fields if (
        words(field_spec)[0].upper() not in [
            'FOREIGN', 'CONSTRAINT', 'PRIMARY', 'UNIQUE', 'NOT',
            'CHECK', 'DEFAULT', 'COLLATE'] + [
                x[1].upper() for x in actual_fields]) ]

def missing_constraints(table_fields, actual_fkeys):
    return [ field_spec for field_spec in table_fields if (
        words(field_spec)[0].upper() in ['FOREIGN', 'CONSTRAINT'] and
        'REFERENCES' in [ w.upper() for w in words(field_spec) ] and
        not any(map(lambda fkey: match_constraint(field_spec, fkey),
                    actual_fkeys))) ]

def match_constraint(field_spec, fkey_record):
    global fkey_pattern
    match = fkey_pattern.match(field_spec)
    return (match and
            match.group(1).upper() == fkey_record[3].upper() and
            match.group(2).upper() == fkey_record[2].upper() and
            match.group(3).upper() == fkey_record[4].upper())

sqlite_pragma_columns = [
    'column_ID', 'name', 'type', 'notnull', 'default', 'pk_member'
]

def altered_fields(table_fields, actual_fields):
    altered = []
    for actual in actual_fields:
        matching_spec = find_field_spec_for_pragma(table_fields, actual)
        if matching_spec and not field_spec_matches_pragma(matching_spec, actual):
            altered.append(matching_spec)
    return altered

def deleted_fields(table_fields, actual_fields):
    deleted = []
    for actual in actual_fields:
        matching_spec = find_field_spec_for_pragma(table_fields, actual)
        if not matching_spec:
            deleted.append(actual[1] + ' ' + actual[2])
    return deleted

def find_field_spec_for_pragma(table_fields, pragma_rec):
    for field in table_fields:
        if words(field)[0].upper() == pragma_rec[1].upper():
            return field
    return None

def field_spec_matches_pragma(field_spec, pragma_rec):
    global sqlite_pragma_columns
    if field_spec is None or pragma_rec is None:
        return False
    field = dict(zip(
        sqlite_pragma_columns,
        [x.upper() if isinstance(x, str) else x for x in pragma_rec]))
    spec = words(field_spec.upper())
    return (spec[0] == field['name'] and
            all([w in spec for w in words(field['type'])]) and
            (field['notnull'] == 0 or ('NOT' in spec and 'NULL' in spec)) and
            (field['default'] is None or
             ('DEFAULT' in spec and str(field['default']) in spec)) and
            (field['pk_member'] == (
                1 if 'PRIMARY' in spec and 'KEY' in spec else 0))
    )

pointsPerPlayer = 30000

def updateGame(scores):
    if scores is None:
        return {"status":"error", "message":"Please enter some scores"}

    if len(scores) != 4 and len(scores) != 5:
        return {"status":"error", "message":"Please enter 4 or 5 scores"}

    try:
        with getCur() as cur:
            total = 0
            gameID = None
            roundID = None
            for score in scores:
                total += score['rawscore']

                for table, id in [('Players', 'playerid'),
                                  ('Rounds', 'roundid')]:
                    cur.execute("SELECT Id from {0} WHERE Id = ?".format(table),
                                (score[id],))
                    if cur.fetchone() is None:
                        return {"status":1,
                                "error":"ID {0} not in {1}".format(
                                    score[id], table)}
                if gameID is not None and gameID != score['gameid']:
                    return {"status":"error",
                            "message": "Inconsistent game IDs"}
                gameID = score['gameid']
                if roundID is not None and roundID != score['roundid']:
                    return {"status":"error",
                            "message": "Inconsistent round IDs"}
                roundID = score['roundid']

            if total != len(scores) * pointsPerPlayer:
                return {"status":"error",
                        "message":"Scores do not add up to {0}".format(
                            len(scores) * pointsPerPlayer)}

            cur.execute("DELETE FROM Scores WHERE GameId = ? and Round = ?",
                        (gameID, roundID))
            fields = ['roundid', 'gameid', 'playerid', 'rank', 'rawscore',
                      'score']
            cur.executemany(
                "INSERT INTO Scores"
                " (Round, GameId, PlayerId, Rank, RawScore, Score)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                map(lambda score: [score[f] for f in fields], scores))
    except Exception as e:
        return {"status":"error",
                "message": "Error during database update of scores, {0}".format(e)}

    return {"status": "success"}

penalty_fields = ['penalty', 'description', 'referee']

valid = {
    'all': re.compile(r'^[\w\s():,.\'+\u202F-]*$'),
    'description': re.compile(r'^[\w\s():,.\'+\u202F-]*$'),
    'penalty': re.compile(r'^-?\d*$'),
    'name': re.compile(r'^[\w\s():,.\'+\u202F-]*$'),
    'number': re.compile(r'^\d*$'),
}

def updatePenalties(scoreID, penalties):
    global penalty_fields
    global valid
    if penalties is None:
        return {"status":"error", "message":"Please enter a list of penalties"}

    try:
        with getCur() as cur:
            cur.execute("SELECT Id from Scores WHERE Id = ?", (scoreID,))
            if cur.fetchone() is None:
                return {"status": "error",
                        "message":"Score ID {0} not in Scores".format(scoreID)}
            message = ''
            for penalty in penalties:
                if str(penalty['scoreID']) != str(scoreID):
                    return {"status":"error",
                            "message": "All penalties must be for a single player score record"}
                if penalty['penalty'] > 0:
                    message += ' All penalties must be negative integers.'
                for field, val in penalty.items():
                    if field not in penalty_fields or not isinstance(val, str):
                        continue
                    if not valid[field if field in valid else 'all'].match(val):
                        message += " Invalid entry for {0} field.".format(
                                    field)
            if len(message) > 0:
                return {"status": "error", "message": message}
            
            cur.execute("DELETE FROM Penalties WHERE ScoreId = ?", (scoreID,))
            fields = ['scoreID', 'penalty', 'description', 'referee']
            cur.executemany(
                "INSERT INTO Penalties"
                " (ScoreId, Penalty, Description, Referee)"
                " VALUES (?, ?, ?, ?)",
                map(lambda penalty: [penalty[f] for f in fields], penalties))
    except Exception as e:
        return {"status":"error",
                "message": "Error during database update of penalties, {0}".format(e)}

    return {"status": "success"}
