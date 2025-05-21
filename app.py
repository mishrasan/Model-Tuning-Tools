from flask import Flask, render_template, request
import os
import pandas as pd
import io

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    message = ""
    footer = "© 2025 Your Company Name - All rights reserved"

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'signia':
            # SIGNIA Logic
            try:
                excel_hd_file = request.files['excel_hd']
                excel_dat_file = request.files['excel_dat']
                base_input_path = request.form['base_input_path'].strip()
                output_path = request.form['output_path'].strip()

                if not os.path.isdir(base_input_path):
                    message = "❌ Base input folder not found."
                    return render_template('index.html', message=message, footer=footer)

                if not os.path.isdir(output_path):
                    message = "❌ Output folder not found."
                    return render_template('index.html', message=message, footer=footer)

                df_hd = pd.read_excel(io.BytesIO(excel_hd_file.read()))
                df_dat = pd.read_excel(io.BytesIO(excel_dat_file.read()))
                df_hd.columns = df_hd.columns.str.strip()
                df_dat.columns = df_dat.columns.str.strip()

                # HD Generation
                for idx, row in df_hd.iterrows():
                    try:
                        folder = str(row.iloc[14]).strip()
                        subfolder = str(row.iloc[16]).strip()
                        if pd.isna(folder) or pd.isna(subfolder):
                            continue
                        site_id = str(row['SITE_ID']).strip()
                        if not site_id or site_id.lower() == 'nan':
                            site_id = f"row_{idx+1}"
                        main_path = os.path.join(output_path, folder)
                        sub_path = os.path.join(main_path, subfolder)
                        os.makedirs(sub_path, exist_ok=True)
                        row_data = row.drop(index=row.index[16])
                        hd_file = os.path.join(sub_path, f"{site_id}.HD")
                        with open(hd_file, 'w', encoding='utf-8') as f:
                            for col, val in zip(df_hd.columns, row_data):
                                f.write(f"{col:<20} {val}\n")
                    except Exception as e:
                        print(f"Error in HD row {idx+1}: {e}")

                # DAT Generation
                for idx, row in df_dat.iterrows():
                    try:
                        site_name = str(row['SITE NAME']).strip()
                        band = str(row['Band']).strip()
                        cell_name = str(row['Cell Name']).strip()
                        pci_value = int(row['PCI'])

                        site_folder_path = os.path.join(base_input_path, site_name)
                        band_folder_path = os.path.join(site_folder_path, band)
                        if not os.path.isdir(band_folder_path):
                            continue

                        excel_inside = None
                        for file in os.listdir(band_folder_path):
                            if file.endswith('.xls') or file.endswith('.xlsx'):
                                excel_inside = os.path.join(band_folder_path, file)
                                break
                        if not excel_inside:
                            continue

                        df_internal = pd.read_excel(excel_inside)
                        df_internal.columns = df_internal.columns.str.strip()
                        if not {'bin_lat', 'bin_lon', 'RSRP', 'ServingCellID'}.issubset(df_internal.columns):
                            continue

                        dat_output_path = os.path.join(output_path, band, site_name)
                        os.makedirs(dat_output_path, exist_ok=True)
                        dat_file_path = os.path.join(dat_output_path, f"{cell_name}.DAT")

                        with open(dat_file_path, 'w', encoding='utf-8') as f:
                            for _, data_row in df_internal.iterrows():
                                try:
                                    if int(data_row['ServingCellID']) != pci_value:
                                        continue
                                    lon = float(data_row['bin_lon'])
                                    lat = float(data_row['bin_lat'])
                                    rsrp = float(data_row['RSRP'])
                                    f.write(f"{lon:.6f} {lat:.6f} {rsrp:.1f}\n")
                                except:
                                    continue
                    except Exception as e:
                        print(f"Error in DAT row {idx+1}: {e}")

                message = "✅ Signia files successfully generated!"

            except Exception as e:
                message = f"❌ Error in Signia: {e}"

        elif action == 'excel_combiner':
            # EXCEL COMBINER Logic (Fixed)
            try:
                excel_file = request.files['excel_combiner_file']
                output_path = request.form['output_combiner_path'].strip()

                # Make sure output_path includes filename (e.g., endswith .xlsx)
                if not output_path.lower().endswith('.xlsx'):
                    message = "❌ Output path must be a full path including filename ending with .xlsx"
                    return render_template('index.html', message=message, footer=footer)

                # Load ExcelFile object once
                df_excel = pd.ExcelFile(io.BytesIO(excel_file.read()))
                sheet_names = df_excel.sheet_names

                if len(sheet_names) < 2:
                    message = "❌ Excel must have at least two sheets."
                    return render_template('index.html', message=message, footer=footer)

                # Rewind file for each read
                excel_file.seek(0)
                raw_sheet2 = pd.read_excel(excel_file, sheet_name=sheet_names[1], header=None)
                header_row = raw_sheet2.iloc[5].tolist()

                combined_df = pd.DataFrame(columns=['Cell Name'] + header_row)

                for sheet_name in sheet_names[1:]:
                    excel_file.seek(0)
                    df_raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                    a2_value = df_raw.iloc[1, 0]
                    df_data = df_raw.drop(index=range(6)).reset_index(drop=True)
                    df_data = df_data.iloc[:, :len(header_row)]
                    df_data.columns = header_row
                    df_data.insert(0, 'Cell Name', a2_value)
                    combined_df = pd.concat([combined_df, df_data], ignore_index=True)

                combined_df.to_excel(output_path, index=False)
                message = f"✅ Excel combined file saved to: {output_path}"

            except Exception as e:
                message = f"❌ Error combining excels: {e}"

        elif action == 'dat_maker':
            # DAT MAKER Logic
            try:
                dat_file = request.files['dat_maker_file']
                output_folder = request.form['dat_maker_output_path'].strip()

                if not os.path.isdir(output_folder):
                    message = "❌ DAT Maker output folder not found."
                    return render_template('index.html', message=message, footer=footer)

                df = pd.read_excel(io.BytesIO(dat_file.read()))

                # Filter rows where 11th column (index 10) is blank
                filtered_df = df[df.iloc[:, 10].isna()]

                for cell_name in filtered_df['Cell Name'].dropna().unique():
                    cell_df = filtered_df[filtered_df['Cell Name'] == cell_name]
                    selected_data = cell_df.iloc[:, [2, 3, 5]]  # C, D, F columns

                    output_file = os.path.join(output_folder, f"{cell_name}.dat")
                    selected_data.to_csv(output_file, index=False, header=False, sep='\t')

                message = "✅ DAT files generated successfully!"

            except Exception as e:
                message = f"❌ Error generating DAT files: {e}"

        else:
            message = "❌ Unknown action."

    return render_template('index.html', message=message, footer=footer)


if __name__ == '__main__':
    app.run(debug=True)
