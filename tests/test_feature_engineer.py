import os
import sys
import logging
import json
from pathlib import Path
import pandas as pd
import numpy as np

# Add the parent directory to the Python path to make the pie module importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pie.feature_engineer import FeatureEngineer
from pie.reporting import generate_feature_engineering_report_html

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PIE.test_feature_engineer")

def test_feature_engineering_pipeline(
    input_csv_path: str = "output/final_reduced_consolidated_data.csv",
    output_csv_path: str = "output/final_engineered_dataset.csv",
    output_report_html_path: str = "output/feature_engineering_report.html"
):
    """
    Tests the FeatureEngineer class on data that has been reduced and consolidated.
    """
    logger.info("Starting feature engineering pipeline test...")
    report_data_collector = {
        'input_csv_path': input_csv_path,
        'output_csv_path': output_csv_path,
    }

    # --- 1. Load Data ---
    input_file = Path(input_csv_path)
    if not input_file.exists():
        logger.error(f"Input data file not found: {input_csv_path}. Test cannot proceed.")
        logger.error("Please ensure 'test_data_reducer.py' has run successfully to generate this file.")
        return

    try:
        df = pd.read_csv(input_file)
        report_data_collector['input_data_shape'] = df.shape
        logger.info(f"Successfully loaded data from: {input_csv_path}. Shape: {df.shape}")
    except Exception as e:
        logger.error(f"Failed to load data from {input_csv_path}: {e}", exc_info=True)
        return
    
    if df.empty:
        logger.warning("Input DataFrame is empty. No feature engineering will be performed.")
        report_data_collector['feature_engineering_summary'] = {}
        report_data_collector['output_data_shape'] = df.shape
        generate_feature_engineering_report_html(report_data_collector, output_report_html_path)
        return

    # --- 2. Feature Engineering ---
    logger.info("Initializing FeatureEngineer...")
    engineer = FeatureEngineer(df.copy()) # Work on a copy

    # Example: One-hot encode, explicitly ignoring COHORT, PATNO, EVENT_ID
    # The FeatureEngineer's one_hot_encode method now defaults to ignoring these.
    # We can specify additional columns via `ignore_for_ohe` if needed.
    logger.info("Performing one-hot encoding (auto-identify)...")
    engineer.one_hot_encode(
        auto_identify_threshold=20, # Encode if unique values <= 20
        max_categories_to_encode=25, # Safety net
        min_frequency_for_category=0.01, # Group rare categories
        dummy_na=False,
        drop_first=True
        # ignore_for_ohe=['another_id_column_if_any'] # Example of adding more ignores
    )
    logger.info(f"Shape after OHE: {engineer.get_dataframe().shape}")

    # Example: Scale numeric features
    # Auto-identifies numeric columns (excluding PATNO, EVENT_ID by default within scale_numeric_features)
    logger.info("Performing numeric feature scaling (standard)...")
    engineer.scale_numeric_features(scaler_type='standard')
    logger.info(f"Shape after scaling: {engineer.get_dataframe().shape}")

    # Example: Polynomial features on a couple of numeric columns if they exist
    numeric_cols = engineer.get_dataframe().select_dtypes(include=np.number).columns
    potential_poly_cols = [col for col in numeric_cols if col.upper() not in ['PATNO', 'EVENT_ID', 'COHORT']][:2]
    if len(potential_poly_cols) >= 1: # Need at least one for non-interaction, 2 for interaction
        logger.info(f"Generating polynomial features for: {potential_poly_cols}")
        engineer.engineer_polynomial_features(columns=potential_poly_cols, degree=2, interaction_only=False)
        logger.info(f"Shape after polynomial features: {engineer.get_dataframe().shape}")
    else:
        logger.info("Not enough suitable numeric columns found for polynomial feature demonstration.")
    
    # Example: Distribution transformation for a numeric column if one exists
    if len(potential_poly_cols) > 0: # Reuse first identified numeric non-ID/target column
        col_to_transform = potential_poly_cols[0]
        # Check if this column still exists and is numeric
        if col_to_transform in engineer.get_dataframe().columns and \
           pd.api.types.is_numeric_dtype(engineer.get_dataframe()[col_to_transform]):
            
            min_val = engineer.get_dataframe()[col_to_transform].min()
            constant_to_add = 0
            if min_val <= 0:
                constant_to_add = abs(min_val) + 1e-6 # Add small epsilon if min is 0 or negative
                logger.info(f"Min value of '{col_to_transform}' is {min_val}. Adding constant {constant_to_add} for log transform.")
            
            logger.info(f"Applying log transformation to '{col_to_transform}' (new column: {col_to_transform}_log)")
            engineer.transform_numeric_distribution(
                column_name=col_to_transform,
                new_column_name=f"{col_to_transform}_log",
                transform_type='log',
                add_constant_for_log_sqrt=constant_to_add if constant_to_add > 0 else None
            )
            logger.info(f"Shape after log transformation: {engineer.get_dataframe().shape}")
    else:
        logger.info("No suitable column found for distribution transformation demonstration.")


    final_engineered_df = engineer.get_dataframe()
    report_data_collector['output_data_shape'] = final_engineered_df.shape
    report_data_collector['feature_engineering_summary'] = engineer.get_engineered_feature_summary()
    
    logger.info(f"Final DataFrame shape after all feature engineering: {final_engineered_df.shape}")
    logger.info(f"Feature Engineering Summary: {json.dumps(report_data_collector['feature_engineering_summary'], indent=2)}")

    # --- 3. Save Final Engineered Data ---
    if output_csv_path and not final_engineered_df.empty:
        try:
            Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)
            final_engineered_df.to_csv(output_csv_path, index=False)
            logger.info(f"Final engineered DataFrame saved to: {output_csv_path}")
        except Exception as e:
            logger.error(f"Failed to save final engineered DataFrame: {e}")
    elif final_engineered_df.empty:
        logger.warning(f"Final engineered DataFrame is empty. Not saving to {output_csv_path}")

    # --- 4. Generate HTML Report for Feature Engineering ---
    generate_feature_engineering_report_html(report_data_collector, output_report_html_path)
    
    # Try to open the report
    try:
        import webbrowser
        report_abs_path = Path(output_report_html_path).resolve()
        webbrowser.open(f"file://{report_abs_path}")
        logger.info(f"Attempted to open FE report in browser: file://{report_abs_path}")
    except Exception as e:
        logger.info(f"Could not automatically open the FE report in browser: {e}")


if __name__ == "__main__":
    # This script expects "output/final_reduced_consolidated_data.csv" to exist.
    # For standalone testing, ensure this file is present or create a placeholder.
    input_path = "output/final_reduced_consolidated_data.csv"
    report_path = "output/feature_engineering_report.html"
    output_engineered_path = "output/final_engineered_dataset.csv"

    test_feature_engineering_pipeline(
        input_csv_path=input_path,
        output_csv_path=output_engineered_path,
        output_report_html_path=report_path
    )
