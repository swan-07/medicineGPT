import json

def check_user_genome(uploaded_file):
  json_file_path = 'Nevi_hashmap.json'
  with open(json_file_path) as json_file:
    rsid_data = json.load(json_file)

  matching_rsids = []

  # Process the user's genome file
  for line in uploaded_file:
    # print(line)
    user_data = line.strip().split('\t')
    # print(user_data)
    user_rsid, user_genotype = user_data[0], user_data[3]

    # Compare user's genotype with JSON data
    if user_rsid in rsid_data:
      json_positive_genotype = rsid_data[user_rsid]['Positive Genotype']
      if user_genotype == json_positive_genotype:
        matching_rsids.append(user_rsid)

  return matching_rsids


print(check_user_genome((open('8.23andme.2.txt.tsv', 'r'))))