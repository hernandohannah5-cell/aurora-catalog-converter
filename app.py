import pandas as pd
import re
import os

def get_beam_svg_path(angle_val):
    """
    Maps beam angle degree values to SVG icon paths:
    - 15° to 25° -> Links/Icons/Beam_15_25.svg
    - 26° to 40° -> Links/Icons/Beam_26_40.svg
    - 41° to 60° -> Links/Icons/Beam_41_60.svg
    - > 60°      -> Links/Icons/Beam_Wide.svg
    - Text/Blank -> Handled dynamically
    """
    if pd.isna(angle_val) or str(angle_val).strip() == "":
        return ""
    
    val_str = str(angle_val).strip()
    
    # Extract numerical degree value
    nums = re.findall(r'\d+', val_str)
    if nums:
        deg = int(nums[0])
        if 15 <= deg <= 25:
            return "Links/Icons/Beam_15_25.svg"
        elif 26 <= deg <= 40:
            return "Links/Icons/Beam_26_40.svg"
        elif 41 <= deg <= 60:
            return "Links/Icons/Beam_41_60.svg"
        elif deg > 60:
            return "Links/Icons/Beam_Wide.svg"
    
    # Fallback for text-based beam angles (e.g., Wide Beam / Narrow Beam)
    if "wide" in val_str.lower():
        return "Links/Icons/Beam_Wide.svg"
    elif "narrow" in val_str.lower():
        return "Links/Icons/Beam_Narrow.svg"
        
    return "Links/Icons/Beam_Default.svg"


def process_catalog_data(input_file, output_csv="InDesign_DataMerge_33Cols.csv"):
    """
    Processes source Excel/CSV and outputs a clean 33-column CSV 
    tailored for Omar's InDesign Data Merge template.
    """
    df = pd.read_excel(input_file) if input_file.endswith(('.xlsx', '.xls')) else pd.read_csv(input_file)
    
    # Target 33 Columns defined in Omar's reference sheet
    target_columns = [
        'S/R  "Item Code"', 'Name', 'Power_Main', 'CCT', 'Lumen_Main', 
        'LED_Current', 'LED_Voltage', 'Cut-out_Main', 'Lifetime', 'LED_Brand', 
        'IP_rate', 'CRI', 'SDCM', 'UGR', 
        'Beam_A', 'Beam_B', 'Beam_C', 'Beam_D', 
        'SKU_Varient', 'Cut-out_Varient', 'power_Varient', 'lumen_Varient', 
        'Flex_Varient', 'Mounting_Varient', 'Driver_Main', 
        'F_main', 'R_Main', 'B_Main', 'E_main', 
        'F_Answer', 'R_Answer', 'B_Answer', 'A_Answer'
    ]
    
    processed_rows = []
    group_col = 'S/R  "Item Code"' if 'S/R  "Item Code"' in df.columns else df.columns[0]
    
    for series_id, group in df.groupby(group_col, sort=False):
        row_dict = {col: "" for col in target_columns}
        first_row = group.iloc[0]
        
        # 1. Main Specs Mapping
        row_dict['S/R  "Item Code"'] = str(series_id) if pd.notna(series_id) else ""
        row_dict['Name'] = str(first_row.get('Name', '')) if pd.notna(first_row.get('Name')) else ""
        row_dict['Power_Main'] = str(first_row.get('Power_Main', '')) if pd.notna(first_row.get('Power_Main')) else ""
        row_dict['CCT'] = str(first_row.get('CCT', '')) if pd.notna(first_row.get('CCT')) else ""
        row_dict['Lumen_Main'] = str(first_row.get('Lumen_Main', '')) if pd.notna(first_row.get('Lumen_Main')) else ""
        row_dict['LED_Current'] = str(first_row.get('LED_Current', '')) if pd.notna(first_row.get('LED_Current')) else ""
        row_dict['LED_Voltage'] = str(first_row.get('LED_Voltage', '')) if pd.notna(first_row.get('LED_Voltage')) else ""
        row_dict['Cut-out_Main'] = str(first_row.get('Cut-out_Main', '')) if pd.notna(first_row.get('Cut-out_Main')) else ""
        row_dict['Lifetime'] = str(first_row.get('Lifetime', '')) if pd.notna(first_row.get('Lifetime')) else ""
        row_dict['LED_Brand'] = str(first_row.get('LED_Brand', '')) if pd.notna(first_row.get('LED_Brand')) else ""
        row_dict['IP_rate'] = str(first_row.get('IP_rate', '')) if pd.notna(first_row.get('IP_rate')) else ""
        row_dict['CRI'] = str(first_row.get('CRI', '')) if pd.notna(first_row.get('CRI')) else ""
        row_dict['SDCM'] = str(first_row.get('SDCM', '')) if pd.notna(first_row.get('SDCM')) else ""
        
        # UGR Icon Logic (Blank if empty)
        ugr_val = first_row.get('UGR', '')
        row_dict['UGR'] = "Links/Icons/UGR19.svg" if pd.notna(ugr_val) and str(ugr_val).strip() != "" else ""

        # 2. Dynamic Beam Angle Logic (Sort Smallest -> Largest and Map to Beam_A .. Beam_D)
        angles = []
        for angle_col in ['Beam_A', 'Beam_B', 'Beam_C', 'Beam_D']:
            if angle_col in group.columns:
                vals = group[angle_col].dropna().unique()
                for v in vals:
                    if str(v).strip() != "":
                        angles.append(str(v).strip())
        
        def extract_deg(a):
            m = re.findall(r'\d+', a)
            return int(m[0]) if m else 999
            
        unique_angles = sorted(list(set(angles)), key=extract_deg)
        
        beam_keys = ['Beam_A', 'Beam_B', 'Beam_C', 'Beam_D']
        for idx, key in enumerate(beam_keys):
            if idx < len(unique_angles):
                row_dict[key] = get_beam_svg_path(unique_angles[idx])
            else:
                row_dict[key] = "" # Blank cell triggers frame auto-hide in InDesign

        # 3. Main Driver & Features
        row_dict['Driver_Main'] = str(first_row.get('Driver_Main', '')) if pd.notna(first_row.get('Driver_Main')) else ""
        
        for icon_col in ['F_main', 'R_Main', 'B_Main', 'E_main']:
            val = first_row.get(icon_col, '')
            row_dict[icon_col] = f"Links/Icons/{icon_col}.svg" if pd.notna(val) and str(val).strip() != "" else ""

        for ans_col in ['F_Answer', 'R_Answer', 'B_Answer', 'A_Answer']:
            row_dict[ans_col] = str(first_row.get(ans_col, '')) if pd.notna(first_row.get(ans_col)) else ""

        # 4. Variant Info
        skus = [str(s) for s in group.get('SKU_Varient', group.iloc[:, 0]).dropna().tolist() if str(s).strip() != ""]
        row_dict['SKU_Varient'] = ", ".join(skus[:4])
        
        processed_rows.append(row_dict)

    result_df = pd.DataFrame(processed_rows, columns=target_columns)
    result_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    return result_df
