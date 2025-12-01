import csv

def Generate_Seeds(filepath):
    titles = []
    total_entries = 0
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        if 'Title' not in reader.fieldnames:
            raise ValueError("Seeds.csv file is missing the Title column")
        for row in reader:
            titles.append(row["Title"].strip())
            total_entries += 1

    empty_indices = [index for index, title in enumerate(titles) if not title]
    print(f"Total Resulted titles: {len(titles)}. \n \
          All titles received: {'Yes' if (len(titles) == total_entries) else 'Not all titles have been read'}\n \
          {empty_indices if empty_indices else ''}")
    return titles