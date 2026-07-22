"""Deterministic offline training adapter for the permanent production MLP."""

from __future__ import annotations

import hashlib

import numpy as np

from app.config import production_model_config
from app.dataset_builder.contracts import NumericValue, TrainingExample
from app.evaluation.contracts import PredictionRow
from app.experiments.configuration import canonical_metadata
from app.experiments.contracts import (
    MetadataValue,
    ModelAdapterOutput,
    ModelExecutionRequest,
    ModelInputRow,
)

from .configuration import ProductionModelConfig
from .contracts import (
    ProductionLayer,
    ProductionModelArtifact,
    ProductionTrainingSummary,
)
from .exceptions import ProductionConfigurationError, ProductionDataError
from .serialization import ProductionModelSerializer


class DeterministicMLPRegressorAdapter:
    """Train a seeded normalized MLP with deterministic full-batch Adam."""

    algorithm_identifier = production_model_config.PRODUCTION_MODEL_ALGORITHM
    model_version = production_model_config.PRODUCTION_MODEL_SCHEMA_VERSION

    def __init__(self, config: ProductionModelConfig) -> None:
        self._config = config

    @property
    def hyperparameters(self) -> tuple[MetadataValue, ...]:
        """Return canonical Phase 5 hyperparameters."""

        return self._config.metadata()

    @property
    def random_seed(self) -> int:
        """Return the deterministic initialization seed."""

        return self._config.random_seed

    def execute(self, request: ModelExecutionRequest) -> ModelAdapterOutput:
        """Train, serialize, reload, and predict through the Phase 5 contract."""

        self._validate_request(request)
        feature_schema = request.dataset.feature_schema.feature_names
        target_schema = request.dataset.feature_schema.target_names
        x_train = self._matrix(
            tuple(example.features for example in request.training_examples),
            feature_schema,
            "training features",
        )
        y_train = self._matrix(
            tuple(example.targets for example in request.training_examples),
            target_schema,
            "training targets",
        )
        if request.validation_examples:
            x_validation = self._matrix(
                tuple(example.features for example in request.validation_examples),
                feature_schema,
                "validation features",
            )
            y_validation = self._matrix(
                tuple(example.targets for example in request.validation_examples),
                target_schema,
                "validation targets",
            )
        else:
            x_validation = y_validation = None
        x_predict = self._matrix(
            tuple(row.features for row in request.prediction_inputs),
            feature_schema,
            "prediction features",
        )
        artifact = self._train(
            request,
            x_train,
            y_train,
            x_validation,
            y_validation,
        )
        payload = ProductionModelSerializer.dumps(artifact)
        loaded = ProductionModelSerializer.loads(
            payload,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )
        predicted = loaded.predict(x_predict)
        rows = tuple(
            sorted(
                (
                    PredictionRow(
                        example_id=input_row.example_id,
                        target_name=target_name,
                        value=float(predicted[row_index, target_index]),
                    )
                    for row_index, input_row in enumerate(request.prediction_inputs)
                    for target_index, target_name in enumerate(target_schema)
                ),
                key=lambda row: (row.example_id, row.target_name),
            )
        )
        return ModelAdapterOutput(
            model_id=artifact.model_id,
            model_version=artifact.model_version,
            feature_schema=feature_schema,
            target_schema=target_schema,
            model_artifact=payload,
            model_artifact_media_type=production_model_config.PRODUCTION_MODEL_MEDIA_TYPE,
            prediction_rows=rows,
            execution_metadata=canonical_metadata(
                {
                    "selected_epoch": artifact.training_summary.selected_epoch,
                    "training_example_count": len(request.training_examples),
                    "validation_example_count": len(request.validation_examples),
                }
            ),
        )

    def _train(
        self,
        request: ModelExecutionRequest,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_validation: np.ndarray | None,
        y_validation: np.ndarray | None,
    ) -> ProductionModelArtifact:
        feature_mean = x_train.mean(axis=0)
        feature_scale = x_train.std(axis=0)
        feature_scale[feature_scale == 0] = 1.0
        target_mean = y_train.mean(axis=0)
        target_scale = y_train.std(axis=0)
        target_scale[target_scale == 0] = 1.0
        normalized_x = (x_train - feature_mean) / feature_scale
        normalized_y = (y_train - target_mean) / target_scale
        normalized_validation_x = (
            None
            if x_validation is None
            else (x_validation - feature_mean) / feature_scale
        )
        normalized_validation_y = (
            None
            if y_validation is None
            else (y_validation - target_mean) / target_scale
        )
        dimensions = (
            x_train.shape[1],
            *self._config.hidden_layer_sizes,
            y_train.shape[1],
        )
        random = np.random.default_rng(self.random_seed)
        weights = [
            random.uniform(
                -np.sqrt(6.0 / (input_size + output_size)),
                np.sqrt(6.0 / (input_size + output_size)),
                size=(input_size, output_size),
            )
            for input_size, output_size in zip(dimensions[:-1], dimensions[1:])
        ]
        biases = [np.zeros(size, dtype=np.float64) for size in dimensions[1:]]
        first_weight = [np.zeros_like(value) for value in weights]
        second_weight = [np.zeros_like(value) for value in weights]
        first_bias = [np.zeros_like(value) for value in biases]
        second_bias = [np.zeros_like(value) for value in biases]
        best_weights = [value.copy() for value in weights]
        best_biases = [value.copy() for value in biases]
        best_loss = float("inf")
        best_epoch = 1
        for epoch in range(1, self._config.epochs + 1):
            activations = self._forward(normalized_x, weights, biases)
            gradient = 2.0 * (activations[-1] - normalized_y) / normalized_y.size
            weight_gradients: list[np.ndarray] = []
            bias_gradients: list[np.ndarray] = []
            for layer_index in reversed(range(len(weights))):
                weight_gradients.append(
                    activations[layer_index].T @ gradient
                    + 2.0 * self._config.l2_penalty * weights[layer_index]
                )
                bias_gradients.append(gradient.sum(axis=0))
                if layer_index:
                    gradient = (gradient @ weights[layer_index].T) * (
                        1.0 - activations[layer_index] ** 2
                    )
            weight_gradients.reverse()
            bias_gradients.reverse()
            self._adam_update(
                weights,
                weight_gradients,
                first_weight,
                second_weight,
                epoch,
            )
            self._adam_update(
                biases,
                bias_gradients,
                first_bias,
                second_bias,
                epoch,
            )
            selection_x = (
                normalized_validation_x
                if normalized_validation_x is not None
                else normalized_x
            )
            selection_y = (
                normalized_validation_y
                if normalized_validation_y is not None
                else normalized_y
            )
            loss = float(
                np.mean((self._forward(selection_x, weights, biases)[-1] - selection_y) ** 2)
            )
            if loss < best_loss:
                best_loss = loss
                best_epoch = epoch
                best_weights = [value.copy() for value in weights]
                best_biases = [value.copy() for value in biases]
        training_loss = float(
            np.mean(
                (
                    self._forward(normalized_x, best_weights, best_biases)[-1]
                    - normalized_y
                )
                ** 2
            )
        )
        model_id = (
            f"{self.algorithm_identifier}-{request.spec.configuration_hash[:24]}"
        )
        return ProductionModelArtifact(
            model_id=model_id,
            configuration_hash=request.spec.configuration_hash,
            random_seed=self.random_seed,
            feature_schema=request.dataset.feature_schema.feature_names,
            target_schema=request.dataset.feature_schema.target_names,
            hyperparameters=self.hyperparameters,
            feature_mean=tuple(float(value) for value in feature_mean),
            feature_scale=tuple(float(value) for value in feature_scale),
            target_mean=tuple(float(value) for value in target_mean),
            target_scale=tuple(float(value) for value in target_scale),
            layers=tuple(
                ProductionLayer(
                    weights=tuple(
                        tuple(float(value) for value in row) for row in weight
                    ),
                    biases=tuple(float(value) for value in bias),
                )
                for weight, bias in zip(best_weights, best_biases)
            ),
            training_summary=ProductionTrainingSummary(
                selected_epoch=best_epoch,
                training_loss=training_loss,
                validation_loss=(
                    best_loss if normalized_validation_x is not None else None
                ),
                training_example_count=x_train.shape[0],
                validation_example_count=(
                    0 if x_validation is None else x_validation.shape[0]
                ),
            ),
        )

    def _adam_update(
        self,
        parameters: list[np.ndarray],
        gradients: list[np.ndarray],
        first: list[np.ndarray],
        second: list[np.ndarray],
        epoch: int,
    ) -> None:
        for index, gradient in enumerate(gradients):
            first[index] = (
                self._config.adam_beta_one * first[index]
                + (1 - self._config.adam_beta_one) * gradient
            )
            second[index] = (
                self._config.adam_beta_two * second[index]
                + (1 - self._config.adam_beta_two) * gradient * gradient
            )
            corrected_first = first[index] / (1 - self._config.adam_beta_one**epoch)
            corrected_second = second[index] / (1 - self._config.adam_beta_two**epoch)
            parameters[index] -= self._config.learning_rate * corrected_first / (
                np.sqrt(corrected_second) + self._config.adam_epsilon
            )

    @staticmethod
    def _forward(
        features: np.ndarray,
        weights: list[np.ndarray],
        biases: list[np.ndarray],
    ) -> list[np.ndarray]:
        activations = [features]
        for index, (weight, bias) in enumerate(zip(weights, biases)):
            values = activations[-1] @ weight + bias
            activations.append(
                np.tanh(values) if index < len(weights) - 1 else values
            )
        return activations

    def _validate_request(self, request: ModelExecutionRequest) -> None:
        if (
            request.spec.algorithm_identifier != self.algorithm_identifier
            or request.spec.hyperparameters != self.hyperparameters
            or request.spec.random_seed != self.random_seed
        ):
            raise ProductionConfigurationError(
                "Production adapter disagrees with the immutable experiment specification."
            )

    @staticmethod
    def _matrix(
        rows: tuple[tuple[NumericValue, ...], ...],
        schema: tuple[str, ...],
        description: str,
    ) -> np.ndarray:
        if not rows or any(tuple(item.name for item in row) != schema for row in rows):
            raise ProductionDataError(f"{description.title()} do not match their schema.")
        matrix = np.asarray(
            [[item.value for item in row] for row in rows],
            dtype=np.float64,
        )
        if not np.isfinite(matrix).all():
            raise ProductionDataError(f"{description.title()} must be finite.")
        return matrix
