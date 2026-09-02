import pandas as pd
import re
import streamlit as st

st.set_page_config(page_title="Catalog Data Merger", layout="wide")
st.title("📦 Aurora Catalog CSV Converter")

uploaded_file = st.file_uploader("Upload Excel File (2025_Aurora List)", type=["xlsx"])

if uploaded_file:
    try:
        df_raw = pd.read_excel(uploaded_file, header=8)
        df_raw.columns = df_raw.iloc[0]
        df_raw = df_raw.iloc[2:].reset_index(drop=True)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]

        if 'S/R' in df_raw.columns:
            df_raw['S/R'] = df_raw['S/R'].ffill()

        df_clean = df_raw[df_raw['Item code'].notna() & (df_raw['Item code'] != '')].copy()

        def clean_series_title(val):
            if pd.isna(val):
                return ''
            # Kukunin lang ang unang linya, tatanggalin ang \n, \r, bullets, at extra spaces
            first_line = str(val).split('\n')[0]
            clean = re.sub(r'[•\r]', '', first_line).strip()
            return clean

        def extract_beam_angles(val):
            if pd.isna(val):
                return ['', '', '', '']
            clean_str = str(val).replace('•', '').replace('\r', '').replace('\n', ' ')
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
                    page_row[f'SKU_{idx}'] = str(item.get('Item code', '')).strip()
                    page_row[f'Power_{idx}'] = str(item.get('Output Power', '')).strip()
                    page_row[f'Lumen_{idx}'] = str(item.get('Delivered Lumen', '')).strip()
                    page_row[f'Cutout_{idx}'] = str(item.get('Cutout size', '')).strip()
                    page_row[f'CCT_{idx}'] = str(item.get('CCT', '')).strip()
                    
                    page_row[f'Beam_{idx}_1'] = item.get('Beam_A', '')
                    page_row[f'Beam_{idx}_2'] = item.get('Beam_B', '')
                    page_row[f'Beam_{idx}_3'] = item.get('Beam_C', '')
                    page_row[f'Beam_{idx}_4'] = item.get('Beam_D', '')
                    
                    page_row[f'@Image_{idx}'] = f"Images/{str(item.get('Item code', '')).strip()}.png"
                    
                pivoted_rows.append(page_row)

        df_pivoted = pd.DataFrame(pivoted_rows)
        csv_data = df_pivoted.to_csv(index=False, encoding='utf-8-sig')

        st.success("✅ Conversion Successful!")
        st.download_button(
            label="📥 Download Cleaned CSV File",
            data=csv_data,
            file_name="pivoted_catalog_data_v3.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Error processing file: {e}")
