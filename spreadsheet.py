#!/usr/bin/env python3

import re
import logging
import sqlite3
import os.path
from collections import *

import tornado.web
import openpyxl
import tempfile
import handler
import db
import tournament

log = logging.getLogger('WebServer')

Player_Columns = [f.capitalize() for f in tournament.player_fields
                     if f not in ('id', 'countryid', 'flag_image')]
excel_mime_type = '''
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'''.strip()

top_center_align = openpyxl.styles.Alignment(
   horizontal='center', vertical='top', wrap_text=True)
title_font = openpyxl.styles.Font(name='Arial', size=14, bold=True)
column_header_font = openpyxl.styles.Font(name='Arial', size=12, bold=True)
no_border = openpyxl.styles.Border()
thin_outline = openpyxl.styles.Border(
   outline=openpyxl.styles.Side(border_style="thin")
)
min_column_width = 10

def merge_cells(sheet, row, column, height=1, width=1, 
                font=title_font, align=top_center_align, border=no_border):
   if height > 1 or width > 1:
      sheet.merge_cells(
         start_row=row, start_column=column,
         end_row=row + height -1, end_column=column + width - 1)
   top_left = sheet.cell(row=row, column=column)
   top_left.alignment = align
   top_left.font = font
   top_left.border = border
   return top_left

class DownloadTournamentSheetHandler(handler.BaseHandler):
    @handler.tournament_handler
    def get(self):
        players = tournament.getPlayers(self.tournamentid)
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.title = 'Players'
        header_row = 3
        first_column = 1
        row = header_row
        widths = defaultdict(lambda: min_column_width)
        merge_cells(sheet, header_row - 2, first_column, 1, len(Player_Columns),
                    font=title_font, border=thin_outline).value=(
                       '{} Players'.format(self.tournamentname))
        sheet.row_dimensions[header_row - 2].height = title_font.size * 3 // 2
        for i, column in enumerate(Player_Columns):
            cell = merge_cells(sheet, row, first_column + i, 1, 1,
                               font=column_header_font)
            cell.value = column
            widths[cell.column_letter] = max(
                widths[cell.column_letter], 
                len(column) * column_header_font.size // 10)
        for player in players:
            row += 1
            for i, f in enumerate(Player_Columns):
                cell = sheet.cell(row=row, column=first_column + i,
                                  value=player[f.lower()])
                widths[cell.column_letter] = max(
                    widths[cell.column_letter], len(str(player[f.lower()])))
        for col in range(first_column, first_column + len(Player_Columns)):
            letter = openpyxl.utils.cell.get_column_letter(col)
            sheet.column_dimensions[letter].width = widths[letter]
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
