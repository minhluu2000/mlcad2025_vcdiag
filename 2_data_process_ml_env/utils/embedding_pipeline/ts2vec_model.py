import numpy as np
from ts2vec import TS2Vec

from .base_model import BaseEmbeddingModel

class TS2VecEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, input_dims: int, output_dims: int = 2048, model_path: str = None):
        self.model = TS2Vec(input_dims=input_dims, output_dims=output_dims)
        if model_path:
            self.model.load(model_path)

    def encode(self, time_series: np.ndarray) -> np.ndarray:
        time_series = time_series[np.newaxis, :, :]  # shape: (1, T, D)
        embedding = self.model.encode(time_series, encoding_window='full_series')[0]
        return embedding
