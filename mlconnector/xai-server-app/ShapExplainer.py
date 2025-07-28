import joblib
import shap
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
from agents.mlsysops.logger_util import logger


class ShapExplainer:

    def __init__(self, model_path=None, test_data=None):
        
        self.shap_explainer = None
        self.model_path = model_path
        self.model = self.load_model()
        self.test_data = test_data
        logger.info(self.model)
    def load_model(self):
        return joblib.load(self.model_path)

    def preprocess_data(self):
        """Extracts the preprocessor and transforms the input data, while mapping original and transformed feature names."""
        preprocessor = self.model.named_steps['preprocessor']
        X_processed = preprocessor.transform(self.test_data)

        # Retrieve transformed feature names
        transformed_feature_names = preprocessor.get_feature_names_out().tolist()

        # Extract mapping from transformed features back to original feature names
        original_feature_names = list(self.test_data.columns)
        feature_mapping = {orig: [] for orig in original_feature_names}

        for transformer_name, _, feature_list in preprocessor.transformers_:
            for feature in feature_list:
                if feature in feature_mapping:
                    for transformed_name in transformed_feature_names:
                        if transformed_name.startswith(transformer_name + "__" + feature):
                            feature_mapping[feature].append(transformed_name)

        # Convert sparse matrix to dense matrix if needed
        X_dense = X_processed.toarray() if not isinstance(X_processed, np.ndarray) else X_processed

        return X_dense, transformed_feature_names, feature_mapping, preprocessor

    def explain_model(self, showImage=False):
        """Explains the model using SHAP, ensuring final feature names match the original input."""
        
        #global shap_explainer  # Store explainer globally for reuse

        # Preprocess data and get transformed feature names and mapping
        X_processed, transformed_feature_names, feature_mapping, _ = self.preprocess_data()

        # Initialize SHAP explainer using full dataset as reference
        self.shap_explainer = shap.Explainer(self.model.named_steps['regressor'], X_processed)

        # Get SHAP values for the processed test set
        shap_values = self.shap_explainer(X_processed)

        # Ensure SHAP values have feature names
        shap_values.feature_names = transformed_feature_names

        # Aggregate SHAP values back to original feature names
        aggregated_shap_values = []
        final_feature_names = []

        for original_feature, indices in feature_mapping.items():
            if indices:  # If the feature was transformed
                transformed_indices = [transformed_feature_names.index(f) for f in indices]
                aggregated_shap_values.append(np.sum(shap_values[:, transformed_indices].values, axis=1))
            else:  # If the feature was not transformed
                original_index = transformed_feature_names.index(original_feature)
                aggregated_shap_values.append(shap_values[:, original_index].values)

            final_feature_names.append(original_feature)

        # Convert to array with correct shape
        final_shap_values = np.column_stack(aggregated_shap_values)

        # Aggregate categorical features in input data
        X_final = np.column_stack(
            [np.mean(X_processed[:, [transformed_feature_names.index(f) for f in indices]], axis=1) if indices else X_processed[:, transformed_feature_names.index(original_feature)]
            for original_feature, indices in feature_mapping.items()]
        )

        # Validate shape consistency
        assert final_shap_values.shape == X_final.shape, f"Mismatch: SHAP values shape {final_shap_values.shape}, Data shape {X_final.shape}"

        # Create SHAP Explanation object
        shap_explainer_values = shap.Explanation(
            values=final_shap_values,
            base_values=shap_values.base_values,
            data=X_final,
            feature_names=final_feature_names
        )

        if showImage:
            # Plot SHAP summary
            shap.initjs()
            shap.plots.waterfall(shap_explainer_values[100])

    def explain_single_instance(self, new_row, showImage=True):
        """Explains a single new row using the trained model while maintaining the same SHAP background distribution."""
        

        if self.shap_explainer is None:
            raise ValueError("SHAP explainer is not initialized. Run explain_model() first.")

        # Ensure new_row is in DataFrame format
        if isinstance(new_row, dict):
            new_row = pd.DataFrame([new_row])  # Convert dictionary to DataFrame
        elif isinstance(new_row, pd.Series):
            new_row = new_row.to_frame().T  # Convert Series to DataFrame

        # Preprocess the single instance
        _, transformed_feature_names, feature_mapping, preprocessor = self.preprocess_data()
        new_row_processed = preprocessor.transform(new_row)

        # Convert sparse matrix to dense matrix if needed
        new_row_dense = new_row_processed.toarray() if not isinstance(new_row_processed, np.ndarray) else new_row_processed

        # Use the stored SHAP explainer to explain the new row
        shap_values = self.shap_explainer(new_row_dense)

        # Aggregate SHAP values back to original feature names
        aggregated_shap_values = []
        final_feature_names = []

        for original_feature, indices in feature_mapping.items():
            if indices:
                transformed_indices = [transformed_feature_names.index(f) for f in indices]
                aggregated_shap_values.append(np.sum(shap_values[:, transformed_indices].values, axis=1))
            else:
                original_index = transformed_feature_names.index(original_feature)
                aggregated_shap_values.append(shap_values[:, original_index].values)

            final_feature_names.append(original_feature)

        # Convert to array with correct shape
        final_shap_values = np.column_stack(aggregated_shap_values)

        # Aggregate categorical features in input data
        X_final = np.column_stack(
            [np.mean(new_row_dense[:, [transformed_feature_names.index(f) for f in indices]], axis=1) if indices else new_row_dense[:, transformed_feature_names.index(original_feature)]
            for original_feature, indices in feature_mapping.items()]
        )

        # Validate shape consistency
        assert final_shap_values.shape == X_final.shape, f"Mismatch: SHAP values shape {final_shap_values.shape}, Data shape {X_final.shape}"

        # Create SHAP Explanation object
        shap_explainer_single = shap.Explanation(
            values=final_shap_values,
            base_values=shap_values.base_values,
            data=X_final,
            feature_names=final_feature_names
        )
        img_buf = io.BytesIO()
        plt.figure()  # Create a new figure
        shap.plots.waterfall(shap_explainer_single[0], show=False)  
        plt.savefig(img_buf, bbox_inches="tight", dpi=300)  
        plt.close()
        img_buf.seek(0)

        img_base64 = base64.b64encode(img_buf.getvalue()).decode("utf-8")

        if showImage:
            img_buf = io.BytesIO()
            plt.figure()  # Create a new figure
            shap.plots.waterfall(shap_explainer_single[0])  
        return self.explainer_to_json_converter(shap_explainer_single[0]), img_base64

    def explainer_to_json_converter(self, shap_values):
        """  """
        shap_values_dict = {"values": shap_values.values.tolist(),  # Convert NumPy array to list
            "base_values": shap_values.base_values.tolist() if isinstance(shap_values.base_values, np.ndarray) else shap_values.base_values,
            "feature_names": shap_values.feature_names if shap_values.feature_names is not None else None,
            "data": shap_values.data.tolist() if hasattr(shap_values, "data") and shap_values.data is not None else None
        }
        return shap_values_dict
