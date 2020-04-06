#!/usr/bin/env python3

__doc__ = """
This utility migrates data from tomas schema where player records could
only be in one tournament to a many-to-many relationship between players
and tournaments using the compete table to link them.
"""

import sys, os, sqlite3, argparse

from sqlite_pragma import *
from sqlite_parser import *
from sqlite_schema import *

import db

schema_spec = {
    'Users': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Email TEXT NOT NULL",
        "Password TEXT NOT NULL",
        "UNIQUE(Email)"
    ],
    'Admins': [
        "Id INTEGER PRIMARY KEY NOT NULL",
        "FOREIGN KEY(Id) REFERENCES Users(Id) ON DELETE CASCADE"
    ],
    'Tournaments': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Name TEXT",
        "Owner INTEGER",
        "Start DATE DEFAULT CURRENT_DATE",
        "End DATE DEFAULT CURRENT_DATE",
        "Location TEXT",
        "Country INTEGER",
        "ScorePerPlayer INTEGER",
        "Logo TEXT",
        "LinkURL TEXT",
        "FOREIGN KEY(Owner) REFERENCES Users(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Country) REFERENCES Countries(Id) ON DELETE CASCADE"
    ],
    'Countries': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Name TEXT",
        "Code TEXT",
        "IOC_Code TEXT",
        "IOC_Name TEXT",
        "Flag_Image TEXT"
    ],
    'Stages': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Tournament INTEGER NOT NULL",
        "Name TEXT",
        "SortOrder INTEGER NOT NULL DEFAULT 0",
        "PreviousStage INTEGER",
        "Ranks INTEGER",
        "Cumulative TINYINT NOT NULL DEFAULT 0",
        "FOREIGN KEY(Tournament) REFERENCES Tournaments(Id) ON DELETE CASCADE",
        "FOREIGN KEY(PreviousStage) REFERENCES Stages(Id) ON DELETE CASCADE",
    ],
    'Rounds': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Tournament INTEGER",
        "Number INTEGER",
        "Name TEXT",
        "Ordering INTEGER",
        "Algorithm INTEGER",
        "Seed TEXT DEFAULT ''",
        "Cut TINYINT DEFAULT 0",
        "SoftCut TINYINT DEFAULT 0",
        "CutMobility TINYINT DEFAULT 0",
        "CombineLastCut TINYINT DEFAULT 0",
        "CutSize INTEGER DEFAULT NULL",
        "CutCount INTEGER DEFAULT NULL",
        "Duplicates TINYINT DEFAULT 1",
        "Diversity TINYINT DEFAULT 1",
        "UsePools TINYINT DEFAULT 1",
        "Winds TINYINT DEFAULT 1",
        "Games INTEGER DEFAULT 1",
        "FOREIGN KEY(Tournament) REFERENCES Tournaments(Id) ON DELETE CASCADE"
    ],
    'Players': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Name TEXT NOT NULL",
        "Country INTEGER",
        "Association TEXT",
	"BirthYear INTEGER",
	"ReplacedBy INTEGER",
        "FOREIGN KEY(Country) REFERENCES Countries(Id) ON DELETE CASCADE",
    ],
    'Compete': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Player INTEGER",
        "Tournament INTEGER",
        "Number INTEGER",
        "Pool TEXT",
        "Wheel TINYINT DEFAULT 0",
        "Type TINYINT DEFAULT 0",
        "FOREIGN KEY(Player) REFERENCES Players(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Tournament) REFERENCES Tournaments(Id) ON DELETE CASCADE",
        "CONSTRAINT NumberInTournament UNIQUE(Number, Tournament)",
        "CONSTRAINT OncePerTournament UNIQUE(Player, Tournament)",
        "CREATE INDEX TournamentPlayers ON Compete (Tournament, Player)",
    ],
    'Seating': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Round INTEGER",
        "Tournament INTEGER",
        "Player INTEGER",
        "TableNum INTEGER",
        "Wind TINYINT",
        "CutName TEXT DEFAULT ''",
        "FOREIGN KEY(Tournament) REFERENCES Tournaments(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Player) REFERENCES Players(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Round) REFERENCES Rounds(Id) ON DELETE CASCADE"
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
    'ResetLinks': [
        'Id CHAR(32) PRIMARY KEY NOT NULL',
        'User INTEGER',
        'Expires DATETIME',
        'FOREIGN KEY(User) REFERENCES Users(Id) ON DELETE CASCADE'
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
        'FOREIGN KEY(UserId) REFERENCES Users(Id) ON DELETE CASCADE'
    ],
}

def migrate_data(olddb, newdb, newdb_schema, keep_orphans=False, verbose=0):
    olddb_schema = get_sqlite_db_schema(olddb)
    with sqliteCur(DBfile=newdb) as cur:
        old_name = "Old"
        cur.execute("ATTACH DATABASE '{}' AS {}".format(olddb, old_name))
        done = []
        def copy_table(table, pd):
            if table in done:
                return
            in_new = table in newdb_schema
            new_cols = newdb_schema[table]['column'] if in_new else []
            in_old = table in olddb_schema
            old_cols = olddb_schema[table]['column'] if in_old else []
            old_fkeys = [p for p in olddb_schema[table]['fkey']
                         if p.on_delete.upper() == 'CASCADE'] if in_old else []
            rename = {}
            if in_new and in_old and table not in ('Players'):
                old_dict = dict_by_col_name(old_cols)
                rename = renamed_fields(new_cols, old_cols, old_dict)
                for name in [n for n in rename if n not in old_dict]:
                    del rename[name]  # Remove case variations
                old_col_names = [c.name for c in
                    (common_fields(pd['column'], old_cols)
                     if in_new and in_old else pd['column'])]
                new_col_names = old_col_names + list() # copy of names
                for name in rename:
                    old_col_names.append(name)
                    new_col_names.append(rename[name])
                if in_old and in_new:
                    if verbose > 1:
                        print('Copying old data from {} ... '.format(table),
                              end='')
                    sql = ('INSERT INTO main.{0} ({1})'
                           ' SELECT {2} FROM {3}.{0}').format(
                               table, ','.join(new_col_names), 
                               ','.join(old_col_names), old_name)
                    if not keep_orphans and old_fkeys:
                        sql += ' WHERE ' + ' AND '.join([
                            '({}) IN (SELECT {} FROM {}.{})'.format(
                                ','.join(p.from_) if isinstance(p.from_, list)
                                else p.from_,
                                ','.join(p.to) if isinstance(p.to, list)
                                else p.to, 
                                'main' if p.table in done else old_name,
                                p.table)
                            for p in old_fkeys])
                    if verbose > 2:
                        print(sql)
                    cur.execute(sql)
                    if verbose > 1:
                        print('Copied {} row{} into {}'.format(
                            cur.rowcount, '' if cur.rowcount == 1 else 's',
                            table))
                done.append(table)
            elif in_old and in_new and table == 'Players':
                if verbose > 1:
                    print('Migrating old data from {} ... '.format(table),
                    end='')
                sql = ('INSERT INTO main.{0} (Id, Name, Country, Association)'
                       ' SELECT Id, Name, Country, Association FROM {1}.{0}'
                       ).format(table,  old_name)
                if not keep_orphans:
                    sql += (" WHERE Players.Name = '{}' OR"
                            ' (Players.Tournament IN'
                            '   (SELECT Id FROM main.Tournaments) AND'
                            '  Players.Country IN'
                            '   (SELECT Id FROM main.Countries))').format(
                                db.unusedPointsPlayerName)
                if verbose > 2:
                    print(sql)
                cur.execute(sql)
                if verbose > 1:
                    print('Copied {} row{} into {}'.format(
                        cur.rowcount, '' if cur.rowcount == 1 else 's',
                        table))
                done.append(table)
            elif in_new and table == 'Compete':
                colnames = [c.name for c in new_cols if c.name != 'Id']
                if verbose > 1:
                    print('Extracting old links to make {} ... '.format(table),
                    end='')
                sql = ('INSERT INTO main.{0} ({2})'
                       ' SELECT Id, {3} FROM {1}.Players'
                       ).format(table, old_name, ','.join(colnames),
                                ','.join(colnames[1:]))
                if not keep_orphans:
                    sql += (' WHERE Players.Tournament'
                            ' IN (SELECT Id FROM main.Tournaments) AND'
                            ' Players.Country IN'
                            '  (SELECT Id FROM main.Countries)')
                if verbose > 2:
                    print(sql)
                cur.execute(sql)
                if verbose > 1:
                    print('Copied {} row{} into {}'.format(
                        cur.rowcount, '' if cur.rowcount == 1 else 's',
                        table))
                done.append(table)
                
        # The migration needs to know that the Players table used to have
        # a foreign key constraint with the Tournaments table to properly
        # order the population of new tables
        newdb_schema['Players']['fkey'].append(
            sqlite_fkey_record(
                None, None, 'Tournaments', 'Tournament', 'Id',
                'NO ACTION', 'CASCADE', 'NONE', ''))
        walk_tables(newdb_schema, copy_table, verbose=verbose)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'olddatabase', help='Current SQLite3 database file to migrate.')
    parser.add_argument(
        'newdatabase', help='Name of new SQLite3 database for migrated data.')
    parser.add_argument(
        '-k', '--keep-orphans', default=False, action='store_true',
        help='Try keeping orphaned records during migration.')
    parser.add_argument(
        '-f', '--force-overwrite', default=False, action='store_true',
        help='Force overwrite of new database, if it exists.')
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help='Add verbose comments.')

    args = parser.parse_args()

    if not os.path.exists(args.olddatabase):
        print('Input database file, {}, does not exist.'.format(
            args.olddatabase))
        sys.exit(-1)

    new_db_schema = parse_database_schema(schema_spec)
    response_dict={True: ['y', 'yes', '1'], False: ['n', 'no', '0']}
    if os.path.exists(args.newdatabase):
        if args.force_overwrite or interpret_response(
                input('Do you want to overwrite {}? [y/n] '.format(
                    args.newdatabase)), response_dict):
            os.remove(args.newdatabase)
            print('Removed {} file'.format(args.newdatabase))
        else:
            print('Exiting without overwriting {}.'.format(
                args.newdatabase))
            sys.exit(-1)
            
    if not create_database(new_db_schema, args.newdatabase,
                           verbose=args.verbose):
        sys.exit(-1)

    migrate_data(args.olddatabase, args.newdatabase, new_db_schema,
                 keep_orphans=args.keep_orphans, verbose=args.verbose)
    
