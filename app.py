import pandas as pd
import re
import streamlit as st
import pdfplumber

st.set_page_config(page_title="Catalog Data Merger", layout="wide")
st.title("📦 Aurora Catalog CSV Converter (Smart SKU Match)")

col1, col2 = st.columns(2)
with col1:
    uploaded_excel = st.file_uploader("1. Upload Excel File (Primary)", type=["xlsx"])
with col2:
    uploaded_pdf = st.file_uploader("2. Upload PDF File (Optional Spec Sheet)", type=["pdf"])

def normalize_sku_key(sku):
    """ Normalize SKU so 'AJE...' and 'XJE...' match seamlessly """
    if not sku:
        return ""
    sku_str = str(sku).strip().upper()
    # Replace starting 'AJE' or 'XJE' with standard 'JE' for matching
    return re.sub(r'^[AX]JE', 'JE', sku_str)

pdf_extra_data = {}

# Process PDF only if uploaded by user
if uploaded_pdf:
    try:
        with pdfplumber.open(uploaded_pdf) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        row_str = " ".join([str(cell) for cell in row if cell])
                        
                        # Find any SKU pattern starting with AJE or XJE
                        sku_match = re.search(r'[AX]JE[A-Za-z0-9\-]+', row_str)
                        if sku_match:
                            raw_sku = sku_match.group(0).strip()
                            norm_key = normalize_sku_key(raw_sku)
                            
                            flex_val = 'Adjustable' if 'adjust' in row_str.lower() else ('Fixed' if 'fix' in row_str.lower() else '')
                            mount_val = 'Recessed' if 'recess' in row_str.lower() else ('Surface' if 'surface' in row_str.lower() else '')
                            
                            pdf_extra_data[norm_key] = {
                                'Flex': flex_val,
                                'Mounting': mount_val
                            }
        st.info(f"📄 Smart PDF Extracted: Found extra specs for {len(pdf_extra_data)} SKUs (Matching 'A' and 'X' codes).")
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

        def extract_beam_angles(val):
            if pd.isna(val):
                return ['', '', '', '']
            clean_str = str(val).replace('•', '').replace('˚', '').replace('°', '').replace('\r', '').replace('\n', ' ')
            angles = [a.strip() for a in re.split(r'[\n,]+', clean_str) if a.strip()]
            while len(angles) < 4:
                angles.append('')
            return [a.replace('\n', '').strip() for a in angles[:4]]

        beam_col = [c for c in df_clean.columns if 'beam' in c.lower() or 'angle' in c.lower()]
        if beam_col:
            beam_data = df_clean[beam_col[0]].apply(extract_beam_angles)
            beam_df = pd.DataFrame(beam_data.tolist(), columns=['Beam_A', 'Beam_B', 'Beam_C', 'Beam_D'])
            df_clean = pd.concat([df_clean.reset_index(drop=True), beam_df], axis=1)

        pivoted_rows = []
        for series_name, group in df_clean.groupby('S/R', sort=False):
            clean_title = clean_series_title(series_name)
            group_items = group.to_dict('records')
            
            for chunk_idx in range(0, len(group_items), 4):
                chunk = group_items[chunk_idx:chunk_idx + 4]
                page_row = {'Series_Title': clean_title}
                
                for i, item in enumerate(chunk, start=1):
                    idx = f"{i:02d}"
                    raw_sku = str(item.get('Item code', '')).strip()
                    norm_key = normalize_sku_key(raw_sku)
                    
                    page_row[f'SKU_{idx}'] = raw_sku
                    page_row[f'Power_{idx}'] = str(item.get('Output Power', '')).strip()
                    page_row[f'Lumen_{idx}'] = str(item.get('Delivered Lumen', '')).strip()
                    page_row[f'Cutout_{idx}'] = str(item.get('Cutout size', '')).strip()
                    page_row[f'CCT_{idx}'] = str(item.get('CCT', '')).strip()
                    
                    # Smart Lookup: PDF Data -> Excel Columns -> Default Fallbacks
                    pdf_info = pdf_extra_data.get(norm_key, {})
                    page_row[f'Flex_{idx}'] = pdf_info.get('Flex') or item.get('Flex', 'Fixed')
                    page_row[f'Mount_{idx}'] = pdf_info.get('Mounting') or item.get('Mounting', 'Recessed')
                    
                    # Single-letter Beam Angle tags (3 chars total)
                    page_row['A'] = item.get('Beam_A', '')
                    page_row['B'] = item.get('Beam_B', '')
                    page_row['C'] = item.get('Beam_C', '')
                    page_row['D'] = item.get('Beam_D', '')
                    
                    page_row[f'@Image_{idx}'] = f"Images/{raw_sku}.png"
                    
                pivoted_rows.append(page_row)

        df_pivoted = pd.DataFrame(pivoted_rows)
        csv_data = df_pivoted.to_csv(index=False, encoding='utf-8-sig')

        st.success("✅ Smart Conversion Completed!")
        st.download_button(
            label="📥 Download Pivoted CSV File",
            data=csv_data,
            file_name="pivoted_catalog_data_v8.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Error processing file: {e}")
