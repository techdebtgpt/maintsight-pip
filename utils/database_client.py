"""Database client for CLI to save predictions to central database."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Client to save predictions to central MaintSight database via API."""

    def __init__(
        self, api_base_url: Optional[str] = None, api_key: Optional[str] = None
    ):
        """
        Initialize database client.

        Args:
            api_base_url: Base URL of the MaintSight API server
            api_key: API key for authentication (if required)`
        """
        self.api_base_url = api_base_url or os.getenv(
            "MAINTSIGHT_API_URL", "http://localhost:8000"
        )
        self.api_key = api_key or os.getenv("MAINTSIGHT_API_KEY")
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        self.session.headers.update({"Content-Type": "application/json"})

        # Test connection
        self.is_connected = self._test_connection()

        # Store last saved predictions with database IDs for HTML generation
        self._last_saved_predictions = []

    def _test_connection(self) -> bool:
        """Test connection to the MaintSight API."""
        try:
            response = self.session.get(f"{self.api_base_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info("Connected to MaintSight database API")
                return True
            else:
                logger.warning(f"MaintSight API returned status {response.status_code}")
                return False
        except Exception as e:
            logger.warning(
                f"Cannot connect to MaintSight API at {self.api_base_url}: {e}"
            )
            return False

    def save_prediction_run(
        self,
        repository_path: str,
        predictions: List[Any],
        commit_data: List[Any],
        metadata: Dict[str, Any],
        processing_mode: str = "moderate",
        features_df: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Save prediction run to central database.

        Args:
            repository_path: Path to the analyzed repository
            predictions: List of RiskPrediction objects
            commit_data: Git commit data
            metadata: Model metadata
            processing_mode: Processing mode used
            features_df: DataFrame containing feature values for each file

        Returns:
            Run ID if successful, None otherwise
        """
        if not self.is_connected:
            logger.warning("Not connected to database - predictions will not be saved")
            return None

        try:
            # Prepare request data - send RESULTS not paths for analysis
            repo_name = Path(repository_path).name

            # Convert predictions to serializable format with feature values
            predictions_data = []
            feature_names = metadata.get("feature_list", [])
            logger.info(
                f"Expected {len(feature_names)} features: "
                f"{feature_names[:5]}... (showing first 5)"
            )
            shape = features_df.shape if features_df is not None else "None"
            logger.info(f"Features DF shape: {shape}")
            logger.info(
                f"Features DF columns: {features_df.columns.tolist()[:5] if features_df is not None else 'None'}... (showing first 5)"
            )

            for pred in predictions:
                pred_data = {
                    "file_path": pred.module,
                    "risk_category": pred.risk_category.value,
                    "normalized_score": pred.normalized_score,
                    "raw_prediction": pred.raw_prediction,
                }

                logger.info(f"Processing prediction for {pred.module}")

                # Add feature values if available
                if features_df is not None:
                    try:
                        # Find the row for this file in the features dataframe
                        # The features_df uses module name as index, not as a column
                        if pred.module in features_df.index:
                            file_row = features_df.loc[pred.module]

                            # Extract feature values as a dictionary
                            feature_values = {}
                            for feature_name in feature_names:
                                if feature_name in file_row.index:
                                    value = file_row[feature_name]
                                    # Convert numpy types to Python types for JSON serialization
                                    if hasattr(value, "item"):
                                        value = value.item()
                                    feature_values[feature_name] = value

                            pred_data["feature_values"] = feature_values
                            logger.info(
                                f"Added {len(feature_values)} feature values for {pred.module}"
                            )
                        else:
                            logger.warning(
                                f"No features found for file {pred.module} in features_df"
                            )
                            pred_data["feature_values"] = {}
                    except Exception as e:
                        logger.warning(
                            f"Could not extract features for {pred.module}: {e}"
                        )
                        pred_data["feature_values"] = {}
                else:
                    logger.warning(
                        "features_df is None - no feature values will be stored"
                    )
                    pred_data["feature_values"] = {}

                predictions_data.append(pred_data)

            # Prepare metadata
            run_metadata = {
                "model_version": metadata.get("version"),
                "feature_count": len(metadata.get("feature_list", [])),
                "commit_data_count": len(commit_data) if commit_data else 0,
                "analysis_timestamp": datetime.now().isoformat(),
                "processing_mode": processing_mode,
            }

            request_data = {
                "repository_name": repo_name,
                "repository_path": repository_path,  # For reference only
                "branch": "main",  # Could be made configurable
                "predictions": predictions_data,
                "metadata": run_metadata,
                "total_files": len(predictions_data),
                "mean_risk_score": (
                    sum(p["normalized_score"] for p in predictions_data)
                    / len(predictions_data)
                    if predictions_data
                    else 0
                ),
            }

            # Send to CLI endpoint that expects results, not paths
            logger.info(f"Saving prediction run for {repo_name} to database...")
            response = self.session.post(
                f"{self.api_base_url}/api/v1/cli/analyze-from-cli",
                json=request_data,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                run_id = result.get("run_id")

                # Store the database IDs for HTML generation
                self._last_saved_predictions = result.get("predictions_with_ids", [])

                logger.info(f"✅ Prediction run saved successfully (ID: {run_id})")
                return run_id
            else:
                logger.error(
                    f"Failed to save prediction run: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error saving prediction run: {e}")
            return None

    def _save_predictions_batch(
        self, run_id: str, predictions_data: List[Dict]
    ) -> bool:
        """Save batch of predictions for a run (deprecated - now done in single request)."""
        # This method is no longer used as predictions are saved in the initial request
        return True

    def update_prediction_category(
        self,
        prediction_id: str,
        new_category: str,
        notes: Optional[str] = None,
        user_identifier: Optional[str] = None,
    ) -> bool:
        """
        Update prediction category in database.

        Args:
            prediction_id: ID of prediction to update
            new_category: New risk category
            notes: Optional notes about the change
            user_identifier: User making the change

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected:
            return False

        try:
            request_data = {
                "prediction_id": prediction_id,
                "new_category": new_category,
                "notes": notes,
                "user_identifier": user_identifier or "html_interface",
            }

            response = self.session.put(
                f"{self.api_base_url}/api/v1/predictions/{prediction_id}/category",
                json=request_data,
                timeout=10,
            )

            if response.status_code == 200:
                logger.info(
                    f"✅ Updated prediction {prediction_id} category to {new_category}"
                )
                return True
            else:
                logger.error(
                    f"Failed to update prediction category: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error updating prediction category: {e}")
            return False

    def get_prediction_data(
        self, file_path: str, repository_path: str
    ) -> Optional[Dict]:
        """
        Get prediction data for a specific file to enable editing.

        Args:
            file_path: Path to the file within repository
            repository_path: Repository path

        Returns:
            Prediction data if found, None otherwise
        """
        if not self.is_connected:
            return None

        try:
            # This would require a search endpoint
            response = self.session.get(
                f"{self.api_base_url}/api/v1/predictions/search",
                params={"file_path": file_path, "repository_path": repository_path},
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            logger.warning(f"Error getting prediction data: {e}")
            return None


# Global database client instance
_db_client = None


def get_database_client() -> DatabaseClient:
    """Get or create global database client instance."""
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client


def configure_database_client(api_url: str, api_key: Optional[str] = None):
    """Configure the global database client."""
    global _db_client
    _db_client = DatabaseClient(api_url, api_key)


def get_predictions_with_database_ids(run_id: str) -> List[Dict]:
    """
    Get predictions with their database IDs for HTML generation.

    Args:
        run_id: The prediction run ID

    Returns:
        List of predictions with database IDs
    """
    client = get_database_client()
    if not client.is_connected or not run_id:
        return []

    try:
        response = client.session.get(
            f"{client.api_base_url}/api/v1/cli/runs/{run_id}/predictions", timeout=10
        )

        if response.status_code == 200:
            return response.json().get("predictions", [])
        else:
            logger.warning(
                f"Failed to get predictions with IDs: {response.status_code}"
            )
            return []

    except Exception as e:
        logger.warning(f"Error getting predictions with IDs: {e}")
        return []
