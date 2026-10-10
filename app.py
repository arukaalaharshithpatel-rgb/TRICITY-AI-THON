
import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO
from difflib import SequenceMatcher

# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="SaaSum AI",
    page_icon="🧹",
    layout="wide"
)

st.title("🧹 SaaSum AI")
st.subheader("Clean. Validate. Standardize. Transform.")

st.write(
    "Upload a messy dataset to remove duplicates, handle missing "
    "values, correct recognizable data errors, standardize values, "
    "and download a clean file."
)


# =========================================================
# 2. HELPER FUNCTIONS
# =========================================================

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100
}


def normalize_key(value):
    return re.sub(
        r"\s+", " ", str(value).strip()
    ).casefold()


def number_value(value):
    """Convert numeric values or supported number words to numbers."""
    if pd.isna(value):
        return np.nan

    if isinstance(value, (int, float, np.number)):
        return float(value)

    text = str(value).strip().casefold()

    if text in NUMBER_WORDS:
        return float(NUMBER_WORDS[text])

    text = text.replace(",", "")

    try:
        return float(text)
    except (ValueError, TypeError):
        return np.nan


def suggest_value(column, value, unique_values):
    """Suggest corrections for common categorical inconsistencies."""
    text = str(value).strip()
    key = normalize_key(text)
    col = str(column).casefold()

    if key in {"yes", "y", "true"}:
        return "Yes"

    if key in {"no", "n", "false"}:
        return "No"

    if "gender" in col or col == "sex":
        aliases = {
            "m": "Male",
            "male": "Male",
            "man": "Male",
            "f": "Female",
            "female": "Female",
            "woman": "Female"
        }
        if key in aliases:
            return aliases[key]

    if "city" in col or "location" in col:
        aliases = {
            "hyd": "Hyderabad",
            "hyderabad": "Hyderabad",
            "warangal": "Warangal",
            "karimnagar": "Karimnagar",
            "nizamabad": "Nizamabad"
        }
        if key in aliases:
            return aliases[key]

    matches = [
        str(v).strip()
        for v in unique_values
        if normalize_key(v) == key
    ]

    if len(set(matches)) > 1:
        counts = pd.Series(matches).value_counts()
        return str(counts.index[0])

    # Similar-spelling suggestions are suggestions only.
    candidates = []

    for other in unique_values:
        other_text = str(other).strip()
        other_key = normalize_key(other_text)

        if other_key == key or len(key) < 5:
            continue

        similarity = SequenceMatcher(
            None, key, other_key
        ).ratio()

        if similarity >= 0.88:
            candidates.append((similarity, other_text))

    if candidates:
        candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )
        return candidates[0][1]

    if text.isupper() or text.islower():
        return text.title()

    return text


# =========================================================
# 3. UPLOAD DATASET
# =========================================================

st.divider()
st.header("📂 Upload Your Dataset")

uploaded_file = st.file_uploader(
    "Choose a CSV or Excel file",
    type=["csv", "xlsx"],
    key="dataset_upload"
)

if uploaded_file is None:
    st.info("Upload a CSV or Excel file to get started.")
    st.stop()

try:
    if uploaded_file.name.lower().endswith(".csv"):
        original_df = pd.read_csv(uploaded_file)
    else:
        original_df = pd.read_excel(uploaded_file)

    if original_df.empty:
        st.warning("The uploaded file has no data rows.")
        st.stop()

    original_df = original_df.copy()

    # Ensure column names are not blank or duplicated.
    new_names = []
    used_names = set()

    for index, name in enumerate(original_df.columns):
        base = str(name).strip() or f"Column_{index + 1}"
        candidate = base
        counter = 2

        while candidate in used_names:
            candidate = f"{base}_{counter}"
            counter += 1

        new_names.append(candidate)
        used_names.add(candidate)

    original_df.columns = new_names

    # Blank cells and whitespace-only cells count as missing.
    original_df = original_df.replace(
        r"^\s*$", pd.NA, regex=True
    )

except Exception as error:
    st.error("Unable to read the uploaded file.")
    st.exception(error)
    st.stop()

st.subheader("Original Dataset")
st.caption(
    f"{len(original_df)} rows × {len(original_df.columns)} columns"
)
st.dataframe(
    original_df.astype("string"),
    width="stretch"
)


# =========================================================
# 4. DUPLICATE DETECTION AND REMOVAL
# =========================================================

st.divider()
st.header("1. Duplicate Detection")

duplicate_count = int(original_df.duplicated().sum())

st.metric("Duplicate rows detected", duplicate_count)

if duplicate_count:
    with st.expander("View duplicate rows"):
        st.dataframe(
            original_df[
                original_df.duplicated(keep=False)
            ].astype("string"),
            width="stretch"
        )

remove_duplicates = st.checkbox(
    "Remove exact duplicate rows",
    value=True,
    key="remove_duplicates"
)

if remove_duplicates:
    working_df = original_df.drop_duplicates().copy()
else:
    working_df = original_df.copy()

rows_removed_duplicates = len(original_df) - len(working_df)


# =========================================================
# 5. MISSING-VALUE HANDLING
# =========================================================

st.divider()
st.header("2. Missing-Value Detection")

missing_counts = working_df.isna().sum()
missing_report = pd.DataFrame({
    "Column": missing_counts.index,
    "Missing Cells": missing_counts.values
})

missing_report = missing_report[
    missing_report["Missing Cells"] > 0
]

m1, m2 = st.columns(2)

m1.metric(
    "Missing cells",
    int(missing_counts.sum())
)

m2.metric(
    "Columns with missing values",
    int((missing_counts > 0).sum())
)

if not missing_report.empty:
    st.dataframe(missing_report, width="stretch")
else:
    st.success("No missing values detected.")

missing_action = st.radio(
    "Choose how to handle missing values:",
    [
        "Keep missing values",
        "Remove rows with missing values",
        "Fill missing values"
    ],
    key="missing_action"
)

rows_removed_missing = 0
filled_cells = 0

if missing_action == "Remove rows with missing values":
    before = len(working_df)
    working_df = working_df.dropna().copy()
    rows_removed_missing = before - len(working_df)

elif missing_action == "Fill missing values":
    for column in working_df.columns:
        missing_count = int(working_df[column].isna().sum())

        if missing_count == 0:
            continue

        if pd.api.types.is_numeric_dtype(working_df[column]):
            fill_value = working_df[column].median()
        else:
            modes = working_df[column].dropna().mode()
            fill_value = modes.iloc[0] if not modes.empty else None

        if fill_value is not None and pd.notna(fill_value):
            working_df[column] = working_df[column].fillna(fill_value)
            filled_cells += missing_count


# =========================================================
# 6. TEXT NORMALIZATION
# =========================================================

st.divider()
st.header("3. Text Normalization")

text_columns = working_df.select_dtypes(
    include=["object", "string", "category"]
).columns.tolist()

if text_columns:
    norm_columns = st.multiselect(
        "Select text columns to normalize:",
        options=text_columns,
        default=text_columns,
        key="norm_columns"
    )

    trim_spaces = st.checkbox(
        "Remove extra spaces",
        value=True,
        key="trim_spaces"
    )

    letter_format = st.selectbox(
        "Text format:",
        [
            "Keep original case",
            "Title Case",
            "lowercase",
            "UPPERCASE"
        ],
        key="letter_format"
    )

    for column in norm_columns:
        values = working_df[column].astype("string")

        if trim_spaces:
            values = values.str.strip()
            values = values.str.replace(
                r"\s+", " ", regex=True
            )

        if letter_format == "Title Case":
            values = values.str.title()
        elif letter_format == "lowercase":
            values = values.str.lower()
        elif letter_format == "UPPERCASE":
            values = values.str.upper()

        working_df[column] = values


# =========================================================
# 7. SMART STANDARDIZATION
# =========================================================

st.divider()
st.header("4. Smart Value Standardization")

st.write(
    "Review suggestions for all text columns. Edit a suggested "
    "value if it is not correct."
)

text_columns = working_df.select_dtypes(
    include=["object", "string", "category"]
).columns.tolist()

standardize_all = st.checkbox(
    "Enable standardization for all text columns",
    value=True,
    key="standardize_all"
)

if standardize_all:
    for col_index, column in enumerate(text_columns):
        with st.expander(f"Review: {column}", expanded=False):
            counts = (
                working_df[column]
                .dropna()
                .astype(str)
                .value_counts()
            )

            values = counts.index.tolist()

            if not values:
                st.info("No values to standardize.")
                continue

            if len(values) > 300:
                st.warning(
                    "More than 300 distinct values. "
                    "Skipping suggestions for this column."
                )
                continue

            mapping = {}

            for value_index, value in enumerate(values):
                suggestion = suggest_value(
                    column, value, values
                )

                left, right = st.columns(2)

                with left:
                    st.text_input(
                        "Original value",
                        value=value,
                        disabled=True,
                        key=f"orig_{col_index}_{value_index}"
                    )
                    st.caption(
                        f"Occurrences: {int(counts[value])}"
                    )

                with right:
                    replacement = st.text_input(
                        "Standard value",
                        value=suggestion,
                        key=f"map_{col_index}_{value_index}"
                    )

                mapping[value] = replacement

            working_df[column] = (
                working_df[column]
                .astype("string")
                .replace(mapping)
            )

            changes = [
                (old, new)
                for old, new in mapping.items()
                if old != new
            ]

            if changes:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Original": old,
                            "Replacement": new,
                            "Rows affected": int(counts[old])
                        }
                        for old, new in changes
                    ]),
                    width="stretch"
                )


# =========================================================
# 8. AGE AND MARKS CORRECTION
# =========================================================

st.divider()
st.header("5. Age and Marks Error Correction")

st.write(
    "Recognizable number words such as 'Twenty' and 'Eighty' "
    "are converted to numbers. Values outside configured ranges "
    "are flagged. You choose whether to replace those invalid "
    "values with missing values."
)

# Find likely age and marks columns by column name.
age_columns = [
    column for column in working_df.columns
    if re.search(r"\bage\b", str(column), flags=re.IGNORECASE)
]

marks_columns = [
    column for column in working_df.columns
    if re.search(
        r"mark|score",
        str(column),
        flags=re.IGNORECASE
    )
]

# Allow user to choose columns if their names differ.
if not age_columns:
    st.info(
        "No column named Age was detected. You can select one below."
    )

age_column = st.selectbox(
    "Age column",
    options=["Do not process"] + working_df.columns.tolist(),
    index=(
        working_df.columns.tolist().index(age_columns[0]) + 1
        if age_columns else 0
    ),
    key="age_column"
)

if not marks_columns:
    st.info(
        "No column named Marks or Score was detected. "
        "You can select one below."
    )

marks_column = st.selectbox(
    "Marks/Score column",
    options=["Do not process"] + working_df.columns.tolist(),
    index=(
        working_df.columns.tolist().index(marks_columns[0]) + 1
        if marks_columns else 0
    ),
    key="marks_column"
)

# Convert selected columns using supported number words.
for selected_column in [age_column, marks_column]:
    if selected_column == "Do not process":
        continue

    original_values = working_df[selected_column].copy()

    converted = original_values.map(number_value)

    recognized_words = (
        original_values.notna()
        & original_values.astype(str).str.strip().str.casefold().isin(
            NUMBER_WORDS
        )
    )

    corrected_word_count = int(recognized_words.sum())

    # Only convert if at least one value is a recognized number word
    # or if the existing column is already numeric.
    has_numeric_data = pd.api.types.is_numeric_dtype(
        original_values
    )

    if has_numeric_data or corrected_word_count > 0:
        working_df[selected_column] = converted

        if corrected_word_count > 0:
            st.success(
                f"{selected_column}: converted "
                f"{corrected_word_count} number-word value(s)."
            )

# Build validation report for age and marks.
validation_issues = []

if age_column != "Do not process":
    numeric_age = pd.to_numeric(
        working_df[age_column],
        errors="coerce"
    )

    invalid_age = numeric_age.notna() & (
        (numeric_age < 0) | (numeric_age > 120)
    )

    for idx in working_df.index[invalid_age]:
        validation_issues.append({
            "Row": str(idx),
            "Column": age_column,
            "Current value": str(working_df.loc[idx, age_column]),
            "Problem": "Age outside 0–120",
            "Suggested action": "Review the original value"
        })

    invalid_age_text = (
        working_df[age_column].notna()
        & numeric_age.isna()
    )

    for idx in working_df.index[invalid_age_text]:
        validation_issues.append({
            "Row": str(idx),
            "Column": age_column,
            "Current value": str(working_df.loc[idx, age_column]),
            "Problem": "Age is not numeric",
            "Suggested action": "Correct the value manually"
        })

if marks_column != "Do not process":
    numeric_marks = pd.to_numeric(
        working_df[marks_column],
        errors="coerce"
    )

    invalid_marks = numeric_marks.notna() & (
        (numeric_marks < 0) | (numeric_marks > 100)
    )

    for idx in working_df.index[invalid_marks]:
        validation_issues.append({
            "Row": str(idx),
            "Column": marks_column,
            "Current value": str(working_df.loc[idx, marks_column]),
            "Problem": "Marks outside 0–100",
            "Suggested action": "Verify the marks scale and source"
        })

    invalid_marks_text = (
        working_df[marks_column].notna()
        & numeric_marks.isna()
    )

    for idx in working_df.index[invalid_marks_text]:
        validation_issues.append({
            "Row": str(idx),
            "Column": marks_column,
            "Current value": str(working_df.loc[idx, marks_column]),
            "Problem": "Marks are not numeric",
            "Suggested action": "Correct the value manually"
        })

if validation_issues:
    validation_df = pd.DataFrame(validation_issues)

    st.warning(
        f"Found {len(validation_df)} Age/Marks issue(s)."
    )

    st.dataframe(
        validation_df,
        width="stretch"
    )

    st.download_button(
        "Download Age and Marks Error Report",
        data=validation_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="saasum_age_marks_errors.csv",
        mime="text/csv"
    )

else:
    st.success(
        "No Age or Marks range problems were detected by these rules."
    )

# Explicitly ask before replacing out-of-range numeric values.
replace_invalid = st.checkbox(
    "Replace out-of-range Age/Marks values with missing values",
    value=False,
    key="replace_invalid"
)

if replace_invalid:
    if age_column != "Do not process":
        age_values = pd.to_numeric(
            working_df[age_column],
            errors="coerce"
        )

        working_df.loc[
            age_values.notna()
            & ((age_values < 0) | (age_values > 120)),
            age_column
        ] = np.nan

    if marks_column != "Do not process":
        marks_values = pd.to_numeric(
            working_df[marks_column],
            errors="coerce"
        )

        working_df.loc[
            marks_values.notna()
            & ((marks_values < 0) | (marks_values > 100)),
            marks_column
        ] = np.nan

    st.info(
        "Out-of-range values were replaced with missing values. "
        "Use the missing-value handling section or review the "
        "original dataset to determine the correct values."
    )


# =========================================================
# 9. ATTENDANCE AND EMAIL VALIDATION
# =========================================================

st.divider()
st.header("6. Other Data Quality Checks")

other_issues = []

for column in working_df.columns:
    name = str(column).casefold()

    if "attendance" in name:
        values = pd.to_numeric(
            working_df[column],
            errors="coerce"
        )

        bad = values.notna() & (
            (values < 0) | (values > 100)
        )

        for idx in working_df.index[bad]:
            other_issues.append({
                "Row": str(idx),
                "Column": column,
                "Value": str(working_df.loc[idx, column]),
                "Problem": "Attendance outside 0–100%"
            })

    if "email" in name or "e-mail" in name:
        for idx, value in working_df[column].items():
            if pd.isna(value):
                continue

            email = str(value).strip()

            if not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email
            ):
                other_issues.append({
                    "Row": str(idx),
                    "Column": column,
                    "Value": email,
                    "Problem": "Email format appears invalid"
                })

if other_issues:
    st.warning(
        f"Found {len(other_issues)} additional issue(s)."
    )

    st.dataframe(
        pd.DataFrame(other_issues),
        width="stretch"
    )
else:
    st.success(
        "No attendance or email-format issues were detected."
    )


# =========================================================
# 10. MIN-MAX NORMALIZATION
# =========================================================

st.divider()
st.header("7. Min-Max Numerical Normalization")

numeric_columns = working_df.select_dtypes(
    include=["number"]
).columns.tolist()

if numeric_columns:
    scale_columns = st.multiselect(
        "Choose numeric columns to scale between 0 and 1",
        options=numeric_columns,
        default=[],
        key="scale_columns"
    )

    for column in scale_columns:
        new_column = f"{column}_Normalized"

        if new_column in working_df.columns:
            st.warning(
                f"{new_column} already exists. "
                "Rename the existing column first."
            )
            continue

        minimum = working_df[column].min()
        maximum = working_df[column].max()

        if pd.isna(minimum) or pd.isna(maximum):
            st.warning(f"{column} has no usable numeric values.")
        elif minimum == maximum:
            working_df[new_column] = working_df[column].where(
                working_df[column].isna(), 0.0
            )
        else:
            working_df[new_column] = (
                (working_df[column] - minimum)
                / (maximum - minimum)
            )


# =========================================================
# 11. DATA RESTRUCTURING
# =========================================================

st.divider()
st.header("8. Data Restructuring")

st.subheader("Rename columns")

rename_map = {}
new_names = []

for index, column in enumerate(working_df.columns):
    name = st.text_input(
        f"Column {index + 1}: {column}",
        value=str(column),
        key=f"rename_{index}"
    ).strip()

    name = name or str(column)
    rename_map[column] = name
    new_names.append(name)

if len(new_names) != len(set(new_names)):
    st.error("Column names must be unique.")
    st.stop()

working_df = working_df.rename(columns=rename_map)

st.subheader("Remove unwanted columns")

remove_columns = st.multiselect(
    "Choose columns to remove",
    options=working_df.columns.tolist(),
    default=[],
    key="remove_columns"
)

if len(remove_columns) >= len(working_df.columns):
    st.warning("Keep at least one column.")
    st.stop()

working_df = working_df.drop(columns=remove_columns)

st.subheader("Reorder columns")

column_order = st.multiselect(
    "Select all columns in the desired order",
    options=working_df.columns.tolist(),
    default=working_df.columns.tolist(),
    key="column_order"
)

if (
    len(column_order) != len(working_df.columns)
    or set(column_order) != set(working_df.columns)
):
    st.warning("Select every remaining column exactly once.")
    st.stop()

working_df = working_df[column_order]


# =========================================================
# 12. BEFORE AND AFTER
# =========================================================

st.divider()
st.header("9. Before and After")

before_col, after_col = st.columns(2)

with before_col:
    st.subheader("Original")
    st.dataframe(
        original_df.astype("string"),
        width="stretch"
    )

with after_col:
    st.subheader("Cleaned")
    st.dataframe(
        working_df.astype("string"),
        width="stretch"
    )


# =========================================================
# 13. SUMMARY AND DOWNLOAD
# =========================================================

st.divider()
st.header("10. Cleaning Summary")

c1, c2, c3 = st.columns(3)

c1.metric("Original rows", len(original_df))
c2.metric("Final rows", len(working_df))
c3.metric("Final columns", len(working_df.columns))

st.write(f"**Duplicate rows detected:** {duplicate_count}")
st.write(f"**Duplicate rows removed:** {rows_removed_duplicates}")
st.write(f"**Rows removed for missing values:** {rows_removed_missing}")
st.write(f"**Missing cells filled:** {filled_cells}")
st.write(
    f"**Missing cells remaining:** "
    f"{int(working_df.isna().sum().sum())}"
)

st.divider()
st.header("📥 Download Cleaned Data")

csv_data = working_df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Download Cleaned CSV",
    data=csv_data,
    file_name="saasum_cleaned.csv",
    mime="text/csv"
)

excel_buffer = BytesIO()

with pd.ExcelWriter(
    excel_buffer,
    engine="openpyxl"
) as writer:
    working_df.to_excel(
        writer,
        index=False,
        sheet_name="Cleaned Data"
    )

st.download_button(
    "Download Cleaned Excel",
    data=excel_buffer.getvalue(),
    file_name="saasum_cleaned.xlsx",
    mime=(
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    )
)

st.success("Processing complete. Review validation warnings before downloading.")
