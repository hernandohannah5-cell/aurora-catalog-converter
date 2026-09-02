import pandas as pd
import re
import streamlit as st
import pdfplumber

st.set_page_config(page_title="Catalog Data Merger", layout="wide")
st.title("📦 Aurora Catalog CSV Converter (Smart PDF + Excel)")

col1, col2 = st.columns(2)
with col1:
    uploaded_excel = st.file_uploader("1. Upload Excel File (Primary)", type=["xlsx"])
with col2:
    uploaded_pdf = st.file_uploader("2. Upload PDF Catalog (Optional)", type=["pdf"])

def normalize_sku_key(sku):
    if not sku:
        return ""
    sku_str = str(sku).strip().upper()
    return re.sub(r'^[AX]JE', 'JE', sku_str)

def clean_cct(val):
    if pd.isna(val):
        return ''
    clean_str = str(val).replace('•', '').replace('\r', ' ').replace('\n', ' ')
    clean_str = re.sub(r'\s+', ' ', clean_str).strip()
    return clean_str

def parse_beam_angles(val):
    """ Extract individual numbers from beam string into a 4-item list """
    if pd.isna(val):
        return ['', '', '', '']
    # Clean text and split by spaces, commas, degrees, or newlines
    clean_str = str(val).replace('•', '').replace('˚', '').replace('°', '').replace('\r', ' ')
    # Extract only digit sequences (e.g., '15', '24', '36', '50')
    angles = re.findall(r'\b\d+\b', clean_str)
    while len(angles) < 4:
        angles.append('')
    return angles[:4]

pdf_extra_data = {}

if uploaded_pdf:
    try:
        with pdfplumber.open(uploaded_pdf) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                sku_matches = list(re.finditer(r'([AX]JE[0-9]{4,5}[A-Za-z0-9]*)\b', text))
                
                for match in sku_matches:
                    raw_sku = match.group(1).strip()
                    norm_key = normalize_sku_key(raw_sku)
                    
                    flex_val = 'Fixed'
                    if raw_sku.endswith('A') or 'A' in raw_sku[7:]:
                        flex_val = 'Adjustable'
                    
                    mount_val = 'Recessed'
                    start_pos = match.start()
                    snippet = text[start_pos:start_pos + 600]
                    
                    volt_match = re.search(r'([0-9]{2}\-[0-9]{2}\s*V|[0-9]{2}\s*V)', snippet, re.IGNORECASE)
                    curr_match = re.search(r'([0-9]{3}\s*mA)', snippet, re.IGNORECASE)
                    
                    volt_val = volt_match.group(1).replace(' ', '') if volt_match else ''
                    curr_val = curr_match.group(1).replace(' ', '') if curr_match else ''
                    
                    pdf_extra_data[norm_key] = {
                        'Flex': flex_val,
                        'Mounting': mount_val,
                        'Voltage': volt_val,
                        'Current': curr_val
                    }
                    
        st.success(f"📄 Smart PDF Extracted: Successfully mapped {len(pdf_extra_data)} SKUs!")
    except Exception as e:
        st.warning(f"Could not parse PDF completely: {e}")

if uploaded_excel:
    try:
        df_raw = pd.read_excel(uploaded_excel, header=8)
        df_raw.columns = df_raw.iloc[0]
        df_raw = df_raw.iloc[2:].reset_index(drop=True)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]

        if 'S/R' in df_raw.columns:
            df_raw['S/R'] = df_raw['S/R'].ffill()

        df_clean = df_raw[df_raw['Item code'].notna() & (df_raw['Item code'] != '')].copy()

        def clean_series_title(val):
            if pd.isna(val):
                return ''
            first_line = str(val).split('\n')[0]
            clean = re.sub(r'[•\r]', '', first_line).strip()
            return clean

        pivoted_rows = []
        beam_col = [c for c in df_clean.columns if 'beam' in c.lower() or 'angle' in c.lower()]
        
        for series_name, group in df_clean.groupby('S/R', sort=False):
            clean_title = clean_series_title(series_name)
            group_items = group.to_dict('records')
            
            for chunk_idx in range(0, len(group_items), 4):
                chunk = group_items[chunk_idx:chunk_idx + 4]
                page_row = {'Series_Title': clean_title}
                
                # Get beam angles from the first valid product in this series/chunk
                first_beam_raw = chunk[0].get(beam_col[0], '') if beam_col else ''
                b_angles = parse_beam_angles(first_beam_raw)
                
                # Assign explicitly: Beam 1 -> A, Beam 2 -> B, Beam 3 -> C, Beam 4 -> D
                page_row['A'] = b_angles[0]
                page_row['B'] = b_angles[1]
                page_row['C'] = b_angles[2]
                page_row['D'] = b_angles[3]
                
                for i, item in enumerate(chunk, start=1):
                    idx = f"{i:02d}"
                    raw_sku = str(item.get('Item code', '')).strip()
                    norm_key = normalize_sku_key(raw_sku)
                    
                    page_row[f'SKU_{idx}'] = raw_sku
                    page_row[f'Power_{idx}'] = str(item.get('Output Power', '')).strip()
                    page_row[f'Lumen_{idx}'] = str(item.get('Delivered Lumen', '')).strip()
                    page_row[f'Cutout_{idx}'] = str(item.get('Cutout size', '')).strip()
                    page_row[f'CCT_{idx}'] = clean_cct(item.get('CCT', ''))
                    
                    pdf_info = pdf_extra_data.get(norm_key, {})
                    auto_flex = 'Adjustable' if ('A' in raw_sku[7:] or raw_sku.endswith('A')) else 'Fixed'
                    page_row[f'Flex_{idx}'] = pdf_info.get('Flex') or item.get('Flex', auto_flex)
                    page_row[f'Mount_{idx}'] = pdf_info.get('Mounting') or item.get('Mounting', 'Recessed')
                    
                    page_row[f'Voltage_{idx}'] = pdf_info.get('Voltage') or str(item.get('LED Voltage', '')).strip()
                    page_row[f'Current_{idx}'] = pdf_info.get('Current') or str(item.get('LED Current', '')).strip()
                    
                    page_row[f'@Image_{idx}'] = f"Images/{raw_sku}.png"
                    
                pivoted_rows.append(page_row)

        df_pivoted = pd.DataFrame(pivoted_rows)
        csv_data = df_pivoted.to_csv(index=False, encoding='utf-8-sig')

        st.success("✅ Fixed Beam Angle Mapping!")
        st.download_button(
            label="📥 Download Corrected CSV File",
            data=csv_data,
            file_name="pivoted_catalog_data_v11.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Error processing file: {e}")
