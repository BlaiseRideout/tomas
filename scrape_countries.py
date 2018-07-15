#!/usr/bin/env python3

__doc__ = """Scrape a web table containing country codes and flag images
such as https://en.wikipedia.org/wiki/Comparison_of_alphabetic_country_codes
"""
import argparse, sys, re, csv, subprocess

def scrape(URL, start_pattern=None, end_pattern=None, delimiter_pattern=None,
           row_end_pattern=None, ignore_line_pattern=None, remove_pattern=None,
           verbose=0, columns=[], output=sys.stdout):
    if not (start_pattern and end_pattern and delimiter_pattern and
            row_end_pattern and ignore_line_pattern and remove_pattern):
        return
    writer = csv.writer(output)
    in_table = False
    row = []
    for line in subprocess.run(
            ['curl', URL], 
            check=True, stdout=subprocess.PIPE).stdout.decode().split('\n'):
        if ignore_line_pattern.match(line):
            continue
        if in_table:
            if end_pattern.search(line):
                return
        else:
            in_table = start_pattern.search(line)
        if in_table:
            row.extend([remove_pattern.sub('', col)
                        for col in delimiter_pattern.split(line)])
            if row_end_pattern.search(line):
                output = clean_output_row(
                    [row[i] for i in columns] if columns else row,
                    row)
                writer.writerow(output)
                row = []

def clean_output_row(row, original):
    # Find missing country codes by filling in with another code, if available
    if row[1] == '':
        for f in row[2:] + original:
            if len(f) == 3:
                row[1] = f.upper()
                break
    # If that didn't work, try using the first three non-whitespace characters
    # of the country's full name
    if row[1] == '' and len(row[0]) > 2:
        row[1] = ''.join(c.upper() for c in row[0] if not c.isspace())[0:3]
    return row

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'source', nargs='*',
        help='Source URL for table')
    parser.add_argument(
        '-s', '--start-pattern', default=r'<td><span class="flagicon">',
        help='Regular expression used to find the first row of the table to '
        'scrape')
    parser.add_argument(
        '-e', '--end-pattern', default=r'</table>',
        help='Regular expression used to find the end of the table to scrape')
    parser.add_argument(
        '-d', '--delimiter-pattern', default=r'<td[^>]*>',
        help='Regular expression used to find delimiter separating table '
        'columns')
    parser.add_argument(
        '-r', '--row-end-pattern', default=r'</tr>',
        help='Regular expression used to find ends of rows in table')
    parser.add_argument(
        '-c', '--column', nargs='*', default=[3, 9, 5, 4, 1],
        help='Column index of column to keep in output.'
        'Provide multiple columns in the order they should appear in the'
        'output CSV')
    parser.add_argument(
        '-i', '--ignore-line-pattern', default=r'^</?tr>$',
        help='Regular expression used to ignore lines from scrape')
    parser.add_argument(
        '-R', '--remove-pattern', 
        default=r'</?(?!img\b)[^>]*>|&#91;\d+&#93;',
        help='Regular expression to be removed from values in table cells')
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help='Add verbose comments')
    args = parser.parse_args()

    config = {'verbose': args.verbose, 'columns': args.column}
    for pattern in args.__dict__:
        if pattern.endswith('_pattern'):
            config[pattern] = re.compile(args.__dict__[pattern], re.IGNORECASE)

    for URL in args.source:
        scrape(URL, **config)

