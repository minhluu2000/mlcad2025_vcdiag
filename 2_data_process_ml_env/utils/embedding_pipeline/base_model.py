from abc import ABC, abstractmethod
import numpy as np

class BaseEmbeddingModel(ABC):
    @abstractmethod
    def encode(self, time_series: np.ndarray) -> np.ndarray:
        """
        Encode a single time series into a fixed-size embedding.
        :param time_series: np.ndarray of shape (T, D)
        :return: np.ndarray of shape (embedding_dim,)
        """
        pass
