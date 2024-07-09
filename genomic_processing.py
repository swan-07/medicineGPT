import csv

def compare_gene_conditions(file_path, output_file):
    results = []
    try:
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                rsid = row['ID']
                conditions = row['ClinVar CLNDBN']
                # Optionally, include genotype information
                genotype = row['Genotype']

                # Simplify conditions string; here we take the first condition for simplicity
                # This part might need refinement depending on the exact requirements and data quality
                main_condition = conditions.split(',')[0]
                if 'not provided' not in main_condition.lower():
                    result_string = f"{main_condition} due to {rsid}"
                    results.append(result_string)

        # Optionally, write results to an output file if needed
        with open(output_file, 'w') as f:
            for result in results:
                f.write(result + "\n")

    except Exception as e:
        print(f"Error processing file: {e}")

    return results