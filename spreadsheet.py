#!/usr/bin/env python3

import re
import logging
import sqlite3
import os.path
from collections import *
import math

import tornado.web
import openpyxl
import tempfile
import handler
import db
import tournament
import seating
import leaderboard

log = logging.getLogger('WebServer')

Player_Columns = [f.capitalize() for f in tournament.player_fields
                     if f not in ('id', 'countryid', 'flag_image')]
excel_mime_type = '''
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'''.strip()

# OpenPyXL formatting definitions
top_center_align = openpyxl.styles.Alignment(
   horizontal='center', vertical='top', wrap_text=True)
title_font = openpyxl.styles.Font(name='Arial', size=14, bold=True)
default_font = openpyxl.styles.Font()
column_header_font = openpyxl.styles.Font(name='Arial', size=12, bold=True)
no_border = openpyxl.styles.Border()
thin_outline = openpyxl.styles.Border(
   outline=openpyxl.styles.Side(border_style="thin")
)
paleGreenFill = openpyxl.styles.fills.PatternFill(
    patternType='solid', fgColor="DDFFDD", fill_type='solid')
paleBlueFill = openpyxl.styles.fills.PatternFill(
    patternType='solid', fgColor="DDDDFF", fill_type='solid')

def merge_cells(sheet, row, column, height=1, width=1, 
                font=title_font, align=top_center_align, border=no_border,
                value=None):
   if height > 1 or width > 1:
      sheet.merge_cells(
         start_row=row, start_column=column,
         end_row=row + height -1, end_column=column + width - 1)
   top_left = sheet.cell(row=row, column=column)
   top_left.alignment = align
   top_left.font = font
   top_left.border = border
   if value:
       top_left.value = value
   return top_left

def resizeColumn(sheet, column, min_row=None, max_row=None, characterWidth=1):
    width = 0
    for value in sheet.iter_rows(
            min_col=column, max_col=column, min_row=min_row, max_row=max_row,
            values_only=True):
        width = max(width, len(str(value)))
    letter = openpyxl.utils.cell.get_column_letter(column)
    sheet.column_dimensions[letter].width = int(
        math.ceil(width * characterWidth))
        
def makePlayersSheet(book, tournamentID, tournamentName, sheet=None):
    if sheet is None:
        sheet = book.create_sheet()
    sheet.title = 'Players'
    players = tournament.getPlayers(tournamentID)
    header_row = 3
    first_column = 1
    row = header_row
    columns = Player_Columns + ['Tournament']
    merge_cells(sheet, header_row - 2, first_column, 1, len(columns),
                font=title_font, border=thin_outline,
                value='{} Players'.format(tournamentName))
    sheet.row_dimensions[header_row - 2].height = title_font.size * 3 // 2
    for i, column in enumerate(columns):
        cell = sheet.cell(row=row, column=first_column + i, value = column)
        cell.font = column_header_font
        cell.alignment = top_center_align
    for player in players:
        row += 1
        for i, f in enumerate(columns):
            cell = sheet.cell(
                row=row, column=first_column + i,
                value=tournamentName if f == 'Tournament'
                else player[f.lower()])
    for col in range(first_column, first_column + len(columns)):
        resizeColumn(sheet, col, min_row=header_row)
    return sheet

def makeSettingsSheet(book, tournamentID, tournamentName, sheet=None):
    if sheet is None:
        sheet = book.create_sheet() 
    sheet.title = 'Settings'
    tmt_fields = [f for f in db.table_field_names('Tournaments')
                  if f not in ('Id', 'Name', 'Country', 'Owner')]
    rounds_fields = [f for f in db.table_field_names('Rounds') 
                     if f not in ('Id', 'Tournament')]
    query_fields = ['Countries.Code', 'Email'] + [
        'Tournaments.{}'.format(f) for f in tmt_fields] + [
        'Rounds.{}'.format(f) for f in rounds_fields]
    round_display_fields = [
        'Name', 'Number', 'Ordering', 'Algorithm', 'CutSize', 'Games']
    sql = """
    SELECT {} FROM Tournaments
      LEFT OUTER JOIN Countries ON Countries.Id = Tournaments.Country
      LEFT OUTER JOIN Users ON Users.Id = Tournaments.Owner
      LEFT OUTER JOIN Rounds ON Rounds.Tournament = Tournaments.Id
    WHERE Tournaments.Id = ?
    """.strip().format(','.join(query_fields))
    args = (tournamentID,)
    with db.getCur() as cur:
        cur.execute(sql, args)
        rounds = [dict(zip(map(db.fieldname, query_fields), row))
                  for row in cur.fetchall()]
    header_row = 3
    first_column = 1
    row = header_row
    merge_cells(sheet, header_row - 2, first_column, 
                1, max(2, len(round_display_fields)),
                font=title_font, border=thin_outline,
                value='{} Settings'.format(tournamentName))
    sheet.row_dimensions[header_row - 2].height = title_font.size * 3 // 2
    top_left = first_column + (len(round_display_fields) - 2) // 2
    for field in tmt_fields + ['Code']:
        if field not in ('Name', ):
            namecell = sheet.cell(
                row=row, column=top_left,
                value='Country ' + field if field == 'Code' else
                'Owner ' + field if field == 'Email' else field)
            valuecell = sheet.cell(row=row, column=top_left + 1,
                                   value=rounds[0][field])
            row += 1
    row += 2
    for i, field in enumerate(round_display_fields):
        cell = sheet.cell(
            row = row, column = first_column + i,
            value = 'Seating Algorithm' if field == 'Algortihm' else
            'Cut Size' if field == 'CutSize' else
            'Round Name' if field == 'Name' else
            'Round Number' if field == 'Number' else
            field)
        cell.font = column_header_font
        cell.alignment = top_center_align
    if len(rounds) == 1 and not rounds[0].Name:
        row += 1
        merge_cells(sheet, row, first_column, 1,
                    len(round_display_fields), font=default_font,
                    value='No rounds defined')
    else:
        for round in rounds:
            row += 1
            for i, field in enumerate(round_display_fields):
                cell = sheet.cell(
                    row = row, column = first_column + i,
                    value = seating.ALGORITHMS[round[field] or 0].name
                    if field == 'Algorithm' else
                    seating.ORDERINGS[round[field] or 0][0]
                    if field == 'Orderings' else
                    round[field])
    for col in range(first_column, 
                     first_column + max(2, len(round_display_fields))):
        resizeColumn(sheet, col, min_row = header_row)

def makeScoresSheet(book, tournamentID, tournamentName, sheet=None):
    if sheet is None:
        sheet = book.create_sheet() 
    sheet.title = 'All Scores'
    player_fields = ['Name', 'Country', 'Status']
    round_display_fields = ['Rank', 'Points', 'Penalty', 'Total']
    scoreboard, rounds = leaderboard.getTournamentScores(tournamentID)
    header_row = 3
    first_column = 1
    total_columns = len(player_fields) + len(round_display_fields) * len(rounds)
    row = header_row
    roundColorFills = [paleGreenFill, paleBlueFill]
    merge_cells(sheet, header_row - 2, first_column, 
                1, min(total_columns, 20),
                font=title_font, border=thin_outline,
                value='{} Scores'.format(tournamentName))
    sheet.row_dimensions[header_row - 2].height = title_font.size * 3 // 2
    for i, field in enumerate(player_fields):
        cell = sheet.cell(
            row = row + 1, column = first_column + i, value = field)
        cell.font = column_header_font
        cell.alignment = top_center_align
    col = first_column + len(player_fields)
    color = 0
    for roundID, roundName in rounds:
        round_cell = merge_cells(
            sheet, row, col, 1, len(round_display_fields), value=roundName)
        round_cell.fill = roundColorFills[color]
        for j, rfield in enumerate(round_display_fields):
            cell = sheet.cell(row = row + 1, column = col + j, value=rfield)
            cell.font = column_header_font
            cell.alignment = top_center_align
            cell.fill = roundColorFills[color]
        col += len(round_display_fields)
        color = 1 - color
    row += 1
    for player in scoreboard:
        row += 1
        for i, field in enumerate(player_fields):
            cell = sheet.cell(
                row = row, column = first_column + i, 
                value = player['type' if field == 'Status' else field.lower()])
        col = first_column + len(player_fields)
        color = 0
        for roundID, roundName in rounds:
            for j, rfield in enumerate(round_display_fields):
                cell = sheet.cell(
                    row = row, column = col + j,
                    value=player['scores'][roundID][
                        'score' if rfield == 'Points' else rfield.lower()])
                cell.fill = roundColorFills[color]
            col += len(round_display_fields)
            color = 1 - color
        
    for col in range(first_column, first_column + total_columns):
        resizeColumn(sheet, col, min_row = header_row)
       
class DownloadTournamentSheetHandler(handler.BaseHandler):
    @handler.tournament_handler
    def get(self):
        book = openpyxl.Workbook()
        playersSheet = makePlayersSheet(
            book, self.tournamentid, self.tournamentname, book.active)
        scoresSheet = makeScoresSheet(
            book, self.tournamentid, self.tournamentname)
        settingsSheet = makeSettingsSheet(
            book, self.tournamentid, self.tournamentname)
        with tempfile.NamedTemporaryFile(
                suffix='.xlsx',
                prefix='{}_'.format(self.tournamentname)) as outf:
            book.save(outf.name)
            outf.seek(0)
            self.write(outf.read())
            self.set_header('Content-type', excel_mime_type)
            self.set_header(
                'Content-Disposition',
                'attachment; filename="{}"'.format(os.path.basename(outf.name)))
            log.debug('Temporary file: {}'.format(outf.name))
        return

class UploadPlayersHandler(handler.BaseHandler):
    @handler.tournament_handler_ajax
    @handler.is_owner_ajax
    def post(self):
        if 'file' not in self.request.files or len(self.request.files['file']) == 0:
            return self.write({'status':"error", 'message':"Please provide a players file"})
        players = self.request.files['file'][0]['body']
        colnames = [c.lower() for c in Player_Columns]
        try:
            with db.getCur() as cur:
                reader = csv.reader(players.decode('utf-8').splitlines())
                good = 0
                bad = 0
                first = True
                unrecognized = []
                for row in reader:
                    hasheader = first and sum(
                        1 if v.lower() in colnames else 0 for v in row) >= len(row) - 1
                    first = False
                    if hasheader:
                        unrecognized = [v for v in row
                                        if v.lower() not in colnames]
                        colnames = [v.lower() for v in row]
                        colnames += [c.lower() for c in Player_Columns
                                     if c.lower() not in colnames]
                        continue
                    if len(row) < 3:
                        bad += 1;
                        continue
                    filled = 0
                    for i in range(len(row)):
                        if row[i] == '':
                            row[i] = None
                        else:
                            filled += 1
                    if filled < 3:
                        bad += 1
                        continue
                    rowdict = dict(zip(
                        colnames, list(row) + [None] * len(colnames)))
                    if not (rowdict['name'] or
                            (rowdict['number'] and
                             not rowdict['number'].isdigit()) or
                            (rowdict['type'] and
                             not rowdict['type'] in db.playertypes)):
                        bad += 1
                        continue
                    rowdict['type'] = db.playertypecode[rowdict['type']] if (
                        rowdict['type'] in db.playertypecode) else 0
                    cur.execute(
                        "INSERT INTO Players(Name, Number, Country, "
                        "                    Association, Pool, Type, Wheel, Tournament)"
                        " VALUES(?, ?,"
                        "   (SELECT Id FROM Countries"
                        "      WHERE Name = ? OR Code = ? OR IOC_Code = ?),"
                        "   ?, ?, ?, ?, ?);",
                        (rowdict['name'], rowdict['number'], rowdict['country'],
                         rowdict['country'], rowdict['country'],
                         rowdict['association'], rowdict['pool'],
                         rowdict['type'], rowdict['wheel'], self.tournamentid))
                    good += 1
            message = ("{} player record(s) loaded, "
                       "{} player record(s) skipped").format(good,bad)
            if unrecognized:
                message += ", skipped column header(s): {}".format(
                    ', '.join(unrecognized))
            return self.write({'status':"success", 'message': message})
        except Exception as e:
            return self.write({'status':"error",
                    'message':"Invalid players file provided: " + str(e)})
