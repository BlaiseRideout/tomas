#!/usr/bin/env python3

__doc__ = """
Sort a CSV file of countries by the country code and move a particular
country to the end of the list.
Input is the name of the CSV file.
Outputs a new CSV to standard output.
"""

import csv, sys

filename = sys.argv[1]
last = 'SUB'
fields = ('Name', 'Code', 'IOC_Code', 'IOC_Name', 'Flag_Image')
key = 'Code'
def sortKey(country):
   return country[key]

with open(filename, "r", encoding='utf-8') as countriesfile:
   reader = csv.reader(countriesfile)
   countries = [dict(zip(fields, row)) for row in reader]
countries.sort(key=sortKey)
try:
   last_index = list(map(sortKey, countries)).index(last)
   last_country = countries[last_index]
   countries[last_index:last_index + 1] = []
   countries.append(last_country)
except ValueError:
   print('Could not find country with {} = {}'.format(key, last),
         file=sys.stderr)
writer = csv.DictWriter(sys.stdout, fields)
for country in countries:
   writer.writerow(country)
      
